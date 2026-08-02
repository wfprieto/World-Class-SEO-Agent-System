"""Structural, fail-closed validation for mandatory quality workflow steps."""

from __future__ import annotations

import hashlib
import re
from typing import Any

import yaml

COVERAGE_TARGETS = ("runtime", "seoctl", "integrations", "adapters")
CANDIDATE_REF = "${{ github.event.pull_request.head.sha || github.sha }}"
RELEASE_REF = "${{ github.sha }}"
DANGEROUS_ENV_EXACT = {
    "BASH_ENV",
    "COMSPEC",
    "ENV",
    "GITHUB_ENV", "GITHUB_PATH", "GITHUB_WORKSPACE", "HOME",
    "IFS",
    "LD_PRELOAD",
    "NODE_OPTIONS",
    "PATH",
    "PATHEXT", "PSMODULEPATH", "RUNNER_TEMP", "RUNNER_TOOL_CACHE",
    "SHELL",
    "SHELLOPTS",
    "VIRTUAL_ENV", "USERPROFILE",
}
DANGEROUS_ENV_PREFIXES = ("COVERAGE_", "DYLD_", "GIT_", "PIP_", "PYTEST_", "PYTHON")
APPROVED_RUNNERS = {"ubuntu-latest", "windows-latest"}
MATRIX_RUNNER = "${{ matrix.os }}"
TRUSTED_PYTHON_OUTPUT = "${{ steps.trusted_python.outputs.path }}"
SOURCE_GATE_PREFIX = f"$env:PATH = Split-Path -Parent '${{{{ steps.trusted_python.outputs.git_path }}}}'; & '{TRUSTED_PYTHON_OUTPUT}' -I -E scripts/validate_source_integrity.py --expected-sha "
TRUSTED_PYTHON_COMMAND = (
    "$resolved = Get-Command python -CommandType Application | Select-Object -First 1 -ExpandProperty Source\n$git = Get-Command git -CommandType Application | Select-Object -First 1 -ExpandProperty Source\n"
    "if (-not [IO.Path]::IsPathFullyQualified($resolved) -or -not (Test-Path -LiteralPath $resolved -PathType Leaf)) { throw 'trusted Python path is not one absolute file' }\nif (-not [IO.Path]::IsPathFullyQualified($git) -or -not (Test-Path -LiteralPath $git -PathType Leaf)) { throw 'trusted Git path is not one absolute file' }\n"
    '"path=$resolved" >> $env:GITHUB_OUTPUT\n"git_path=$git" >> $env:GITHUB_OUTPUT'
)
TRUSTED_PYTHON_STEP = {
    "name": "Capture trusted Python interpreter",
    "id": "trusted_python",
    "shell": "pwsh",
    "run": TRUSTED_PYTHON_COMMAND,
}
VALIDATE_JOBS = (
    "validation_matrix", "provider_authentication", "validate", "quality_security_release",
    "clean_wheel_install", "phase0_rollback_certification",
    "phase_rollback_certification", "certification_status",
)
CHECKOUT_JOBS = set(VALIDATE_JOBS) - {"validate", "certification_status"}
ACTION_SHAS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    "actions/download-artifact": "37930b1c2abaa49bbe596cd826c3c89aef350131",
    "actions/attest": "508db95dd578ae2727ebd6217d5ba78e4fbda05d",
}
PHASE0_BASELINE = "e8c37abb5e939d4433e42ea8a02af63549ca0010"
PHASE0_ROLLBACK_SHA = "4f92ea1fba3e6d97dc1239a2e8cd984eea097a66ba04c6ffa1cfd37d263415ca"
BASELINE_PROOF_PREFIX = (
    "$expectedCommit = ",
    "$expectedTree = (& /usr/bin/git rev-parse \"$expectedCommit`^{tree}\")",
    "$actualTree = (& /usr/bin/git write-tree)",
    "if ($actualTree -ne $expectedTree) { throw 'restored index tree mismatch' }",
    "& /usr/bin/git diff --quiet --no-ext-diff --exit-code",
    "if ($LASTEXITCODE) { throw 'restored worktree drift' }",
    "$flags = @(& /usr/bin/git ls-files -v | Where-Object { $_ -cnotmatch '^H ' })",
    "if ($flags.Count) { throw 'tracked index flags can conceal restored-tree drift' }",
)
PHASE0_BASELINE_PROOF = "\n".join((f"$expectedCommit = '{PHASE0_BASELINE}'", *BASELINE_PROOF_PREFIX[1:]))
PHASE_BASELINE_PROOF = "\n".join((
    "$expectedCommit = (& '${{ steps.trusted_python.outputs.path }}' -I -E -c "
    "\"import json; print(json.load(open('phase-rollback-receipt.json', encoding='utf-8'))['baseline_commit'])\")",
    *BASELINE_PROOF_PREFIX[1:],
))
class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate YAML key: {key}", key_node.start_mark
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping

