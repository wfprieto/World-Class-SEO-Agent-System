from __future__ import annotations

import copy
import json
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
    no_checkout = "\n".join(
        line for line in workflow.splitlines() if "uses: actions/checkout@" not in line
    )
    assert "CI requires at least one pinned actions/checkout step" in _workflow_errors(
        no_checkout, 78.0
    )
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


def test_quality_job_rejects_execution_altering_inherited_environment() -> None:
    workflow = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
    root_pytest_mask = "env:\n  PYTEST_ADDOPTS: --ignore=tests/test_architecture_contract.py\n\n"
    errors = _workflow_errors(root_pytest_mask + workflow, 78.0)
    assert any("PYTEST_ADDOPTS" in error for error in errors)
    job_pythonpath = workflow.replace(
        "  quality_security_release:\n    needs: validate",
        "  quality_security_release:\n    env:\n      PYTHONPATH: unrelated\n    needs: validate",
        1,
    )
    assert any("PYTHONPATH" in error for error in _workflow_errors(job_pythonpath, 78.0))
    unrelated_job_env = workflow.replace(
        "  provider_authentication:\n",
        "  provider_authentication:\n    env:\n      PROVIDER_TEST_LABEL: offline\n",
        1,
    )
    assert _workflow_errors(unrelated_job_env, 78.0) == []


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
        "  quality_security_release:\n    needs: validate",
        "  quality_security_release:\n    if: false\n    needs: validate",
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
            "  quality_security_release:\n    needs: validate",
            f"  quality_security_release:\n    defaults:\n      run:\n        {setting}\n    needs: validate",
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
