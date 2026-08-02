#!/usr/bin/env python3
"""Plan or explicitly execute exact Phase 1 GitHub-provider rollback."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "wfprieto/World-Class-SEO-Agent-System"
RULESET_ID = 18955880
SECURITY_ENABLEMENTS = {
    "private_vulnerability_reporting",
    "vulnerability_alerts",
    "dependabot_security_updates",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def build_plan(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    if baseline.get("repository") != REPOSITORY or current.get("repository") != REPOSITORY:
        raise ValueError("provider evidence repository does not match the rollback target")
    changes: list[dict[str, Any]] = []
    for setting in (
        "private_vulnerability_reporting",
        "discussions",
        "vulnerability_alerts",
        "dependabot_security_updates",
        "ruleset",
    ):
        before = baseline.get(setting)
        after = current.get(setting)
        if before != after:
            changes.append(
                {
                    "setting": setting,
                    "current": after,
                    "restore": before,
                    "security_downgrade": setting in SECURITY_ENABLEMENTS
                    or setting == "ruleset",
                }
            )
    return {
        "schema_version": "1.0.0",
        "repository": REPOSITORY,
        "mode": "DRY_RUN",
        "baseline_capture_window_end": baseline.get("capture_window_end"),
        "current_capture_at": current.get("captured_at"),
        "changes": changes,
        "apply_preconditions": [
            f"--confirm-repository {REPOSITORY}",
            "--allow-security-downgrade",
            "WCSEO_PROVIDER_ROLLBACK_AUTHORIZED=YES",
            "clean owner-authorized incident window",
            "fresh post-restore capture must match the baseline",
        ],
        "result": "PASS",
    }


def _gh(method: str, endpoint: str, payload: dict[str, Any] | None = None) -> None:
    command = ["gh", "api", "--method", method, endpoint]
    if payload is not None:
        command.extend(["--input", "-"])
    subprocess.run(
        command,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        check=True,
        timeout=30,
    )


def apply_plan(plan: dict[str, Any], baseline: dict[str, Any]) -> None:
    for change in plan["changes"]:
        setting = change["setting"]
        restore = change["restore"]
        if setting == "discussions":
            _gh("PATCH", f"repos/{REPOSITORY}", {"has_discussions": restore})
        elif setting == "private_vulnerability_reporting":
            _gh("PUT" if restore else "DELETE", f"repos/{REPOSITORY}/private-vulnerability-reporting")
        elif setting == "vulnerability_alerts":
            _gh("PUT" if restore else "DELETE", f"repos/{REPOSITORY}/vulnerability-alerts")
        elif setting == "dependabot_security_updates":
            _gh("PUT" if restore else "DELETE", f"repos/{REPOSITORY}/automated-security-fixes")
        elif setting == "ruleset":
            ruleset = baseline["ruleset"]
            payload = {
                "name": ruleset["name"],
                "target": ruleset["target"],
                "enforcement": ruleset["enforcement"],
                "bypass_actors": [],
                "conditions": {
                    "ref_name": {"include": ruleset["include"], "exclude": ruleset["exclude"]}
                },
                "rules": [
                    {"type": "deletion"},
                    {"type": "non_fast_forward"},
                    {
                        "type": "pull_request",
                        "parameters": {
                            key: ruleset[key]
                            for key in (
                                "required_approving_review_count",
                                "dismiss_stale_reviews_on_push",
                                "require_code_owner_review",
                                "require_last_push_approval",
                                "required_review_thread_resolution",
                                "allowed_merge_methods",
                            )
                        }
                        | {"required_reviewers": []},
                    },
                    {
                        "type": "required_status_checks",
                        "parameters": {
                            "strict_required_status_checks_policy": ruleset[
                                "strict_required_status_checks_policy"
                            ],
                            "do_not_enforce_on_create": False,
                            "required_status_checks": ruleset["required_status_checks"],
                        },
                    },
                    {"type": "required_linear_history"},
                ],
            }
            _gh("PUT", f"repos/{REPOSITORY}/rulesets/{RULESET_ID}", payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "evaluation/remediation/phase1-provider-baseline.json",
    )
    parser.add_argument(
        "--current",
        type=Path,
        default=ROOT / "evaluation/remediation/phase1-provider-evidence.json",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-security-downgrade", action="store_true")
    parser.add_argument("--confirm-repository")
    args = parser.parse_args()
    baseline = _load(args.baseline)
    current = _load(args.current)
    plan = build_plan(baseline, current)
    if args.apply:
        if args.confirm_repository != REPOSITORY:
            raise RuntimeError("exact repository confirmation is required")
        if not args.allow_security_downgrade:
            raise RuntimeError("exact rollback requires --allow-security-downgrade")
        if os.environ.get("WCSEO_PROVIDER_ROLLBACK_AUTHORIZED") != "YES":
            raise RuntimeError("owner incident authorization is required")
        apply_plan(plan, baseline)
        plan["mode"] = "APPLIED_REQUIRES_POST_RESTORE_VERIFICATION"
    if args.output:
        args.output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