def _jobs(workflow: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    try:
        payload = yaml.load(workflow, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        return {}, [f"CI workflow YAML is invalid: {exc}"]
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), dict):
        return {}, ["CI workflow must contain a jobs mapping"]
    defaults = payload.get("defaults", {})
    run_defaults = defaults.get("run", {}) if isinstance(defaults, dict) else {}
    errors = []
    if isinstance(run_defaults, dict) and set(run_defaults) & {"shell", "working-directory"}:
        errors.append("CI workflow must not inherit shell or working-directory defaults")
    dangerous_env = _dangerous_env_keys(payload)
    if dangerous_env:
        errors.append(
            "CI workflow must not inherit execution-altering environment variables: "
            + ", ".join(dangerous_env)
        )
    jobs = {str(name): job for name, job in payload["jobs"].items() if isinstance(job, dict)}
    return jobs, errors

def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    value = job.get("steps", [])
    return [step for step in value if isinstance(step, dict)] if isinstance(value, list) else []

def _dangerous_env_keys(owner: dict[str, Any]) -> list[str]:
    env = owner.get("env", {})
    if not isinstance(env, dict):
        return ["<invalid-env-mapping>"] if env is not None else []
    dangerous = []
    for key in env:
        normalized = str(key).upper()
        if normalized in DANGEROUS_ENV_EXACT or normalized.startswith(
            DANGEROUS_ENV_PREFIXES
        ):
            dangerous.append(str(key))
    return sorted(dangerous, key=str.casefold)

def _dangerous_container_env_keys(job: dict[str, Any]) -> list[str]:
    container = job.get("container", {})
    return _dangerous_env_keys(container) if isinstance(container, dict) else []

def _source_gate_command(expected_ref: str) -> str:
    return SOURCE_GATE_PREFIX + expected_ref

def _is_source_gate(step: dict[str, Any], expected_ref: str) -> bool:
    return step == {
        "name": "Prove exact source integrity", "shell": "pwsh",
        "run": _source_gate_command(expected_ref),
    }

def _matrix_errors(name: str, job: dict[str, Any]) -> list[str]:
    expected = {
        "validation_matrix": {"fail-fast": False, "matrix": {
            "os": ["windows-latest", "ubuntu-latest"],
            "python-version": ["3.11", "3.12", "3.13"],
        }},
        "clean_wheel_install": {"fail-fast": False, "matrix": {
            "os": ["windows-latest", "ubuntu-latest"],
        }},
    }
    wanted = expected.get(name)
    if wanted is None:
        return [f"canonical job {name} must not define a strategy"] if "strategy" in job else []
    errors = [] if job.get("strategy") == wanted else [f"canonical job {name} matrix must equal the approved expansion"]
    if job.get("runs-on") != MATRIX_RUNNER:
        errors.append(f"canonical job {name} must use only its exact matrix runner")
    return errors

