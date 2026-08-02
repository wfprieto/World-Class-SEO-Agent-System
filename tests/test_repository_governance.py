from __future__ import annotations

import json
import shutil
import datetime as dt
from pathlib import Path

from scripts.validate_repository_governance import local_errors, provider_errors


ROOT = Path(__file__).resolve().parents[1]


def _copy_repository_surface(tmp_path: Path) -> Path:
    for relative in ("SECURITY.md", "SUPPORT.md"):
        shutil.copy2(ROOT / relative, tmp_path / relative)
    for relative in (
        ".github/ISSUE_TEMPLATE",
        ".github/workflows",
        "governance",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ROOT / relative, destination)
    return tmp_path


def test_repository_governance_is_valid() -> None:
    assert local_errors() == []


def test_indirect_security_destination_is_rejected(tmp_path: Path) -> None:
    root = _copy_repository_surface(tmp_path)
    security = root / "SECURITY.md"
    security.write_text(
        security.read_text(encoding="utf-8").replace("security/advisories/new", "security/policy"),
        encoding="utf-8",
    )
    assert any("private advisory form" in error for error in local_errors(root))


def test_weakened_certification_contract_is_rejected(tmp_path: Path) -> None:
    root = _copy_repository_surface(tmp_path)
    path = root / "governance/github-controls.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["ruleset"]["required_approving_review_count"] = 0
    path.write_text(json.dumps(contract), encoding="utf-8")
    assert any("required_approving_review_count" in error for error in local_errors(root))


def test_incomplete_certification_aggregation_is_rejected(tmp_path: Path) -> None:
    root = _copy_repository_surface(tmp_path)
    workflow = root / ".github/workflows/validate.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            ", phase0_rollback_certification", ""
        ),
        encoding="utf-8",
    )
    assert any("canonical certification job" in error for error in local_errors(root))


def test_mutable_action_and_persisted_checkout_credentials_are_rejected(tmp_path: Path) -> None:
    root = _copy_repository_surface(tmp_path)
    workflow = root / ".github/workflows/validate.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8")
        .replace(
            "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
            "actions/checkout@v7",
            1,
        )
        .replace("persist-credentials: false", "persist-credentials: true", 1),
        encoding="utf-8",
    )
    errors = local_errors(root)
    assert any("mutable action reference" in error for error in errors)
    assert any("persist-credentials" in error for error in errors)


def test_provider_snapshot_fails_closed_on_missing_and_weaker_state(tmp_path: Path) -> None:
    contract = json.loads((ROOT / "governance/github-controls.json").read_text(encoding="utf-8"))
    snapshot = {
        "repository": contract["repository"],
        "default_branch": "main",
        "private_vulnerability_reporting": True,
        "discussions": True,
        "vulnerability_alerts": True,
        "authenticated": True,
        "authenticated_actor": "test-owner",
        "capture_method": "gh-api-live",
        "captured_at": dt.datetime.now(dt.UTC).replace(microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "ruleset": dict(contract["ruleset"]),
    }
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert provider_errors(path) == []
    snapshot["ruleset"]["require_last_push_approval"] = False
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert any("require_last_push_approval" in error for error in provider_errors(path))
