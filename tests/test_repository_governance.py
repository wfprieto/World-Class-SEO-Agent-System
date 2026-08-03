from __future__ import annotations

import copy
import datetime as dt
import json
import shutil
from pathlib import Path

import pytest

from scripts.validate_repository_governance import (
    local_errors,
    provider_errors,
    provider_state_errors,
)

ROOT = Path(__file__).resolve().parents[1]


def _phase8_snapshot() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    contract = json.loads(
        (ROOT / "governance/github-controls.json").read_text(encoding="utf-8")
    )
    operations = json.loads(
        (ROOT / "governance/repository-operations.json").read_text(encoding="utf-8")
    )
    owner = contract["repository"].partition("/")[0]
    snapshot: dict[str, object] = {
        "schema_version": "3.0.0",
        "repository": contract["repository"],
        "default_branch": contract["default_branch"],
        "private_vulnerability_reporting": True,
        "discussions": True,
        "vulnerability_alerts": True,
        "dependabot_security_updates": True,
        "secret_scanning": True,
        "secret_scanning_push_protection": True,
        "authenticated": True,
        "authenticated_actor": owner,
        "capture_method": "gh-api-live",
        "captured_at": dt.datetime.now(dt.UTC).replace(microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "ruleset": dict(contract["ruleset"]),
        "collaborators": [
            {
                "login": owner,
                "role_name": "admin",
                "permissions": {
                    "pull": True,
                    "triage": True,
                    "push": True,
                    "maintain": True,
                    "admin": True,
                },
            }
        ],
        "eligible_independent_reviewers": [],
        "independent_reviewer_status": "OWNER_ACTION_REQUIRED",
        "phase8_issues": [
            {
                "control_id": control["id"],
                "number": control["issue"]["number"],
                "url": control["issue"]["url"],
                "title": control["title"],
                "state": control["issue"]["expected_state"],
                "assignees": [owner],
                "locked": False,
            }
            for control in operations["critical_paths"]
        ],
        "phase8_pull_request": {
            "number": 24,
            "url": f"https://github.com/{contract['repository']}/pull/24",
            "base": "main",
            "head": "agent/owner-controlled-remediation-loop",
            "state": "OPEN",
            "draft": True,
            "merged": False,
        },
        "declared_blockers": {
            "independent_reviewer": "OWNER_ACTION_REQUIRED",
            "private_conduct_reporting": "OWNER_ACTION_REQUIRED",
        },
    }
    return snapshot, contract, operations


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
    contract["ruleset"]["required_approving_review_count"] = 1
    path.write_text(json.dumps(contract), encoding="utf-8")
    assert any("required_approving_review_count" in error for error in local_errors(root))


@pytest.mark.parametrize(
    "field",
    ["dependabot_security_updates", "secret_scanning", "secret_scanning_push_protection"],
)
def test_governance_contract_cannot_disable_security_service(
    tmp_path: Path, field: str
) -> None:
    root = _copy_repository_surface(tmp_path)
    path = root / "governance/github-controls.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract[field] = False
    path.write_text(json.dumps(contract), encoding="utf-8")
    assert any(field in error for error in local_errors(root))


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


def test_provider_authentication_cannot_fan_out_across_runtime_matrix(tmp_path: Path) -> None:
    root = _copy_repository_surface(tmp_path)
    workflow = root / ".github/workflows/validate.yml"
    text = workflow.read_text(encoding="utf-8")
    text = text.replace(
        "run: python scripts/validate_repository_governance.py\n",
        "run: python scripts/validate_repository_governance.py\n"
        "      - name: Duplicate provider query\n"
        "        run: python scripts/capture_github_controls.py --ci-observable\n",
        1,
    )
    workflow.write_text(text, encoding="utf-8")
    assert any("provider-offline" in error for error in local_errors(root))


def test_fork_pull_request_provider_skip_cannot_certify(tmp_path: Path) -> None:
    root = _copy_repository_surface(tmp_path)
    workflow = root / ".github/workflows/validate.yml"
    text = workflow.read_text(encoding="utf-8")
    start = text.index("      - name: Reject provider-unverifiable fork pull requests")
    end = text.index("\n\n  validate:", start)
    workflow.write_text(text[:start] + text[end:], encoding="utf-8")

    assert any("Reject provider-unverifiable fork pull requests" in error for error in local_errors(root))


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
        "schema_version": "2.0.0",
        "repository": contract["repository"],
        "default_branch": "main",
        "private_vulnerability_reporting": True,
        "discussions": True,
        "vulnerability_alerts": True,
        "dependabot_security_updates": True,
        "secret_scanning": True,
        "secret_scanning_push_protection": True,
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
    snapshot["ruleset"]["require_last_push_approval"] = True
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert any("require_last_push_approval" in error for error in provider_errors(path))


@pytest.mark.parametrize(
    "field",
    ["dependabot_security_updates", "secret_scanning", "secret_scanning_push_protection"],
)
def test_security_service_missing_or_disabled_is_rejected(tmp_path: Path, field: str) -> None:
    contract = json.loads((ROOT / "governance/github-controls.json").read_text(encoding="utf-8"))
    snapshot = {
        "schema_version": "2.0.0",
        "repository": contract["repository"],
        "default_branch": "main",
        "private_vulnerability_reporting": True,
        "discussions": True,
        "vulnerability_alerts": True,
        "dependabot_security_updates": True,
        "secret_scanning": True,
        "secret_scanning_push_protection": True,
        "authenticated": True,
        "authenticated_actor": "test-owner",
        "capture_method": "gh-api-live",
        "captured_at": dt.datetime.now(dt.UTC).replace(microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "ruleset": dict(contract["ruleset"]),
    }
    path = tmp_path / "snapshot.json"
    weakened = dict(snapshot)
    weakened[field] = False
    path.write_text(json.dumps(weakened), encoding="utf-8")
    assert any(field in error for error in provider_errors(path))
    missing = dict(snapshot)
    del missing[field]
    path.write_text(json.dumps(missing), encoding="utf-8")
    assert any(field in error for error in provider_errors(path))


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ("missing_collaborators", "collaborator inventory"),
        ("invented_reviewer", "reviewer availability differs"),
        ("closed_issue", "issue 26 state"),
        ("unassigned_issue", "issue 26 is not assigned"),
        ("wrong_pull_head", "pull request head"),
        ("false_conduct_ready", "declared blockers"),
    ],
)
def test_phase8_provider_evidence_fails_closed(
    mutation: str, expected_error: str
) -> None:
    snapshot, contract, operations = _phase8_snapshot()
    candidate = copy.deepcopy(snapshot)
    if mutation == "missing_collaborators":
        candidate["collaborators"] = []
    elif mutation == "invented_reviewer":
        candidate["collaborators"].append(
            {
                "login": "invented-reviewer",
                "role_name": "write",
                "permissions": {
                    "pull": True,
                    "triage": True,
                    "push": True,
                    "maintain": False,
                    "admin": False,
                },
            }
        )
        candidate["collaborators"].sort(key=lambda row: row["login"])
        candidate["eligible_independent_reviewers"] = ["invented-reviewer"]
        candidate["independent_reviewer_status"] = "VERIFIED"
    elif mutation == "closed_issue":
        candidate["phase8_issues"][0]["state"] = "CLOSED"
    elif mutation == "unassigned_issue":
        candidate["phase8_issues"][0]["assignees"] = []
    elif mutation == "wrong_pull_head":
        candidate["phase8_pull_request"]["head"] = "unreviewed"
    else:
        candidate["declared_blockers"]["private_conduct_reporting"] = "VERIFIED"

    errors = provider_state_errors(candidate, contract, operations=operations)
    assert any(expected_error in error for error in errors)


def test_repository_validator_enumerates_only_tracked_documents() -> None:
    validator = (ROOT / "scripts/validate-repository.ps1").read_text(encoding="utf-8")

    assert "git -C $Root ls-files" in validator
    assert 'Get-TrackedFiles "*.json"' in validator
    assert 'Get-TrackedFiles "*.md"' in validator
    assert 'Get-ChildItem -Path $Root -Recurse' not in validator