def _job_source_profile_errors(name: str, job: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors += _matrix_errors(name, job)
    if name not in {"validation_matrix", "clean_wheel_install"} and job.get("runs-on") != "ubuntu-latest":
        errors.append(f"canonical job {name} must use ubuntu-latest")
    if "container" in job or "services" in job:
        errors.append(f"canonical job {name} must not use containers or services")
    dangerous_env = _dangerous_env_keys(job) + _dangerous_container_env_keys(job)
    dangerous_env += [key for step in _steps(job) for key in _dangerous_env_keys(step)]
    if dangerous_env:
        errors.append(
            f"canonical job {name} has execution-altering environment variables: "
            + ", ".join(dangerous_env)
        )
    return errors

def _canonical_job_errors(
    jobs: dict[str, dict[str, Any]], required: tuple[str, ...]
) -> list[str]:
    errors = [f"canonical certification job is missing: {name}" for name in required if name not in jobs]
    for name in required:
        if name in jobs:
            errors += _job_source_profile_errors(name, jobs[name])
    return errors

def _is_evidence_boundary(step: dict[str, Any]) -> bool:
    return isinstance(step.get("run"), str) or isinstance(step.get("uses"), str)

def _poisons_command_channel(step: dict[str, Any]) -> bool:
    command = step.get("run")
    normalized = re.sub(r"[^a-z0-9]", "", command.casefold()) if isinstance(command, str) else ""
    return "github" in normalized and ("env" in normalized or "path" in normalized)

def _baseline_gate(name: str) -> dict[str, Any] | None:
    commands = {
        "phase0_rollback_certification": PHASE0_BASELINE_PROOF,
        "phase_rollback_certification": PHASE_BASELINE_PROOF,
    }
    command = commands.get(name)
    return None if command is None else {
        "name": "Prove exact restored baseline", "shell": "/usr/bin/pwsh -command \". '{0}'\"",
        "run": command,
    }

def _replaces_candidate_source(name: str, step: dict[str, Any]) -> bool:
    if name == "phase_rollback_certification":
        return step == {
            "name": "Rehearse exact-head current-phase rollback",
            "run": "python scripts/rehearse_phase_rollback.py --receipt phase-rollback-receipt.json",
        }
    command = step.get("run")
    return (
        name == "phase0_rollback_certification"
        and set(step) == {"name", "shell", "run"}
        and step.get("name") == "Rehearse exact-head Phase 0 rollback"
        and step.get("shell") == "bash"
        and isinstance(command, str)
        and hashlib.sha256(command.encode()).hexdigest() == PHASE0_ROLLBACK_SHA
    )

def _ordered_source_errors(name: str, steps: list[dict[str, Any]], expected_ref: str) -> list[str]:
    errors: list[str] = []
    baseline = False
    for index, step in enumerate(steps):
        source_gate = _is_source_gate(step, expected_ref)
        restored_gate = step == _baseline_gate(name)
        bootstrap = step == TRUSTED_PYTHON_STEP or index < 2
        if not (source_gate or restored_gate or bootstrap) and _poisons_command_channel(step):
            errors.append("workflow commands must not poison GITHUB_ENV or GITHUB_PATH")
        previous = steps[index - 1] if index else {}
        prior_proof = previous == _baseline_gate(name) if baseline else _is_source_gate(previous, expected_ref)
        if _is_evidence_boundary(step) and not (source_gate or restored_gate or bootstrap) and not prior_proof:
            errors.append(
                f"canonical job {name} boundary lacks its fresh adjacent source proof"
            )
        baseline = baseline or _replaces_candidate_source(name, step)
    return errors

def _source_integrity_errors(
    jobs: dict[str, dict[str, Any]], expected_ref: str, names: set[str]
) -> list[str]:
    errors: list[str] = []
    for name in names:
        if name not in jobs:
            continue
        steps = _steps(jobs[name])
        if len(steps) < 4 or not _is_checkout(steps[0]) or not _is_setup_python(steps[1]) or steps[2] != TRUSTED_PYTHON_STEP or not _is_source_gate(steps[3], expected_ref):
            errors.append(f"canonical job {name} must start checkout, setup-python, trusted interpreter, and source proof")
        expected_python = "${{ matrix.python-version }}" if name == "validation_matrix" else "3.13"
        if len(steps) < 2 or steps[1].get("with") != {"python-version": expected_python}:
            errors.append(f"canonical job {name} setup-python profile must remain exact")
        errors += _ordered_source_errors(name, steps, expected_ref)
    return errors

def _is_checkout(step: dict[str, Any]) -> bool:
    action = step.get("uses")
    return isinstance(action, str) and action.casefold().startswith("actions/checkout@")

def _is_setup_python(step: dict[str, Any]) -> bool:
    action = step.get("uses")
    return isinstance(action, str) and action.casefold().startswith("actions/setup-python@")

def _action_errors(jobs: dict[str, dict[str, Any]], names: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    expected = {
        "validation_matrix": ["actions/checkout", "actions/setup-python", "actions/upload-artifact", "actions/upload-artifact"],
        "provider_authentication": ["actions/checkout", "actions/setup-python"],
        "quality_security_release": ["actions/checkout", "actions/setup-python", "actions/upload-artifact"],
        "clean_wheel_install": ["actions/checkout", "actions/setup-python", "actions/download-artifact"],
        "phase0_rollback_certification": ["actions/checkout", "actions/setup-python", "actions/upload-artifact"],
        "phase_rollback_certification": ["actions/checkout", "actions/setup-python", "actions/upload-artifact"],
        "validate": [], "certification_status": [],
        "release": ["actions/checkout", "actions/setup-python", "actions/attest", "actions/attest"],
    }
    for name in names:
        identities: list[str] = []
        for step in _steps(jobs.get(name, {})):
            action = step.get("uses")
            if not isinstance(action, str):
                continue
            identity, separator, reference = action.partition("@")
            identities.append(identity)
            if not separator or ACTION_SHAS.get(identity) != reference:
                errors.append(f"canonical job {name} uses an unapproved or mutable action")
        if identities != expected[name]:
            errors.append(f"canonical job {name} action sequence must remain exact")
    return errors

def _checkout_step_errors(step: dict[str, Any], expected_ref: str) -> list[str]:
    errors: list[str] = []
    reference = str(step["uses"]).split("@", 1)[1]
    settings = step.get("with", {})
    depth = settings.get("fetch-depth") if isinstance(settings, dict) else None
    credentials = settings.get("persist-credentials") if isinstance(settings, dict) else None
    candidate_ref = settings.get("ref") if isinstance(settings, dict) else None
    if not str(step["uses"]).startswith("actions/checkout@"):
        errors.append("every checkout step must use canonical lowercase actions/checkout identity")
    if not re.fullmatch(r"[0-9a-f]{40}", reference):
        errors.append("every actions/checkout step must use an immutable 40-character SHA")
    if not (
        depth == "0"
        or (isinstance(depth, int) and not isinstance(depth, bool) and depth == 0)
    ):
        errors.append("every actions/checkout step must set fetch-depth: 0")
    if credentials not in {False, "false"}:
        errors.append("every actions/checkout step must set persist-credentials: false")
    if candidate_ref != expected_ref:
        errors.append("every actions/checkout step must check out the exact event commit")
    if not isinstance(settings, dict) or set(settings) != {
        "fetch-depth",
        "persist-credentials",
        "ref",
    }:
        errors.append("actions/checkout accepts only canonical source-integrity settings")
    return errors

def _checkout_errors(
    jobs: dict[str, dict[str, Any]], expected_ref: str, names: set[str]
) -> list[str]:
    errors: list[str] = []
    for name in names:
        checkouts = [step for step in _steps(jobs.get(name, {})) if _is_checkout(step)]
        if len(checkouts) != 1:
            errors.append(f"canonical job {name} must contain exactly one checkout")
        for step in checkouts:
            errors.extend(_checkout_step_errors(step, expected_ref))
    return errors

def _is_exact_step(step: dict[str, Any], command: str) -> bool:
    return set(step) <= {"name", "run"} and step.get("run") == command

def _has_run_defaults(owner: dict[str, Any]) -> bool:
    defaults = owner.get("defaults", {})
    run_defaults = defaults.get("run", {}) if isinstance(defaults, dict) else {}
    return isinstance(run_defaults, dict) and bool(
        set(run_defaults) & {"shell", "working-directory"}
    )

def _exact_locations(jobs: list[dict[str, Any]], command: str) -> list[tuple[int, int]]:
    return [
        (job_index, step_index)
        for job_index, job in enumerate(jobs)
        for step_index, step in enumerate(_steps(job))
        if _is_exact_step(step, command)
    ]

def _quality_step_errors(
    jobs: list[dict[str, Any]], coverage: str, risk: str
) -> list[str]:
    errors: list[str] = []
    coverage_at = _exact_locations(jobs, coverage)
    risk_at = _exact_locations(jobs, risk)
    if len(coverage_at) != 1:
        errors.append("CI coverage command must be one exact dedicated unmasked step")
    if len(risk_at) != 1:
        errors.append("CI risk coverage command must be one exact dedicated unmasked step")
    if len(coverage_at) == len(risk_at) == 1 and not (
        coverage_at[0][0] == risk_at[0][0] and coverage_at[0][1] < risk_at[0][1]
    ):
        errors.append("CI coverage must precede risk validation in the same job")
    if coverage_at and any(key in jobs[coverage_at[0][0]] for key in ("if", "continue-on-error")):
        errors.append("CI quality job must not be conditional or continue on error")
    if coverage_at and _has_run_defaults(jobs[coverage_at[0][0]]):
        errors.append("CI quality job must not inherit shell or working-directory defaults")
    if coverage_at:
        quality_job = jobs[coverage_at[0][0]]
        dangerous_env = _dangerous_env_keys(quality_job)
        if dangerous_env:
            errors.append(
                "CI quality job must not inherit execution-altering environment variables: "
                + ", ".join(dangerous_env)
            )
        if "container" in quality_job:
            errors.append("CI quality job must not use a container")
    return errors

def workflow_errors(
    workflow: str, coverage_floor: float, release_workflow: str | None = None
) -> list[str]:
    """Reject shallow checkout and any masked or weakened quality command."""
    coverage = (
        "pytest -q "
        + " ".join(f"--cov={target}" for target in COVERAGE_TARGETS)
        + " --cov-report=term-missing --cov-report=xml:outputs/coverage.xml"
        + " --cov-report=json:outputs/coverage.json "
        + f"--cov-fail-under={coverage_floor:g} --junitxml=outputs/pytest-quality.xml"
    )
    risk = "python scripts/validate_risk_coverage.py outputs/coverage.json"
    job_map, errors = _jobs(workflow)
    errors += _canonical_job_errors(job_map, VALIDATE_JOBS)
    errors += _action_errors(job_map, VALIDATE_JOBS)
    errors += _checkout_errors(job_map, CANDIDATE_REF, CHECKOUT_JOBS)
    errors += _source_integrity_errors(job_map, CANDIDATE_REF, CHECKOUT_JOBS)
    errors += _quality_step_errors(list(job_map.values()), coverage, risk)
    if release_workflow is not None:
        release_jobs, release_errors = _jobs(release_workflow)
        errors += release_errors
        errors += _canonical_job_errors(release_jobs, ("release",))
        errors += _action_errors(release_jobs, ("release",))
        errors += _checkout_errors(release_jobs, RELEASE_REF, {"release"})
        errors += _source_integrity_errors(release_jobs, RELEASE_REF, {"release"})
    return errors
