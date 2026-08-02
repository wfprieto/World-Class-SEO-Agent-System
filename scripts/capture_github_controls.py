#!/usr/bin/env python3
"""Capture and fail-closed verify live GitHub repository governance controls."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.validate_repository_governance import provider_state_errors  # noqa: E402


REPOSITORY = "wfprieto/World-Class-SEO-Agent-System"
RULESET_ID = 18955880


def _api(endpoint: str) -> Any:
    output = subprocess.check_output(
        ["gh", "api", endpoint], text=True, encoding="utf-8", timeout=30
    )
    return json.loads(output) if output.strip() else None


def capture() -> dict[str, Any]:
    actor = _api("user")
    repository = _api(f"repos/{REPOSITORY}")
    private_reporting = _api(f"repos/{REPOSITORY}/private-vulnerability-reporting")
    _api(f"repos/{REPOSITORY}/vulnerability-alerts")
    ruleset = _api(f"repos/{REPOSITORY}/rulesets/{RULESET_ID}")
    rules = {item["type"]: item for item in ruleset["rules"]}
    pull_request = rules["pull_request"]["parameters"]
    status_checks = rules["required_status_checks"]["parameters"]
    analysis = repository.get("security_and_analysis", {})
    return {
        "schema_version": "2.0.0",
        "repository": REPOSITORY,
        "authenticated": True,
        "authenticated_actor": actor["login"],
        "capture_method": "gh-api-live",
        "captured_at": dt.datetime.now(dt.UTC).replace(microsecond=0).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "default_branch": repository["default_branch"],
        "private_vulnerability_reporting": private_reporting["enabled"],
        "discussions": repository["has_discussions"],
        "vulnerability_alerts": True,
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
        "ruleset": {
            "name": ruleset["name"],
            "target": ruleset["target"],
            "enforcement": ruleset["enforcement"],
            "include": ruleset["conditions"]["ref_name"]["include"],
            "exclude": ruleset["conditions"]["ref_name"]["exclude"],
            "required_status_checks": status_checks["required_status_checks"],
            "strict_required_status_checks_policy": status_checks[
                "strict_required_status_checks_policy"
            ],
            "required_approving_review_count": pull_request[
                "required_approving_review_count"
            ],
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
            "bypass_actor_count": len(ruleset["bypass_actors"]),
        },
        "source_endpoints": [
            f"GET /repos/{REPOSITORY}",
            f"GET /repos/{REPOSITORY}/private-vulnerability-reporting",
            f"GET /repos/{REPOSITORY}/vulnerability-alerts",
            f"GET /repos/{REPOSITORY}/rulesets/{RULESET_ID}",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    snapshot = capture()
    contract = json.loads((ROOT / "governance/github-controls.json").read_text(encoding="utf-8"))
    errors = provider_state_errors(snapshot, contract)
    result = {**snapshot, "result": "PASS" if not errors else "FAIL", "errors": errors}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
