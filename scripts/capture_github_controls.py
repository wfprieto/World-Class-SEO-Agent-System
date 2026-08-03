#!/usr/bin/env python3
"""Capture and fail-closed verify live GitHub repository governance controls."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_repository_governance import provider_state_errors  # noqa: E402

REPOSITORY = "wfprieto/World-Class-SEO-Agent-System"
RULESET_ID = 18955880
PERMISSIONS = ("pull", "triage", "push", "maintain", "admin")


def _api(endpoint: str) -> Any:
    output = subprocess.check_output(
        ["gh", "api", endpoint], text=True, encoding="utf-8", timeout=30
    )
    return json.loads(output) if output.strip() else None


def _api_list(endpoint: str) -> list[dict[str, Any]]:
    output = subprocess.check_output(
        ["gh", "api", "--paginate", "--slurp", endpoint],
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    pages = json.loads(output)
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise RuntimeError(f"authenticated provider response is not a paginated list: {endpoint}")
    return [item for page in pages for item in page if isinstance(item, dict)]


def _collaborator_evidence(owner_login: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for item in _api_list(f"repos/{REPOSITORY}/collaborators?per_page=100"):
        permissions = item.get("permissions", {})
        rows.append(
            {
                "login": str(item.get("login", "")),
                "role_name": str(item.get("role_name", "")),
                "permissions": {
                    name: permissions.get(name) is True for name in PERMISSIONS
                },
            }
        )
    rows.sort(key=lambda item: item["login"])
    eligible = sorted(
        item["login"]
        for item in rows
        if item["login"] != owner_login and item["permissions"]["push"]
    )
    return {
        "collaborators": rows,
        "eligible_independent_reviewers": eligible,
        "independent_reviewer_status": (
            "VERIFIED" if eligible else "OWNER_ACTION_REQUIRED"
        ),
    }


def _issue_evidence(operations: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for control in sorted(operations["critical_paths"], key=lambda item: item["issue"]["number"]):
        number = int(control["issue"]["number"])
        issue = _api(f"repos/{REPOSITORY}/issues/{number}")
        rows.append(
            {
                "control_id": str(control["id"]),
                "number": number,
                "url": str(issue.get("html_url", "")),
                "title": str(issue.get("title", "")),
                "state": str(issue.get("state", "")).upper(),
                "assignees": sorted(
                    str(item.get("login", ""))
                    for item in issue.get("assignees", [])
                    if isinstance(item, dict)
                ),
                "locked": issue.get("locked") is True,
            }
        )
    return rows


def _pull_request_evidence(contract: dict[str, Any]) -> dict[str, Any]:
    expected = contract["phase8_pull_request"]
    pull = _api(f"repos/{REPOSITORY}/pulls/{expected['number']}")
    return {
        "number": int(pull.get("number", 0)),
        "url": str(pull.get("html_url", "")),
        "base": str(pull.get("base", {}).get("ref", "")),
        "head": str(pull.get("head", {}).get("ref", "")),
        "state": str(pull.get("state", "")).upper(),
        "draft": pull.get("draft") is True,
        "merged": pull.get("merged") is True,
    }


def _phase8_evidence(
    contract: dict[str, Any], operations: dict[str, Any]
) -> dict[str, Any]:
    owner_login = str(contract["repository"]).partition("/")[0]
    collaborators = _collaborator_evidence(owner_login)
    conduct = next(
        item for item in operations["critical_paths"] if item["id"] == "security-intake"
    )
    return {
        **collaborators,
        "phase8_issues": _issue_evidence(operations),
        "phase8_pull_request": _pull_request_evidence(contract),
        "declared_blockers": {
            "independent_reviewer": contract["independent_reviewer"]["status"],
            "private_conduct_reporting": (
                "OWNER_ACTION_REQUIRED"
                if conduct["status"] == "BLOCKED_OWNER_ACTION"
                else "VERIFIED"
            ),
        },
    }


def _normalized_ruleset(
    ruleset: dict[str, Any], owner_snapshot: dict[str, Any] | None
) -> dict[str, Any]:
    rules = {item["type"]: item for item in ruleset["rules"]}
    pull_request = rules["pull_request"]["parameters"]
    status_checks = rules["required_status_checks"]["parameters"]
    if "bypass_actors" in ruleset:
        bypass_actor_count = len(ruleset["bypass_actors"])
    elif owner_snapshot is not None:
        bypass_actor_count = owner_snapshot["ruleset"]["bypass_actor_count"]
    else:
        raise RuntimeError("authenticated provider response omitted bypass actors")
    return {
        "name": ruleset["name"],
        "target": ruleset["target"],
        "enforcement": ruleset["enforcement"],
        "include": ruleset["conditions"]["ref_name"]["include"],
        "exclude": ruleset["conditions"]["ref_name"]["exclude"],
        "required_status_checks": status_checks["required_status_checks"],
        "strict_required_status_checks_policy": status_checks[
            "strict_required_status_checks_policy"
        ],
        "required_approving_review_count": pull_request["required_approving_review_count"],
        "dismiss_stale_reviews_on_push": pull_request["dismiss_stale_reviews_on_push"],
        "require_last_push_approval": pull_request["require_last_push_approval"],
        "required_review_thread_resolution": pull_request[
            "required_review_thread_resolution"
        ],
        "require_code_owner_review": pull_request["require_code_owner_review"],
        "allowed_merge_methods": pull_request["allowed_merge_methods"],
        "required_linear_history": "required_linear_history" in rules,
        "block_deletion": "deletion" in rules,
        "block_non_fast_forward": "non_fast_forward" in rules,
        "bypass_actor_count": bypass_actor_count,
    }


def _security_analysis(
    repository: dict[str, Any], owner_snapshot: dict[str, Any] | None
) -> dict[str, Any]:
    if owner_snapshot is None:
        return repository.get("security_and_analysis", {})
    return {
        name: {"status": "enabled" if owner_snapshot[name] else "disabled"}
        for name in (
            "dependabot_security_updates",
            "secret_scanning",
            "secret_scanning_push_protection",
        )
    }


def _source_endpoints(
    owner_snapshot: dict[str, Any] | None,
    operations: dict[str, Any],
    contract: dict[str, Any],
) -> list[str]:
    endpoints = [
        f"GET /repos/{REPOSITORY}",
        f"GET /repos/{REPOSITORY}/rulesets/{RULESET_ID}",
    ]
    if owner_snapshot is None:
        endpoints[1:1] = [
            f"GET /repos/{REPOSITORY}/private-vulnerability-reporting",
            f"GET /repos/{REPOSITORY}/vulnerability-alerts",
        ]
    endpoints.append(f"GET /repos/{REPOSITORY}/collaborators?per_page=100")
    endpoints.extend(
        f"GET /repos/{REPOSITORY}/issues/{item['issue']['number']}"
        for item in sorted(
            operations["critical_paths"], key=lambda item: item["issue"]["number"]
        )
    )
    endpoints.append(
        f"GET /repos/{REPOSITORY}/pulls/{contract['phase8_pull_request']['number']}"
    )
    return endpoints


def capture(
    owner_snapshot: dict[str, Any] | None = None,
    *,
    contract: dict[str, Any] | None = None,
    operations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or json.loads(
        (ROOT / "governance/github-controls.json").read_text(encoding="utf-8")
    )
    operations = operations or json.loads(
        (ROOT / "governance/repository-operations.json").read_text(encoding="utf-8")
    )
    actor = (
        {"login": os.environ.get("GITHUB_ACTOR")}
        if os.environ.get("GITHUB_ACTOR")
        else _api("user")
    )
    repository = _api(f"repos/{REPOSITORY}")
    if owner_snapshot is None:
        private_reporting = _api(f"repos/{REPOSITORY}/private-vulnerability-reporting")
        _api(f"repos/{REPOSITORY}/vulnerability-alerts")
    else:
        private_reporting = {"enabled": owner_snapshot["private_vulnerability_reporting"]}
    ruleset = _api(f"repos/{REPOSITORY}/rulesets/{RULESET_ID}")
    normalized_ruleset = _normalized_ruleset(ruleset, owner_snapshot)
    analysis = _security_analysis(repository, owner_snapshot)
    phase8 = _phase8_evidence(contract, operations)
    return {
        "schema_version": "3.0.0",
        "repository": REPOSITORY,
        "authenticated": True,
        "authenticated_actor": actor["login"],
        "capture_method": (
            "gh-api-live" if owner_snapshot is None else "gh-api-live-plus-fresh-owner-capture"
        ),
        "captured_at": dt.datetime.now(dt.UTC).replace(microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "default_branch": repository["default_branch"],
        "private_vulnerability_reporting": private_reporting["enabled"],
        "discussions": repository["has_discussions"],
        "vulnerability_alerts": (
            True if owner_snapshot is None else owner_snapshot["vulnerability_alerts"]
        ),
        "dependabot_security_updates": analysis.get("dependabot_security_updates", {}).get(
            "status"
        )
        == "enabled",
        "secret_scanning": analysis.get("secret_scanning", {}).get("status") == "enabled",
        "secret_scanning_push_protection": analysis.get(
            "secret_scanning_push_protection", {}
        ).get("status")
        == "enabled",
        "ruleset_id": ruleset["id"],
        "ruleset": normalized_ruleset,
        "source_endpoints": _source_endpoints(owner_snapshot, operations, contract),
        "live_fields": [
            "default_branch",
            "discussions",
            "ruleset_except_bypass_actor_count",
            "collaborators",
            "phase8_issues",
            "phase8_pull_request",
        ],
        "fresh_owner_capture_fields": (
            []
            if owner_snapshot is None
            else [
                "private_vulnerability_reporting",
                "vulnerability_alerts",
                "dependabot_security_updates",
                "secret_scanning",
                "secret_scanning_push_protection",
                "ruleset.bypass_actor_count",
            ]
        ),
        "owner_capture_at": None if owner_snapshot is None else owner_snapshot["captured_at"],
        **phase8,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ci-observable", action="store_true")
    args = parser.parse_args()
    contract = json.loads((ROOT / "governance/github-controls.json").read_text(encoding="utf-8"))
    operations = json.loads(
        (ROOT / "governance/repository-operations.json").read_text(encoding="utf-8")
    )
    owner_snapshot = None
    owner_errors: list[str] = []
    if args.ci_observable:
        owner_snapshot = json.loads(
            (ROOT / "evaluation/remediation/phase1-provider-evidence.json").read_text(
                encoding="utf-8"
            )
        )
        owner_errors = provider_state_errors(owner_snapshot, contract)
    snapshot = capture(owner_snapshot, contract=contract, operations=operations)
    errors = provider_state_errors(snapshot, contract, operations=operations)
    errors.extend(f"owner capture: {error}" for error in owner_errors)
    result = {**snapshot, "result": "PASS" if not errors else "FAIL", "errors": errors}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
