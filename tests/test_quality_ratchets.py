from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts import validate_quality_ratchets as ratchets
from scripts.validate_quality_ratchets import (
    FILE_DEFAULTS,
    FILE_METRICS,
    FUNCTION_DEFAULTS,
    FUNCTION_METRICS,
    MINIMUM_CRITICAL_COVERAGE,
    MINIMUM_REPOSITORY_COVERAGE,
    PACKAGES,
    ROOT,
    RUFF_RULES,
    _contract_digest,
    _monotonic_contract_errors,
    _repository_setting_errors,
    _ruff_counts,
    _workflow_errors,
    main,
    measure,
    tightened_contract,
    validate,
)
from scripts.workflow_quality_contract import TRUSTED_PYTHON_COMMAND


def _baseline(tmp_path: Path, sources: dict[str, str] | None = None) -> Path:
    for package in ("runtime", "adapters", "integrations", "seoctl", "scripts"):
        package_path = tmp_path / package
        package_path.mkdir(parents=True)
        (package_path / "__init__.py").write_text("", encoding="utf-8")
    for relative, content in (sources or {}).items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    files, functions = measure(tmp_path)
    def exceptions(measurements, defaults, pairs):
        return {
            key: {
                **{limit: metrics[metric] for metric, limit in pairs},
                "owner": "Quality owner",
                "rationale": "Frozen P3 legacy ceiling; increases fail and reductions are encouraged.",
                "removal_phase": "P7",
            }
            for key, metrics in measurements.items()
            if any(metrics[metric] > defaults[limit] for metric, limit in pairs)
        }
    contract = {
        "schema_version": "1.0.0",
        "packages": list(PACKAGES),
        "file_defaults": dict(FILE_DEFAULTS),
        "function_defaults": dict(FUNCTION_DEFAULTS),
        "file_exceptions": exceptions(files, FILE_DEFAULTS, FILE_METRICS),
        "function_exceptions": exceptions(functions, FUNCTION_DEFAULTS, FUNCTION_METRICS),
        "ruff": {
            "rules": list(RUFF_RULES),
            "violation_counts": dict(sorted(_ruff_counts(tmp_path).items())),
        },
        "coverage": {
            "repository_floor": MINIMUM_REPOSITORY_COVERAGE,
            "critical_file_floors": dict(MINIMUM_CRITICAL_COVERAGE),
        },
    }
    contract_path = tmp_path / "governance" / "code-quality-ratchet.json"
    contract_path.parent.mkdir(parents=True)
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    return contract_path


def test_canonical_quality_ratchet_passes() -> None:
    assert validate() == []


def test_new_complex_or_oversized_function_fails(tmp_path: Path) -> None:
    contract_path = _baseline(tmp_path)
    branches = "\n".join(f"    if value == {index}: value += 1" for index in range(20))
    padding = "\n".join("    value += 1" for _ in range(80))
    (tmp_path / "runtime" / "new_debt.py").write_text(
        f"def new_debt(value):\n{branches}\n{padding}\n    return value\n",
        encoding="utf-8",
    )
    errors = validate(tmp_path, contract_path, enforce_repository_settings=False)
    assert any("runtime.new_debt::new_debt span" in error for error in errors)
    assert any("runtime.new_debt::new_debt complexity" in error for error in errors)
    assert any("runtime.new_debt::new_debt missing_annotations" in error for error in errors)


def test_grandfathered_complexity_increase_fails(tmp_path: Path) -> None:
    source = "def legacy(value):\n" + "\n".join(
        f"    if value == {index}: value += 1" for index in range(16)
    ) + "\n    return value\n"
    contract_path = _baseline(tmp_path, {"runtime/legacy.py": source})
    (tmp_path / "runtime" / "legacy.py").write_text(
        source.replace("    return value", "    if value == 99: value += 1\n    return value"),
        encoding="utf-8",
    )
    errors = validate(tmp_path, contract_path, enforce_repository_settings=False)
    assert any("runtime.legacy::legacy complexity" in error for error in errors)


def test_new_ruff_debt_fails_against_exact_fingerprint_baseline(tmp_path: Path) -> None:
    contract_path = _baseline(tmp_path)
    (tmp_path / "runtime" / "lint_debt.py").write_text("import os\n", encoding="utf-8")
    errors = validate(tmp_path, contract_path, enforce_repository_settings=False)
    assert any("new Ruff debt:" in error and "F401" in error for error in errors)


