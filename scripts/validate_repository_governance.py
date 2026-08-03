#!/usr/bin/env python3
"""Fail-closed validation for repository governance and captured provider state."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_phase8_issues import issue_errors  # noqa: E402

ADVISORY_URL = "https://github.com/wfprieto/World-Class-SEO-Agent-System/security/advisories/new"
CERTIFICATION_NEEDS = {
    "validation_matrix", "provider_authentication", "validate", "quality_security_release",
    "clean_wheel_install", "phase0_rollback_certification", "phase_rollback_certification",
}
COLLABORATOR_PERMISSIONS = {"pull", "triage", "push", "maintain", "admin"}
PROVIDER_JOB_MARKERS = ("WCSEO_AUTHENTICATE_CI_RECEIPTS", "GITHUB_TOKEN", "capture_github_controls.py --ci-observable", "Reject provider-unverifiable fork pull requests", "head.repo.full_name != github.repository", "repository certification fails closed")

def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return value


def _phase8_local_errors(
    contract: dict[str, Any], provider_job: object
) -> list[str]:
    errors: list[str] = []
    expected_pull = {
        "number": 24,
        "base": "main",
        "head": "agent/owner-controlled-remediation-loop",
        "allowed_states": ["OPEN", "CLOSED"],
    }
    if contract.get("phase8_pull_request") != expected_pull:
        errors.append("Phase 8 provider evidence must bind the exact remediation pull request")
    expected_permissions = {
        "contents": "read",
        "issues": "read",
        "pull-requests": "read",
    }
    if isinstance(provider_job, dict) and provider_job.get("permissions") != expected_permissions:
        errors.append(
            "provider-authentication permissions must be exact read-only contents/issues/pull-requests"
        )
    return errors


def local_errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    security = (root / "SECURITY.md").read_text(encoding="utf-8")
    support = (root / "SUPPORT.md").read_text(encoding="utf-8")
    config = _load_yaml(root / ".github/ISSUE_TEMPLATE/config.yml")
    workflow = _load_yaml(root / ".github/workflows/validate.yml")
    contract = _load_json(root / "governance/github-controls.json")
    if ADVISORY_URL not in security:
        errors.append("SECURITY.md must link directly to the private advisory form")
    contact_urls = {link.get("url") for link in config.get("contact_links", [])}
    if ADVISORY_URL not in contact_urls:
        errors.append("issue configuration must link directly to the private advisory form")
    support_form = root / ".github/ISSUE_TEMPLATE/support_request.yml"
    if not support_form.is_file() or "support_request.yml" not in support:
        errors.append("a documented repository-owned support request form is required")
    elif "credentials, private URLs, client data" not in support_form.read_text(encoding="utf-8"):
        errors.append("support form must require removal of sensitive data")
    if (root / ".github/ISSUE_TEMPLATE/bug_report.md").exists():
        errors.append("legacy duplicate bug_report.md must not weaken the issue form")

    for workflow_path in sorted((root / ".github/workflows").glob("*.yml")):
        workflow_text = workflow_path.read_text(encoding="utf-8")
        for reference in re.findall(r"\buses:\s*([^\s#]+)", workflow_text):
            if not re.fullmatch(r"[^/@\s]+/[^/@\s]+@[0-9a-f]{40}", reference):
                errors.append(f"{workflow_path.name} has mutable action reference {reference}")
        workflow_document = _load_yaml(workflow_path)
        for job in workflow_document.get("jobs", {}).values():
            for step in job.get("steps", []):
                if not isinstance(step, dict):
                    continue
                reference = str(step.get("uses", ""))
                options = step.get("with", {})
                if not isinstance(options, dict):
                    options = {}
                if (
                    reference.startswith("actions/checkout@")
                    and options.get("persist-credentials") is not False
                ):
                    errors.append(
                        f"{workflow_path.name} checkout must set persist-credentials: false"
                    )

    names: dict[str, str] = {}
    for path in sorted((root / ".github/ISSUE_TEMPLATE").glob("*.yml")):
        document = _load_yaml(path)
        name = document.get("name")
        if isinstance(name, str) and name in names:
            errors.append(f"duplicate issue-template name {name!r}: {names[name]} and {path.name}")
        elif isinstance(name, str):
            names[name] = path.name
    ruleset = contract.get("ruleset", {})
    for service in (
        "private_vulnerability_reporting",
        "vulnerability_alerts",
        "dependabot_security_updates",
        "secret_scanning",
        "secret_scanning_push_protection",
    ):
        if contract.get(service) is not True:
            errors.append(f"governance contract must require {service}=true")
    expected = {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": True,
        "require_last_push_approval": False,
        "required_review_thread_resolution": True,
        "required_linear_history": True,
        "block_deletion": True,
        "block_non_fast_forward": True,
        "bypass_actor_count": 0,
    }
    for key, value in expected.items():
        if ruleset.get(key) != value:
            errors.append(f"governance contract must set ruleset.{key}={value!r}")
    checks = ruleset.get("required_status_checks", [])
    if [check.get("context") for check in checks] != ["repository-certification"]:
        errors.append("repository-certification must be the sole required status check")
    reviewer = contract.get("independent_reviewer", {})
    if reviewer.get("accountable_owner") != "Repository maintainer":
        errors.append("solo-maintainer governance requires the repository maintainer owner")
    if reviewer.get("due_phase") != "P8":
        errors.append("solo-maintainer governance decision must remain bound to Phase P8")
    if (reviewer.get("status"), reviewer.get("merge_availability")) != (
        "NOT_APPLICABLE_SOLO_MAINTAINER", "AVAILABLE_AFTER_REQUIRED_STATUS_CHECKS"
    ):
        errors.append("governance must bind truthful solo-maintainer status to required checks")
    if workflow.get("permissions") != {"contents": "read"}:
        errors.append("validation workflow must retain least-privilege contents: read permission")
    triggers = workflow.get("on")
    if not isinstance(triggers, dict):
        # PyYAML 1.1 may parse the plain scalar `on` as boolean true.
        triggers = workflow.get("True")
    if not isinstance(triggers, dict):
        triggers = {}
    pull_request = triggers.get("pull_request")
    if pull_request not in (None, {}):
        errors.append("validation must run on every pull request without path filters")
    jobs = workflow.get("jobs", {})
    matrix_job = jobs.get("validation_matrix", {})
    matrix_text = json.dumps(matrix_job, sort_keys=True)
    if "GITHUB_TOKEN" in matrix_text or "capture_github_controls.py" in matrix_text:
        errors.append("runtime matrix must remain deterministic and provider-offline")
    provider_job = jobs.get("provider_authentication")
    if not isinstance(provider_job, dict) or provider_job.get("name") != "provider-authentication":
        errors.append("one centralized provider-authentication job is required")
    else:
        provider_text = json.dumps(provider_job, sort_keys=True)
        for required_text in PROVIDER_JOB_MARKERS:
            if required_text not in provider_text:
                errors.append(f"provider-authentication job is missing {required_text}")
    errors.extend(_phase8_local_errors(contract, provider_job))
    aggregate = jobs.get("validate", {})
    aggregate_needs = aggregate.get("needs", []) if isinstance(aggregate, dict) else []
    if isinstance(aggregate_needs, str):
        aggregate_needs = [aggregate_needs]
    if set(aggregate_needs) != {"validation_matrix", "provider_authentication"}:
        errors.append("validate aggregate must require matrix and provider authentication")
    aggregate_text = json.dumps(aggregate, sort_keys=True)
    if "needs.provider_authentication.result" not in aggregate_text:
        errors.append("validate aggregate must enforce provider-authentication success")
    matching = [job for job in jobs.values() if job.get("name") == "repository-certification"]
    if len(matching) != 1:
        errors.append("exactly one repository-certification workflow job is required")
    else:
        job = matching[0]
        needs = job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        if set(needs) != CERTIFICATION_NEEDS:
            errors.append("repository-certification must depend on every canonical certification job")
        run_text = "\n".join(
            str(step.get("run", "")) for step in job.get("steps", []) if isinstance(step, dict)
        )
        for need in CERTIFICATION_NEEDS - {"validation_matrix"}:
            if f"needs.{need}.result" not in run_text:
                errors.append(f"repository-certification does not enforce {need} result")
    return errors


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
        (item for item in operations.get("critical_paths", []) if item.get("id") == "security-intake"),
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
    if not isinstance(captured_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", captured_at):
        errors.append("provider snapshot requires a UTC captured_at timestamp")
    elif require_fresh:
        captured = dt.datetime.strptime(captured_at, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.UTC
        )
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
