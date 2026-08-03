from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.validate_open_issue_remediation import validate

ROOT = Path(__file__).resolve().parents[1]


def _copy_surface(tmp_path: Path) -> Path:
    contract = json.loads(
        (ROOT / "governance/open-issue-remediation.json").read_text(encoding="utf-8")
    )
    paths = {
        "schemas/open-issue-remediation.schema.json",
        "governance/open-issue-remediation.json",
        "governance/repository-operations.json",
        *(path for row in contract["issues"] for path in row["evidence_paths"]),
    }
    for relative in paths:
        source = ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return tmp_path


def _mutate(tmp_path: Path, operation) -> list[str]:
    root = _copy_surface(tmp_path)
    path = root / "governance/open-issue-remediation.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    operation(payload)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return validate(root)


def test_open_issue_remediation_contract_passes() -> None:
    assert validate() == []


def test_six_canonical_issues_are_required(tmp_path: Path) -> None:
    errors = _mutate(tmp_path, lambda payload: payload["issues"].pop())
    assert any("issues 26, 28, 29, 30, 31, and 32" in error for error in errors)


def test_issue_identity_and_classification_cannot_drift(tmp_path: Path) -> None:
    def mutate(payload):
        payload["issues"][0]["classification"] = "RECURRING_CONTROL"
        payload["issues"][0]["close_policy"] = "KEEP_OPEN_RECURRING"

    errors = _mutate(tmp_path, mutate)
    assert any("issue 26 classification" in error for error in errors)


def test_owner_only_conduct_blocker_cannot_be_erased(tmp_path: Path) -> None:
    def mutate(payload):
        row = next(row for row in payload["issues"] if row["number"] == 30)
        row["state"] = "ACTIVE"
        row["blocked_by"] = None

    errors = _mutate(tmp_path, mutate)
    assert any("issue 30 cannot claim remediation" in error for error in errors)


def test_evidence_path_must_exist_inside_repository(tmp_path: Path) -> None:
    def mutate(payload):
        payload["issues"][0]["evidence_paths"] = ["../outside.json"]

    errors = _mutate(tmp_path, mutate)
    assert any("missing or unsafe" in error for error in errors)


def test_recurring_control_cannot_claim_one_time_closure(tmp_path: Path) -> None:
    def mutate(payload):
        row = next(row for row in payload["issues"] if row["number"] == 29)
        row["close_policy"] = "CLOSE_ON_ACCEPTANCE"

    errors = _mutate(tmp_path, mutate)
    assert any("KEEP_OPEN_RECURRING" in error for error in errors)


def test_unknown_fields_fail_closed(tmp_path: Path) -> None:
    errors = _mutate(
        tmp_path,
        lambda payload: payload["issues"][0].update({"pretend_complete": True}),
    )
    assert any("Additional properties are not allowed" in error for error in errors)
