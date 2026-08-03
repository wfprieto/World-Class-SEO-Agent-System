from __future__ import annotations

from pathlib import Path

from scripts.validate_scheduled_maintenance import validate

ROOT = Path(__file__).resolve().parents[1]


def _mutate(tmp_path: Path, old: str, new: str) -> list[str]:
    source = ROOT / ".github/workflows/maintenance.yml"
    target = tmp_path / ".github/workflows/maintenance.yml"
    target.parent.mkdir(parents=True)
    text = source.read_text(encoding="utf-8")
    assert old in text
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return validate(tmp_path)


def test_scheduled_maintenance_contract_passes() -> None:
    assert validate() == []


def test_schedule_and_manual_dispatch_are_mandatory(tmp_path: Path) -> None:
    errors = _mutate(tmp_path, "  workflow_dispatch:\n", "")
    assert any("triggers must be" in error for error in errors)


def test_permissions_cannot_be_elevated(tmp_path: Path) -> None:
    errors = _mutate(tmp_path, "  contents: read", "  contents: write")
    assert any("exact read-only" in error for error in errors)


def test_actions_must_use_immutable_commits(tmp_path: Path) -> None:
    errors = _mutate(
        tmp_path,
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/setup-python@v7",
    )
    assert any("action is mutable" in error for error in errors)


def test_required_gate_cannot_be_removed(tmp_path: Path) -> None:
    errors = _mutate(
        tmp_path,
        "python scripts/validate_open_issue_remediation.py",
        "python scripts/pretend_validation.py",
    )
    assert any("commands are missing" in error for error in errors)


def test_checkout_cannot_persist_credentials(tmp_path: Path) -> None:
    errors = _mutate(tmp_path, "persist-credentials: false", "persist-credentials: true")
    assert any("checkout settings must remain exact" in error for error in errors)
