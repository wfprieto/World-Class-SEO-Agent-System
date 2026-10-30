"""Execute the guarded CI compile/import boundary against owned source fixtures."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts import workflow_quality_contract as contract
from scripts.validate_source_integrity import validate
from tests.test_source_integrity import _repository

ROOT = Path(__file__).resolve().parents[1]
COMPILE_COMMAND = 'python -X "pycache_prefix=${{ runner.temp }}/wcseo-compile-cache" -m compileall -q .'
NO_BYTECODE = "PYTHONDONTWRITEBYTECODE"
BAD_VALUES = ["", "0", "true", "01", " 1", "1 ", "${{ '1' }}", 0, 1, 1.0, True, False, None, ["1"], {"value": "1"}]


def _workflow() -> dict:
    return yaml.load(
        (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8"),
        Loader=contract.UniqueKeyLoader,
    )


def _compile_step(workflow: dict) -> dict:
    return next(step for step in workflow["jobs"]["validation_matrix"]["steps"]
                if step.get("name") == "Compile Python sources")


def _environment(workflow: dict) -> dict[str, str]:
    environment = dict(os.environ)
    for name in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"):
        environment.pop(name, None)
    environment.update(workflow.get("env", {}))
    return environment


def _compile(root: Path, runner_temp: Path, workflow: dict) -> subprocess.CompletedProcess[str]:
    command = _compile_step(workflow)["run"].replace("${{ runner.temp }}", runner_temp.as_posix())
    arguments = shlex.split(command)
    assert arguments[0] == "python", "bind only the canonical Python executable"
    return subprocess.run([sys.executable, *arguments[1:]], cwd=root,
                          env=_environment(workflow), capture_output=True, text=True, timeout=30)


def test_compilation_and_child_imports_keep_certified_checkout_source_only(tmp_path: Path) -> None:
    root = tmp_path / "certified source fixture"
    expected = _repository(root, {
        "scripts/__init__.py": "",
        "scripts/certified_module.py": "def answer():\n    return sum({19, 23})\n",
        "main.py": "MAIN = 1\n", "sensitive_data.py": "VALUE = 1\n",
        **{f"{name}/{name}_probe.py": "VALUE = 1\n" for name in (
            "runtime", "seoctl", "integrations", "adapters", "contracts", "security",
        )},
        "unlisted_nested/unlisted_probe.py": "VALUE = 1\n",
    })
    runner_temp = tmp_path / "external compiler cache with spaces"
    runner_temp.mkdir()
    workflow = _workflow()
    compiled = _compile(root, runner_temp, workflow)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    assert not list(root.rglob("*.pyc")), "canonical compileall polluted the certified checkout"
    assert list(runner_temp.rglob("*.pyc")), "compileall must still produce real external artifacts"
    artifact_names = {path.name.split(".")[0] for path in runner_temp.rglob("*.pyc")}
    assert {"main", "sensitive_data", "__init__", "certified_module", "unlisted_probe",
            "runtime_probe", "seoctl_probe", "integrations_probe", "adapters_probe",
            "contracts_probe", "security_probe"} <= artifact_names
    child_code = (
        "import json, os, sys; from scripts.certified_module import answer; "
        "print(json.dumps({'value':answer(), 'policy':os.environ.get('PYTHONDONTWRITEBYTECODE'), "
        "'dont_write':sys.dont_write_bytecode, 'cache_prefix':sys.pycache_prefix}))"
    )
    parent_code = (
        "import json, os, subprocess, sys; from scripts.certified_module import answer; "
        f"child=subprocess.run([sys.executable, '-c', {child_code!r}], check=True, "
        "capture_output=True, text=True); "
        "print(json.dumps({'value':answer(), 'policy':os.environ.get('PYTHONDONTWRITEBYTECODE'), "
        "'dont_write':sys.dont_write_bytecode, 'cache_prefix':sys.pycache_prefix, 'child':json.loads(child.stdout)}))"
    )
    imported = subprocess.run([sys.executable, "-c", parent_code], cwd=root,
                              env=_environment(workflow), capture_output=True, text=True, timeout=30)
    assert imported.returncode == 0, imported.stdout + imported.stderr
    observed = json.loads(imported.stdout)
    ordinary = {"value": 42, "policy": "1", "dont_write": True, "cache_prefix": None}
    assert observed == {**ordinary, "child": ordinary}
    assert not list(root.rglob("*.pyc")), "ordinary child imports must inherit the no-write policy"
    assert validate(expected, root, proof_mode="candidate") == []
    assert validate(expected, root, proof_mode="restored-baseline") == []


@pytest.mark.parametrize("filename", ["validate.yml", "release.yml", "maintenance.yml", "autonomous-seo-certification.yml"])
def test_all_python_workflows_inherit_only_the_exact_source_only_literal(filename: str) -> None:
    workflow = yaml.load((ROOT / ".github/workflows" / filename).read_text(encoding="utf-8"),
                         Loader=contract.UniqueKeyLoader)
    assert workflow["env"] == {NO_BYTECODE: "1"}


def test_global_literal_allowance_does_not_allow_arbitrary_python_environment() -> None:
    payload = {"env": {NO_BYTECODE: "1"}, "jobs": {"fixture": {"steps": []}}}
    assert contract._jobs(yaml.safe_dump(payload))[1] == []
    for name in ("PYTHONPATH", "PYTHONPYCACHEPREFIX", "PYTHONHOME", "PYTHONOPTIMIZE"):
        payload["env"] = {NO_BYTECODE: "1", name: "synthetic-placeholder"}
        assert any(name in error for error in contract._jobs(yaml.safe_dump(payload))[1])


@pytest.mark.parametrize("value", BAD_VALUES)
def test_global_no_bytecode_rejects_wrong_values_and_types(value) -> None:
    payload = {"env": {NO_BYTECODE: value}, "jobs": {"fixture": {"steps": []}}}
    assert any(NO_BYTECODE in error for error in contract._jobs(yaml.safe_dump(payload))[1])


@pytest.mark.parametrize("name", ["pythondontwritebytecode", "PythonDontWriteBytecode", "PYTHONdontwritebytecode"])
def test_global_no_bytecode_rejects_case_variants(name: str) -> None:
    payload = {"env": {name: "1"}, "jobs": {"fixture": {"steps": []}}}
    assert any(name in error for error in contract._jobs(yaml.safe_dump(payload))[1])


@pytest.mark.parametrize("scope", ["job", "step", "container"])
@pytest.mark.parametrize("value", ["1", *BAD_VALUES])
def test_canonical_jobs_never_allow_local_python_overrides(scope: str, value) -> None:
    for name in (*contract.VALIDATE_JOBS, "release"):
        job = {"runs-on": "ubuntu-latest", "steps": [{"run": "python -c 'print(1)'"}]}
        carrier = job if scope == "job" else job["steps"][0] if scope == "step" else {}
        carrier["env"] = {NO_BYTECODE: value}
        if scope == "container":
            job["container"] = carrier
        errors = contract._job_source_profile_errors(name, job)
        assert any("execution-altering" in error and NO_BYTECODE in error for error in errors), (scope, name, value)


def test_current_workflows_bind_the_exact_global_policy_and_compile_command() -> None:
    validation = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert _compile_step(_workflow()) == {"name": "Compile Python sources", "run": COMPILE_COMMAND}
    assert contract.workflow_errors(validation, 78.0, release) == []


@pytest.mark.parametrize("metadata", [
    {"if": False}, {"continue-on-error": True}, {"shell": "bash"},
    {"working-directory": "unrelated"}, {"timeout-minutes": 999}, {"id": "unapproved-compile"},
    {"env": {NO_BYTECODE: "1"}},
])
def test_compile_boundary_rejects_unapproved_metadata(metadata: dict) -> None:
    workflow = _workflow()
    _compile_step(workflow).update(metadata)
    errors = contract.workflow_errors(yaml.safe_dump(workflow, sort_keys=False), 78.0)
    assert errors, metadata


@pytest.mark.parametrize("command", [
    "python -m compileall -q .", COMPILE_COMMAND.replace(" -q .", " -q main.py"),
    COMPILE_COMMAND.replace("wcseo-compile-cache", "unapproved-cache"),
    COMPILE_COMMAND + " || true", COMPILE_COMMAND.replace("python -X", "python -B -X"),
    COMPILE_COMMAND.replace(" -q .", " -q . --invalidation-mode=unchecked-hash"),
])
def test_compile_boundary_rejects_changed_target_flags_output_or_masking(command: str) -> None:
    workflow = _workflow()
    _compile_step(workflow)["run"] = command
    assert any("finite contract" in error for error in contract.workflow_errors(yaml.safe_dump(workflow, sort_keys=False), 78.0))


@pytest.mark.parametrize("mutation", ["missing", "renamed", "extra"])
def test_finite_workflow_contract_binds_global_environment_exactly(mutation: str) -> None:
    for filename in ("validate.yml", "release.yml"):
        workflow = yaml.load((ROOT / ".github/workflows" / filename).read_text(encoding="utf-8"), Loader=contract.UniqueKeyLoader)
        if mutation == "missing":
            workflow.pop("env")
        elif mutation == "renamed":
            workflow["env"] = {NO_BYTECODE.lower(): "1"}
        else:
            workflow["env"]["EXTRA_NOT_REVIEWED"] = "1"
        fingerprint = contract.WORKFLOW_CONTRACT_SHA if filename == "validate.yml" else contract.RELEASE_CONTRACT_SHA
        assert contract._workflow_contract_errors(yaml.safe_dump(workflow, sort_keys=False), fingerprint)


@pytest.mark.parametrize("relative", ["main.py", "runtime/broken.py", "unlisted_nested/broken.py"])
def test_external_compilation_still_rejects_syntax_errors(tmp_path: Path, relative: str) -> None:
    root = tmp_path / "invalid source fixture"
    _repository(root, {relative: "def broken(:\n    pass\n"})
    runner_temp = tmp_path / "external syntax error cache with spaces"
    runner_temp.mkdir()
    compiled = _compile(root, runner_temp, _workflow())
    assert compiled.returncode != 0
    assert "SyntaxError" in compiled.stdout + compiled.stderr
    assert not list(root.rglob("*.pyc"))