def test_unsafe_or_unknown_baseline_entries_fail(tmp_path: Path) -> None:
    contract_path = _baseline(tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["file_exceptions"]["../escape.py"] = {
        "max_lines": 999,
        "max_complexity_total": 999,
        "max_missing_annotations": 999,
        "owner": "Quality owner",
        "rationale": "A traversal baseline must never be accepted by the quality validator.",
        "removal_phase": "P7",
    }
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    errors = validate(tmp_path, contract_path, enforce_repository_settings=False)
    assert "unsafe quality file exception path: ../escape.py" in errors
    assert "quality file exception references missing file: ../escape.py" in errors


def test_deleted_public_annotation_is_detected(tmp_path: Path) -> None:
    source = "def boundary(value: str) -> str:\n    return value\n"
    contract_path = _baseline(tmp_path, {"runtime/boundary.py": source})
    (tmp_path / "runtime" / "boundary.py").write_text(
        "def boundary(value):\n    return value\n", encoding="utf-8"
    )
    errors = validate(tmp_path, contract_path, enforce_repository_settings=False)
    assert any("runtime.boundary::boundary missing_annotations" in error for error in errors)


def test_repository_settings_cannot_weaken_ruff_coverage_or_ci(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    contract = json.loads(
        (ROOT / "governance" / "code-quality-ratchet.json").read_text(encoding="utf-8")
    )
    (tmp_path / "pyproject.toml").write_text(
        pyproject.replace('select = ["E4", "E7", "E9", "F", "I", "B", "UP", "C4", "SIM", "C90"]', 'select = ["E9"]')
        .replace("fail_under = 78", "fail_under = 77"),
        encoding="utf-8",
    )
    (tmp_path / ".github" / "workflows" / "validate.yml").write_text(
        workflow.replace("python scripts/validate_architecture_contract.py", "python -m compileall runtime"),
        encoding="utf-8",
    )
    (tmp_path / ".github" / "workflows" / "release.yml").write_text(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    errors = _repository_setting_errors(tmp_path, contract)
    assert "pyproject Ruff profile must equal the canonical P3 rule profile" in errors
    assert "repository coverage floor is weaker than the quality contract" in errors
    assert any("validate_architecture_contract.py" in error for error in errors)


def test_canonical_defaults_and_coverage_minima_are_immutable(tmp_path: Path) -> None:
    contract_path = _baseline(tmp_path)
    previous = json.loads(contract_path.read_text(encoding="utf-8"))
    weakened = copy.deepcopy(previous)
    weakened["file_defaults"]["max_lines"] = 999
    weakened["function_defaults"]["max_complexity"] = 99
    weakened["coverage"]["repository_floor"] = 77
    critical = next(iter(MINIMUM_CRITICAL_COVERAGE))
    weakened["coverage"]["critical_file_floors"][critical] -= 1
    contract_path.write_text(json.dumps(weakened), encoding="utf-8")

    errors = validate(
        tmp_path, contract_path, enforce_repository_settings=False,
        previous_contract=previous,
    )
    assert "file defaults must equal the immutable canonical new-code policy" in errors
    assert "function defaults must equal the immutable canonical new-code policy" in errors
    assert "repository coverage floor is below the immutable canonical minimum" in errors
    assert any("critical coverage floor is below" in error for error in errors)


def test_same_commit_regeneration_cannot_raise_legacy_ceiling(tmp_path: Path) -> None:
    source = "def legacy(value):\n" + "\n".join(
        f"    if value == {index}: value += 1" for index in range(16)
    ) + "\n    return value\n"
    contract_path = _baseline(tmp_path, {"runtime/legacy.py": source})
    previous = json.loads(contract_path.read_text(encoding="utf-8"))
    changed = source.replace("    return value", "    if value == 99: value += 1\n    return value")
    (tmp_path / "runtime/legacy.py").write_text(changed, encoding="utf-8")
    current = copy.deepcopy(previous)
    current["function_exceptions"]["runtime.legacy::legacy"]["max_complexity"] += 1
    contract_path.write_text(json.dumps(current), encoding="utf-8")

    errors = validate(
        tmp_path, contract_path, enforce_repository_settings=False,
        previous_contract=previous,
    )
    assert "quality ratchet cannot raise runtime.legacy::legacy max_complexity" in errors


def test_reductions_require_and_receive_immediate_tightening(tmp_path: Path) -> None:
    source = "def legacy(value):\n" + "\n".join(
        "    value += 1" for _ in range(80)
    ) + "\n    return value\n"
    contract_path = _baseline(tmp_path, {"runtime/legacy.py": source})
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    (tmp_path / "runtime/legacy.py").write_text(
        source.replace("    value += 1\n", "", 1), encoding="utf-8"
    )
    assert any("stale quality function ceiling" in error for error in validate(
        tmp_path, contract_path, enforce_repository_settings=False
    ))
    tightened = tightened_contract(tmp_path, contract)
    assert not _monotonic_contract_errors(contract, tightened)
    contract_path.write_text(json.dumps(tightened), encoding="utf-8")
    assert validate(tmp_path, contract_path, enforce_repository_settings=False) == []


def test_safe_updater_rejects_new_debt_and_cli_requires_exact_approval(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    contract_path = _baseline(tmp_path)
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    (tmp_path / "runtime/new_debt.py").write_text("import os\n", encoding="utf-8")
    try:
        tightened_contract(tmp_path, contract)
    except ValueError as exc:
        assert "cannot baseline new Ruff debt" in str(exc)
    else:
        raise AssertionError("new Ruff debt was silently baselined")

    monkeypatch.setattr(sys, "argv", ["validate_quality_ratchets.py", "--write-baseline"])
    assert main() == 1
    output = json.loads(capsys.readouterr().out)
    assert output["current_contract_sha256"] == _contract_digest(
        json.loads((ROOT / "governance/code-quality-ratchet.json").read_text(encoding="utf-8"))
    )


def test_canonical_validation_fails_closed_without_prior_git_history(
    tmp_path: Path, monkeypatch
) -> None:
    contract_path = _baseline(tmp_path)
    monkeypatch.setattr(ratchets, "ROOT", tmp_path)
    monkeypatch.setattr(ratchets, "_previous_contract", lambda *_args: None)
    errors = ratchets.validate(
        tmp_path, contract_path, enforce_repository_settings=False
    )
    assert "quality ratchet prior contract Git history is unavailable" in errors


def test_checkout_steps_must_exist_be_pinned_and_fetch_full_history() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    assert _workflow_errors(workflow, 78.0) == []
    checkout = (
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7\n"
        "        with:\n"
        "          fetch-depth: 0\n"
        "          fetch-tags: true\n"
        "          persist-credentials: false\n"
        "          ref: ${{ github.event.pull_request.head.sha || github.sha }}\n"
    )
    no_checkout = workflow.replace(checkout, "", 1)
    assert any("exactly one checkout" in error for error in _workflow_errors(no_checkout, 78.0))
    unpinned = workflow.replace(
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/checkout@v7",
        1,
    )
    assert any("immutable 40-character SHA" in error for error in _workflow_errors(unpinned, 78.0))
    shallow = workflow.replace("fetch-depth: 0", "fetch-depth: 1", 1)
    assert any("fetch-depth: 0" in error for error in _workflow_errors(shallow, 78.0))
    quoted_shallow = workflow.replace(
        "uses: actions/checkout@", "uses: 'actions/checkout@", 1
    ).replace(" # v7", "' # v7", 1).replace(
        "fetch-depth: 0", "fetch-depth: 1", 1
    )
    assert any("fetch-depth: 0" in error for error in _workflow_errors(quoted_shallow, 78.0))
    duplicate = workflow.replace(
        "fetch-depth: 0", 'fetch-depth: 0\n          "fetch-depth": 1', 1
    )
    assert any("duplicate YAML key" in error for error in _workflow_errors(duplicate, 78.0))
    quoted_zero = workflow.replace("fetch-depth: 0", 'fetch-depth: "0"', 1)
    assert _workflow_errors(quoted_zero, 78.0) == []
    expression = workflow.replace("fetch-depth: 0", "fetch-depth: ${{ github.event.depth }}", 1)
    assert any("fetch-depth: 0" in error for error in _workflow_errors(expression, 78.0))
    case_variant = workflow.replace("actions/checkout@", "Actions/Checkout@", 1).replace(
        "fetch-depth: 0", "fetch-depth: 1", 1
    )
    assert any("fetch-depth: 0" in error for error in _workflow_errors(case_variant, 78.0))
    credentials = workflow.replace("persist-credentials: false", "persist-credentials: true", 1)
    assert any("persist-credentials" in error for error in _workflow_errors(credentials, 78.0))
    uppercase_unpinned = workflow.replace("actions/checkout@", "ACTIONS/CHECKOUT@", 1).replace(
        "3d3c42e5aac5ba805825da76410c181273ba90b1", "v7", 1
    )
    errors = _workflow_errors(uppercase_unpinned, 78.0)
    assert any("canonical lowercase" in error for error in errors)
    assert any("immutable 40-character SHA" in error for error in errors)
    missing_candidate = workflow.replace(
        "          ref: ${{ github.event.pull_request.head.sha || github.sha }}\n", "", 1
    )
    assert any(
        "exact event commit" in error
        for error in _workflow_errors(missing_candidate, 78.0)
    )
    branch_override = workflow.replace(
        "ref: ${{ github.event.pull_request.head.sha || github.sha }}", "ref: main", 1
    )
    assert any(
        "exact event commit" in error
        for error in _workflow_errors(branch_override, 78.0)
    )
    for override in ("repository: attacker/fork", "path: unrelated"):
        mutated = workflow.replace(
            "          fetch-depth: 0", f"          {override}\n          fetch-depth: 0", 1
        )
        assert any(
            "canonical source-integrity settings" in error
            for error in _workflow_errors(mutated, 78.0)
        )


def test_release_checkout_is_bound_to_tag_event_commit() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert _workflow_errors(workflow, 78.0, release) == []
    mutations = (
        release.replace("ref: ${{ github.sha }}", "ref: main", 1),
        release.replace("          ref: ${{ github.sha }}\n", "", 1),
        release.replace(
            "          fetch-depth: 0", "          path: release-src\n          fetch-depth: 0", 1
        ),
        release.replace(
            "          fetch-depth: 0",
            "          repository: attacker/fork\n          fetch-depth: 0",
            1,
        ),
    )
    for mutated in mutations:
        assert _workflow_errors(workflow, 78.0, mutated)
    gate = (
        "      - name: Prove exact source integrity\n"
        "        shell: pwsh\n"
        "        run: >-\n"
        "          $env:PATH = Split-Path -Parent '${{ steps.trusted_python.outputs.git_path }}';\n"
            "          $raw = & '${{ steps.trusted_python.outputs.path }}' -I -E -S "
            "scripts/validate_source_integrity.py --expected-sha ${{ github.sha }};\n"
            "          $exitCode = $LASTEXITCODE; $proof = $raw | ConvertFrom-Json;\n"
            "          if ($exitCode -or $proof.status -ne 'PASS' -or @($proof.errors).Count) "
            "{ throw 'source-integrity proof did not return structured PASS' }\n"
    )
    assert any(
        "fresh adjacent source proof" in error
        for error in _workflow_errors(workflow, 78.0, release.replace(gate, "", 1))
    )
    poisoned = release.replace(
        gate,
        gate
        + "      - name: Poison release PATH\n"
        + "        run: echo '/attacker/bin' >> $env:GITHUB_PATH\n",
        1,
    )
    assert any(
        "must not poison" in error
        for error in _workflow_errors(workflow, 78.0, poisoned)
    )
    containerized = release.replace(
        "  release:\n    permissions:\n      contents: write\n      id-token: write\n      attestations: write\n    runs-on: ubuntu-latest",
        "  release:\n    permissions:\n      contents: write\n      id-token: write\n      attestations: write\n    container: python:3.13\n    runs-on: ubuntu-latest",
        1,
    )
    assert any(
        "containers or services" in error
        for error in _workflow_errors(workflow, 78.0, containerized)
    )
    self_hosted = release.replace("runs-on: ubuntu-latest", "runs-on: self-hosted", 1)
    assert any(
        "release must use ubuntu-latest" in error
        for error in _workflow_errors(workflow, 78.0, self_hosted)
    )
    release_path_env = release.replace(
        "        env:\n          GH_TOKEN: ${{ github.token }}",
        "        env:\n          GH_TOKEN: ${{ github.token }}\n          pAtH: /attacker/bin",
        1,
    )
    assert any("pAtH" in error for error in _workflow_errors(workflow, 78.0, release_path_env))


def test_quality_job_rejects_execution_altering_inherited_environment() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    root_pytest_mask = "env:\n  PYTEST_ADDOPTS: --ignore=tests/test_architecture_contract.py\n\n"
    errors = _workflow_errors(root_pytest_mask + workflow, 78.0)
    assert any("PYTEST_ADDOPTS" in error for error in errors)
    job_pythonpath = workflow.replace(
        "  quality_security_release:\n    permissions:\n      contents: read\n    needs: validate",
        "  quality_security_release:\n    permissions:\n      contents: read\n    env:\n      PYTHONPATH: unrelated\n    needs: validate",
        1,
    )
    assert any("PYTHONPATH" in error for error in _workflow_errors(job_pythonpath, 78.0))
    unrelated_job_env = workflow.replace(
        "  provider_authentication:\n",
        "  provider_authentication:\n    env:\n      PROVIDER_TEST_LABEL: offline\n",
        1,
    )
    assert _workflow_errors(unrelated_job_env, 78.0) == []


def test_workflow_rejects_command_channel_poisoning_and_unbounded_execution() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    for key in ("github_env", "GitHub_Path", "Path"):
        poisoned = f"env:\n  {key}: attacker-controlled\n\n" + workflow
        assert _workflow_errors(poisoned, 78.0)

    gate = (
        "      - name: Prove exact source integrity\n"
        "        shell: pwsh\n"
        "        run: >-\n"
        "          $env:PATH = Split-Path -Parent '${{ steps.trusted_python.outputs.git_path }}';\n"
        "          $raw = & '${{ steps.trusted_python.outputs.path }}' -I -E -S "
        "scripts/validate_source_integrity.py --expected-sha "
        "${{ github.event.pull_request.head.sha || github.sha }};\n"
        "          $exitCode = $LASTEXITCODE; $proof = $raw | ConvertFrom-Json;\n"
        "          if ($exitCode -or $proof.status -ne 'PASS' -or @($proof.errors).Count) "
        "{ throw 'source-integrity proof did not return structured PASS' }\n"
    )
    poisoned_command = gate + (
        "      - name: Poison later commands\n"
        "        run: echo 'PYTEST_ADDOPTS=--ignore=tests/test_architecture_contract.py' >> $github_env\n"
    )
    mutated = workflow.replace(gate, poisoned_command, 1)
    assert any("must not poison" in error for error in _workflow_errors(mutated, 78.0))

    source_edit = gate + (
        "      - name: Alter tracked source\n"
        "        run: echo '# drift' >> scripts/validate_architecture_contract.py\n"
    )
    mutated = workflow.replace(gate, source_edit, 1)
    assert any("fresh adjacent source proof" in error for error in _workflow_errors(mutated, 78.0))

    quality_container = workflow.replace(
        "  quality_security_release:\n    permissions:\n      contents: read\n    needs: validate",
        "  quality_security_release:\n    permissions:\n      contents: read\n    container:\n      image: python:3.13\n      env:\n        PYTEST_ADDOPTS: --ignore=tests/test_architecture_contract.py\n    needs: validate",
        1,
    )
    errors = _workflow_errors(quality_container, 78.0)
    assert any("containers or services" in error for error in errors)
    assert any("PYTEST_ADDOPTS" in error for error in errors)
    services = workflow.replace(
        "  quality_security_release:\n    permissions:\n      contents: read\n    needs: validate",
        "  quality_security_release:\n    permissions:\n      contents: read\n    services:\n      helper:\n        image: attacker/image\n    needs: validate",
        1,
    )
    assert any("containers or services" in error for error in _workflow_errors(services, 78.0))
    self_hosted = workflow.replace(
        "  quality_security_release:\n    permissions:\n      contents: read\n    needs: validate\n    runs-on: ubuntu-latest",
        "  quality_security_release:\n    permissions:\n      contents: read\n    needs: validate\n    runs-on: [self-hosted, linux]",
        1,
    )
    assert any(
        "quality_security_release must use ubuntu-latest" in error
        for error in _workflow_errors(self_hosted, 78.0)
    )
    unbounded_matrix = workflow.replace(
        "os: [windows-latest, ubuntu-latest]",
        "os: [windows-latest, ubuntu-latest, self-hosted]",
        1,
    )
    assert _workflow_errors(unbounded_matrix, 78.0)
    harmless_metadata = workflow.replace(
        "  provider_authentication:\n",
        "  provider_authentication:\n    timeout-minutes: 15\n",
        1,
    )
    assert _workflow_errors(harmless_metadata, 78.0) == []


def test_every_repository_command_requires_fresh_adjacent_source_proof() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    gate = (
        "      - name: Prove exact source integrity\n"
        "        shell: pwsh\n"
        "        run: >-\n"
        "          $env:PATH = Split-Path -Parent '${{ steps.trusted_python.outputs.git_path }}';\n"
        "          $raw = & '${{ steps.trusted_python.outputs.path }}' -I -E -S "
        "scripts/validate_source_integrity.py --expected-sha "
        "${{ github.event.pull_request.head.sha || github.sha }};\n"
        "          $exitCode = $LASTEXITCODE; $proof = $raw | ConvertFrom-Json;\n"
        "          if ($exitCode -or $proof.status -ne 'PASS' -or @($proof.errors).Count) "
        "{ throw 'source-integrity proof did not return structured PASS' }\n"
    )
    removed = workflow.replace(gate, "", 1)
    assert any("fresh adjacent source proof" in error for error in _workflow_errors(removed, 78.0))
    stale = workflow.replace(
        gate,
        gate
        + "      - uses: actions/setup-node@8f4b1789f2552f8ff68f0f4206a5fc1f92b3f514\n",
        1,
    )
    assert any("fresh adjacent source proof" in error for error in _workflow_errors(stale, 78.0))


def test_every_named_certification_job_is_mandatory_and_profiled() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    names = (
        "validation_matrix", "provider_authentication", "validate",
        "quality_security_release", "clean_wheel_install",
        "phase0_rollback_certification", "phase_rollback_certification",
        "certification_status",
    )
    for name in names:
        renamed = workflow.replace(f"  {name}:\n", f"  removed_{name}:\n", 1)
        assert any(
            f"missing: {name}" in error for error in _workflow_errors(renamed, 78.0)
        )
    checkout_free_hijack = workflow.replace(
        "  validate:\n    name: validate\n    permissions:\n      contents: read\n    needs: [validation_matrix, provider_authentication]\n    if: always()\n    runs-on: ubuntu-latest",
        "  validate:\n    name: validate\n    permissions:\n      contents: read\n    needs: [validation_matrix, provider_authentication]\n    if: always()\n    runs-on: self-hosted",
        1,
    )
    assert any("validate must use ubuntu-latest" in error for error in _workflow_errors(checkout_free_hijack, 78.0))


def test_complete_matrix_expansion_must_be_exact() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    mutations = (
        workflow.replace("        os: [windows-latest, ubuntu-latest]", "        os: [windows-latest, ubuntu-latest]\n        include: [{os: self-hosted, python-version: '3.13'}]", 1),
        workflow.replace("        os: [windows-latest, ubuntu-latest]", "        os: [windows-latest, ubuntu-latest]\n        exclude: [{os: windows-latest}]", 1),
        workflow.replace("        python-version: [\"3.11\", \"3.12\", \"3.13\"]", "        python-version: [\"3.11\", \"3.12\", \"3.13\"]\n        architecture: [x64, arm64]", 1),
        workflow.replace("os: [windows-latest, ubuntu-latest]", "os: ${{ fromJSON(inputs.runners) }}", 1),
        workflow.replace('python-version: ["3.11", "3.12", "3.13"]', 'python-version: ["3.11", "3.12", "3.13", "3.14"]', 1),
        workflow.replace("      fail-fast: false", "      fail-fast: false\n      max-parallel: 1", 1),
    )
    for mutated in mutations:
        assert _workflow_errors(mutated, 78.0)


def test_fixed_workflow_certification_metadata_catalog_fails_closed() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    workflow_mutations = (
        workflow.replace("  workflow_dispatch:\n", "", 1),
        workflow.replace("permissions:\n  contents: read", "permissions:\n  contents: write", 1),
        workflow.replace("jobs:\n  validation_matrix:", "concurrency: unsafe\n\njobs:\n  validation_matrix:", 1),
        workflow.replace("jobs:\n  validation_matrix:", "jobs:\n  injected: null\n  validation_matrix:", 1),
        workflow.replace("    needs: validate", "    needs: []", 1),
        workflow.replace("    runs-on: ubuntu-latest", "    runs-on: windows-latest", 1),
        workflow.replace("    permissions:\n      contents: read", "    permissions: {}", 1),
        workflow.replace("      - name: Validate critical coverage", "      - name: Validate critical coverage\n        shell: bash", 1),
        workflow.replace("        continue-on-error: true", "        continue-on-error: false", 1),
        workflow.replace("        if: always()", "        if: success()", 1),
        workflow.replace("          name: quality-security-release", "          name: substituted", 1),
        workflow.replace('test "${{ needs.validation_matrix.result }}" = "success"\n', "", 1),
        workflow.replace("          path: phase-rollback-receipt.json", "          path: README.md", 1),
    )
    for mutated in workflow_mutations:
        assert _workflow_errors(mutated, 78.0)
    release_mutations = (
        release.replace('      - "v*"', '      - "release-*"', 1),
        release.replace("id-token: write", "id-token: read", 1),
        release.replace("cancel-in-progress: false", "cancel-in-progress: true", 1),
        release.replace("    permissions:\n      contents: write", "    permissions:\n      contents: read", 1),
        release.replace("          subject-path: dist/*", "          subject-path: outputs/*", 1),
        release.replace("          sbom-path: outputs/sbom.cdx.json", "          sbom-path: README.md", 1),
    )
    for mutated in release_mutations:
        assert _workflow_errors(workflow, 78.0, mutated)


def test_step_environment_and_constructed_file_commands_fail_closed() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    step_env = workflow.replace(
        "      - name: Validate generated dependency lock\n        run:",
        "      - name: Validate generated dependency lock\n        env:\n          pyThOnPaTh: attacker\n        run:",
        1,
    )
    assert any("pyThOnPaTh" in error for error in _workflow_errors(step_env, 78.0))
    gate = next(
        block for block in workflow.split("      - ")
        if block.startswith("name: Prove exact source integrity")
    )
    marker = "      - " + gate
    constructed = (
        marker
        + "      - name: Construct persisted poison\n"
        + "        run: echo bad >> $GITHUB_'ENV'\n"
    )
    assert any("must not poison" in error for error in _workflow_errors(workflow.replace(marker, constructed, 1), 78.0))
    powershell = (
        marker
        + "      - name: Construct persisted PATH poison\n"
        + "        run: $channel = 'GITHUB_' + 'PATH'; Add-Content $channel 'C:\\\\attacker'\n"
    )
    assert any("must not poison" in error for error in _workflow_errors(workflow.replace(marker, powershell, 1), 78.0))
    formatted = (
        marker
        + "      - name: Format persisted poison name\n"
        + "        run: $channel = 'GITHUB_%s' -f 'ENV'; Add-Content $channel bad\n"
    )
    assert any("must not poison" in error for error in _workflow_errors(workflow.replace(marker, formatted, 1), 78.0))


def test_actions_and_trusted_interpreter_sequence_are_immutable() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    mutations = (
        workflow.replace("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", "actions/upload-artifact@v7", 1),
        workflow.replace("actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", "attacker/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97", 1),
        workflow.replace(" -I -E -S scripts/validate_source_integrity.py", " scripts/validate_source_integrity.py", 1),
        workflow.replace("${{ steps.trusted_python.outputs.path }}", "python", 1),
        workflow.replace("Get-Command python -CommandType Application | Select-Object -First 1 -ExpandProperty Source", "'C:\\\\attacker\\python.exe'", 1),
    )
    for mutated in mutations:
        assert _workflow_errors(mutated, 78.0)
    action_without_proof = workflow.replace(
        "      - name: Prove exact source integrity\n        shell: pwsh\n",
        "      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a\n        with:\n          name: premature\n          path: README.md\n      - name: Prove exact source integrity\n        shell: pwsh\n",
        1,
    )
    assert any("fresh adjacent source proof" in error for error in _workflow_errors(action_without_proof, 78.0))


def test_trusted_tool_capture_emits_one_executable_path_per_output(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    assert pwsh is not None
    output = tmp_path / "github-output.txt"
    completed = subprocess.run(
        [pwsh, "-NoProfile", "-NonInteractive", "-Command", TRUSTED_PYTHON_COMMAND],
        cwd=ROOT,
        env={**os.environ, "GITHUB_OUTPUT": str(output)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    raw_output = output.read_bytes()
    output_text = raw_output.decode("utf-16" if raw_output.startswith(b"\xff\xfe") else "utf-8")
    entries = dict(line.split("=", 1) for line in output_text.splitlines())
    assert set(entries) == {"path", "git_path"}
    python_path, git_path = Path(entries["path"]), Path(entries["git_path"])
    assert python_path.is_absolute() and python_path.is_file()
    assert git_path.is_absolute() and git_path.is_file()
    subprocess.run([str(python_path), "-I", "-E", "-c", "print('trusted')"], check=True)
    subprocess.run([str(git_path), "--version"], check=True)


def test_rollback_baseline_boundaries_each_require_fresh_baseline_proof() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    proof_start = "      - name: Prove exact restored baseline\n"
    positions = [index for index in range(len(workflow)) if workflow.startswith(proof_start, index)]
    assert len(positions) == 10
    for position in positions:
        end = workflow.find("\n      - ", position + len(proof_start))
        removed = workflow[:position] + workflow[end + 1 :]
        assert any("fresh adjacent source proof" in error for error in _workflow_errors(removed, 78.0))
    weakened_transition = workflow.replace(
        '"${{ steps.trusted_python.outputs.path }}" -I -E -S scripts/verify_phase0_rollback.py --baseline "$baseline" --receipt phase0-rollback-receipt.json',
        "git checkout main",
        1,
    )
    assert any("fresh adjacent source proof" in error for error in _workflow_errors(weakened_transition, 78.0))


def test_coverage_and_risk_commands_reject_deletion_path_or_threshold_weakening() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    mutations = (
        workflow.replace("--cov=runtime", "--cov=runtime2", 1),
        workflow.replace("outputs/coverage.json", "outputs/weaker.json", 1),
        workflow.replace("--cov-fail-under=78", "--cov-fail-under=77", 1),
        workflow.replace("python scripts/validate_risk_coverage.py outputs/coverage.json", "", 1),
        workflow.replace(
            "python scripts/validate_risk_coverage.py outputs/coverage.json",
            "python scripts/renamed_risk_coverage.py outputs/coverage.json",
            1,
        ),
        workflow.replace(
            "        run: pytest -q --cov=runtime",
            "        run: |\n          exit 0\n          pytest -q --cov=runtime",
            1,
        ),
    )
    for mutated in mutations:
        assert _workflow_errors(mutated, 78.0)


def test_quality_steps_reject_masking_metadata_and_wrong_order() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    coverage_run = "        run: pytest -q --cov=runtime"
    risk_block = (
        "      - name: Validate critical coverage\n"
        "        run: python scripts/validate_risk_coverage.py outputs/coverage.json"
    )
    for addition in (
        "\n        if: false",
        "\n        continue-on-error: true",
        "\n        shell: bash",
    ):
        assert _workflow_errors(workflow.replace(risk_block, risk_block + addition, 1), 78.0)
    assert _workflow_errors(
        workflow.replace(coverage_run, coverage_run + " || true", 1), 78.0
    )
    conditional_job = workflow.replace(
        "  quality_security_release:\n    permissions:\n      contents: read\n    needs: validate",
        "  quality_security_release:\n    permissions:\n      contents: read\n    if: false\n    needs: validate",
        1,
    )
    assert any("quality job" in error for error in _workflow_errors(conditional_job, 78.0))
    for defaults in (
        "defaults:\n  run:\n    shell: bash -c 'exit 0' {0}\n\n",
        "defaults:\n  run:\n    working-directory: unrelated\n\n",
    ):
        assert _workflow_errors(defaults + workflow, 78.0)
    for setting in (
        "shell: bash -c 'exit 0' {0}",
        "working-directory: unrelated",
    ):
        job_default = workflow.replace(
            "  quality_security_release:\n    permissions:\n      contents: read\n    needs: validate",
            f"  quality_security_release:\n    permissions:\n      contents: read\n    defaults:\n      run:\n        {setting}\n    needs: validate",
            1,
        )
        assert _workflow_errors(job_default, 78.0)
    unrelated_default = workflow.replace(
        "  provider_authentication:\n",
        "  provider_authentication:\n    defaults:\n      run:\n        shell: bash\n",
        1,
    )
    assert _workflow_errors(unrelated_default, 78.0) == []
    coverage_block = next(
        block for block in workflow.split("      - ") if block.startswith("name: Run coverage gate")
    ).rstrip()
    risk_text = next(
        block for block in workflow.split("      - ") if block.startswith("name: Validate critical coverage")
    ).rstrip()
    reversed_workflow = workflow.replace(coverage_block, "__COVERAGE__", 1).replace(
        risk_text, coverage_block, 1
    ).replace("__COVERAGE__", risk_text, 1)
    assert any("must precede" in error for error in _workflow_errors(reversed_workflow, 78.0))


def test_repository_policy_rejects_risk_script_deletion_and_floor_weakening(
    tmp_path: Path
) -> None:
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / "scripts").mkdir()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    critical = next(iter(MINIMUM_CRITICAL_COVERAGE))
    pyproject = pyproject.replace(
        f'"{critical}" = {int(MINIMUM_CRITICAL_COVERAGE[critical])}',
        f'"{critical}" = {int(MINIMUM_CRITICAL_COVERAGE[critical]) - 1}',
    )
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (tmp_path / ".github/workflows/validate.yml").write_text(
        (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / ".github/workflows/release.yml").write_text(
        (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    contract = json.loads((ROOT / "governance/code-quality-ratchet.json").read_text())
    errors = _repository_setting_errors(tmp_path, contract)
    assert f"critical coverage floor is missing or weak: {critical}" in errors
    assert "CI risk coverage validator script is missing" in errors
