#!/usr/bin/env python3
"""Fail-closed validation for repository governance and captured provider state."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING or __package__:
    from scripts.repository_governance_policy import ROOT, _load_json
    from scripts.repository_governance_policy import local_errors as local_errors
    from scripts.validate_phase8_issues import issue_errors
else:
    from repository_governance_policy import ROOT, _load_json
    from repository_governance_policy import local_errors as local_errors
    from validate_phase8_issues import issue_errors

COLLABORATOR_PERMISSIONS = {"pull", "triage", "push", "maintain", "admin"}


def _collaborator_row(
    row: object, index: int, owner_login: str
) -> tuple[str | None, bool, list[str]]:
    if not isinstance(row, dict):
        return None, False, [f"collaborators[{index}] must be an object"]
    login = row.get("login")
    permissions = row.get("permissions")
    if not isinstance(login, str) or not login:
        return None, False, [f"collaborators[{index}] requires a login"]
    if not isinstance(permissions, dict) or set(permissions) != COLLABORATOR_PERMISSIONS:
        return login, False, [f"collaborator {login} has invalid permission inventory"]
    if any(not isinstance(value, bool) for value in permissions.values()):
        return login, False, [f"collaborator {login} permissions must be boolean"]
    return login, login != owner_login and permissions["push"], []


def _collaborator_errors(snapshot: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    rows = snapshot.get("collaborators")
    if not isinstance(rows, list) or not rows:
        return ["Phase 8 provider snapshot requires collaborator inventory"]
    errors: list[str] = []
    logins: list[str] = []
    derived_eligible: list[str] = []
    owner_login = str(contract.get("repository", "")).partition("/")[0]
    for index, row in enumerate(rows):
        login, eligible, row_errors = _collaborator_row(row, index, owner_login)
        errors.extend(row_errors)
        if login is not None:
            logins.append(login)
        if eligible and login is not None:
            derived_eligible.append(login)
    if logins != sorted(logins) or len(logins) != len(set(logins)):
        errors.append("collaborator inventory must be sorted and unique")
    if owner_login not in logins:
        errors.append("repository owner is missing from collaborator inventory")
    declared_eligible = snapshot.get("eligible_independent_reviewers")
    if declared_eligible != sorted(derived_eligible):
        errors.append("eligible independent reviewer inventory does not match permissions")
    expected_status = contract.get("independent_reviewer", {}).get("status")
    if snapshot.get("independent_reviewer_status") != expected_status:
        errors.append("provider reviewer status does not match the governance decision")
    if expected_status == "NOT_APPLICABLE_SOLO_MAINTAINER" and derived_eligible:
        errors.append("solo-maintainer status is stale because an eligible reviewer now exists")
    return errors


def _phase8_pull_errors(snapshot: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    observed = snapshot.get("phase8_pull_request")
    expected = contract.get("phase8_pull_request")
    if not isinstance(observed, dict) or not isinstance(expected, dict):
        return ["Phase 8 provider snapshot requires pull-request identity"]
    errors: list[str] = []
    for key in ("number", "base", "head"):
        if observed.get(key) != expected.get(key):
            errors.append(f"Phase 8 pull request {key} does not match the contract")
    expected_url = f"https://github.com/{contract['repository']}/pull/{expected['number']}"
    if observed.get("url") != expected_url:
        errors.append("Phase 8 pull request URL does not match the contract")
    state = observed.get("state")
    if state not in expected.get("allowed_states", []):
        errors.append("Phase 8 pull request state is not allowed by the contract")
    if state == "OPEN" and observed.get("merged") is not False:
        errors.append("an open Phase 8 pull request cannot be recorded as merged")
    if state == "CLOSED" and observed.get("merged") is not True:
        errors.append("the closed Phase 8 pull request must be recorded as merged")
    if not isinstance(observed.get("draft"), bool):
        errors.append("Phase 8 pull request draft state must be boolean")
    return errors


def _phase8_provider_errors(
    snapshot: dict[str, Any], contract: dict[str, Any], operations: dict[str, Any]
) -> list[str]:
    errors = _collaborator_errors(snapshot, contract)
    errors.extend(issue_errors(snapshot, contract, operations))
    errors.extend(_phase8_pull_errors(snapshot, contract))
    security: dict[str, Any] = next(
        (
            item
            for item in operations.get("critical_paths", [])
            if item.get("id") == "security-intake"
        ),
        {},
    )
    expected_blockers = {
        "independent_reviewer": contract.get("independent_reviewer", {}).get("status"),
        "private_conduct_reporting": (
            "OWNER_ACTION_REQUIRED"
            if security.get("status") == "BLOCKED_OWNER_ACTION"
            else "VERIFIED"
        ),
    }
    if snapshot.get("declared_blockers") != expected_blockers:
        errors.append("Phase 8 declared blockers do not match canonical source state")
    return errors


def _base_provider_errors(  # noqa: C901 - bounded normalized provider comparison
    snapshot: dict[str, Any],
    contract: dict[str, Any],
    *,
    require_fresh: bool = True,
) -> list[str]:
    errors: list[str] = []
    if snapshot.get("repository") != contract.get("repository"):
        errors.append("provider snapshot repository does not match the contract")
    for key in (
        "default_branch",
        "private_vulnerability_reporting",
        "discussions",
        "vulnerability_alerts",
        "dependabot_security_updates",
        "secret_scanning",
        "secret_scanning_push_protection",
    ):
        if snapshot.get(key) != contract.get(key):
            errors.append(f"provider setting {key} does not match the contract")
    observed = snapshot.get("ruleset")
    expected = contract.get("ruleset")
    if not isinstance(expected, dict):
        return ["governance contract is missing the normalized ruleset"]
    if not isinstance(observed, dict):
        errors.append("provider snapshot is missing the normalized ruleset")
    else:
        for key, value in expected.items():
            if observed.get(key) != value:
                errors.append(f"provider ruleset.{key} does not match the contract")
    captured_at = snapshot.get("captured_at")
    if not isinstance(captured_at, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", captured_at
    ):
        errors.append("provider snapshot requires a UTC captured_at timestamp")
    elif require_fresh:
        captured = dt.datetime.strptime(captured_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
        if dt.datetime.now(dt.UTC) - captured > dt.timedelta(hours=24):
            errors.append("provider snapshot is older than the 24-hour closure window")
    if snapshot.get("authenticated") is not True:
        errors.append("provider snapshot must attest authenticated capture")
    if not isinstance(snapshot.get("authenticated_actor"), str):
        errors.append("provider snapshot must identify the authenticated actor")
    if snapshot.get("capture_method") not in {
        "gh-api-live",
        "gh-api-live-plus-fresh-owner-capture",
        "gh-api-live-plus-owner-attestation",
    }:
        errors.append("provider snapshot must identify the live gh API capture method")
    return errors


def provider_state_errors(
    snapshot: dict[str, Any],
    contract: dict[str, Any],
    *,
    require_fresh: bool = True,
    operations: dict[str, Any] | None = None,
) -> list[str]:
    errors = _base_provider_errors(snapshot, contract, require_fresh=require_fresh)
    version = snapshot.get("schema_version")
    if version not in {"2.0.0", "3.0.0"}:
        errors.append("provider snapshot schema_version is unsupported")
    if version != "3.0.0":
        return errors
    if operations is None:
        errors.append("Phase 8 provider validation requires repository operations")
    else:
        errors.extend(_phase8_provider_errors(snapshot, contract, operations))
    return errors


def provider_errors(snapshot_path: Path, root: Path = ROOT) -> list[str]:
    snapshot = _load_json(snapshot_path)
    contract = _load_json(root / "governance/github-controls.json")
    operations = (
        _load_json(root / "governance/repository-operations.json")
        if snapshot.get("schema_version") == "3.0.0"
        else None
    )
    return provider_state_errors(snapshot, contract, operations=operations)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-snapshot", type=Path)
    args = parser.parse_args()
    errors = local_errors()
    if args.provider_snapshot:
        errors.extend(provider_errors(args.provider_snapshot))
    if errors:
        print(json.dumps({"result": "FAIL", "errors": errors}, indent=2))
        return 1
    print(json.dumps({"result": "PASS", "provider_verified": bool(args.provider_snapshot)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
