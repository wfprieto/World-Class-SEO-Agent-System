from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_quality_ratchets import ROOT, _repository_setting_errors, build_contract, validate


def _baseline(tmp_path: Path, sources: dict[str, str] | None = None) -> Path:
    for package in ("runtime", "adapters", "integrations", "seoctl", "scripts"):
        package_path = tmp_path / package
        package_path.mkdir(parents=True)
        (package_path / "__init__.py").write_text("", encoding="utf-8")
    for relative, content in (sources or {}).items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    contract = build_contract(tmp_path)
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
    errors = _repository_setting_errors(tmp_path, contract)
    assert "pyproject Ruff profile must equal the canonical P3 rule profile" in errors
    assert "repository coverage floor is weaker than the quality contract" in errors
    assert any("validate_architecture_contract.py" in error for error in errors)
