#!/usr/bin/env python3
"""Plan or explicitly execute exact Phase 1 GitHub-provider rollback."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
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
    "secret_scanning",
    "secret_scanning_push_protection",
}
RESTORED_FIELDS = (
    "default_branch",
    "private_vulnerability_reporting",
    "discussions",
    "vulnerability_alerts",
    "dependabot_security_updates",
    "secret_scanning",
    "secret_scanning_push_protection",
    "ruleset_id",
    "ruleset",
)


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
        "secret_scanning",
        "secret_scanning_push_protection",
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


def apply_plan(
    plan: dict[str, Any],
    baseline: dict[str, Any],
    *,
    gh_call: Any = _gh,
    applied: list[str] | None = None,
) -> list[str]:
    applied = [] if applied is None else applied
    for change in plan["changes"]:
        setting = change["setting"]
        restore = change["restore"]
        if setting == "discussions":
            gh_call("PATCH", f"repos/{REPOSITORY}", {"has_discussions": restore})
        elif setting == "private_vulnerability_reporting":
            gh_call("PUT" if restore else "DELETE", f"repos/{REPOSITORY}/private-vulnerability-reporting")
        elif setting == "vulnerability_alerts":
            gh_call("PUT" if restore else "DELETE", f"repos/{REPOSITORY}/vulnerability-alerts")
        elif setting == "dependabot_security_updates":
            gh_call("PUT" if restore else "DELETE", f"repos/{REPOSITORY}/automated-security-fixes")
        elif setting in {"secret_scanning", "secret_scanning_push_protection"}:
            gh_call(
                "PATCH",
                f"repos/{REPOSITORY}",
                {"security_and_analysis": {setting: {"status": "enabled" if restore else "disabled"}}},
            )
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
            gh_call("PUT", f"repos/{REPOSITORY}/rulesets/{RULESET_ID}", payload)
        applied.append(setting)
    return applied


def restored_state_errors(
    baseline: dict[str, Any],
    observed: dict[str, Any],
    *,
    now: dt.datetime | None = None,
) -> list[str]:
    errors: list[str] = []
    if observed.get("repository") != REPOSITORY:
        errors.append("post-restore capture repository does not match rollback target")
    for field in RESTORED_FIELDS:
        if field not in observed:
            errors.append(f"post-restore capture is missing {field}")
        elif observed.get(field) != baseline.get(field):
            errors.append(f"post-restore {field} does not match baseline")
    if observed.get("authenticated") is not True:
        errors.append("post-restore capture is not authenticated")
    if not isinstance(observed.get("authenticated_actor"), str):
        errors.append("post-restore capture does not identify its authenticated actor")
    if observed.get("capture_method") != "gh-api-live":
        errors.append("post-restore capture must use live owner-authenticated GitHub APIs")
    captured_at = observed.get("captured_at")
    try:
        captured = dt.datetime.strptime(str(captured_at), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.UTC
        )
    except ValueError:
        errors.append("post-restore capture requires a UTC captured_at timestamp")
    else:
        current = now or dt.datetime.now(dt.UTC)
        age = current - captured
        if age < dt.timedelta(minutes=-1) or age > dt.timedelta(minutes=5):
            errors.append("post-restore capture is outside the five-minute verification window")
    return errors


def execute_verified_rollback(
    plan: dict[str, Any],
    baseline: dict[str, Any],
    *,
    capture_call: Any,
    gh_call: Any = _gh,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": "1.0.0",
        "repository": REPOSITORY,
        "mode": "APPLY_AND_VERIFY",
        "baseline_sha256": hashlib.sha256(
            json.dumps(baseline, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "planned_settings": [change["setting"] for change in plan["changes"]],
        "applied_settings": [],
        "post_restore_capture": None,
        "errors": [],
        "result": "FAIL",
    }
    try:
        apply_plan(
            plan,
            baseline,
            gh_call=gh_call,
            applied=receipt["applied_settings"],
        )
    except Exception as exc:
        receipt["errors"] = [f"provider mutation failed: {exc}"]
        receipt["result"] = "FAIL_PARTIAL_APPLICATION"
        return receipt
    try:
        observed = capture_call()
    except Exception as exc:
        receipt["errors"] = [f"post-restore capture failed: {exc}"]
        receipt["result"] = "FAIL_POST_RESTORE_CAPTURE"
        return receipt
    receipt["post_restore_capture"] = observed
    receipt["errors"] = restored_state_errors(baseline, observed)
    receipt["result"] = "PASS" if not receipt["errors"] else "FAIL_POST_RESTORE_MISMATCH"
    return receipt


def authorize_apply(
    *, confirm_repository: str | None, allow_security_downgrade: bool, authorization: str | None
) -> None:
    if confirm_repository != REPOSITORY:
        raise RuntimeError("exact repository confirmation is required")
    if not allow_security_downgrade:
        raise RuntimeError("exact rollback requires --allow-security-downgrade")
    if authorization != "YES":
        raise RuntimeError("owner incident authorization is required")


def _live_capture() -> dict[str, Any]:
    from scripts.capture_github_controls import capture

    return capture()


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
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-security-downgrade", action="store_true")
    parser.add_argument("--confirm-repository")
    args = parser.parse_args()
    baseline = _load(args.baseline)
    current = _load(args.current)
    plan = build_plan(baseline, current)
    if args.apply:
        authorize_apply(
            confirm_repository=args.confirm_repository,
            allow_security_downgrade=args.allow_security_downgrade,
            authorization=os.environ.get("WCSEO_PROVIDER_ROLLBACK_AUTHORIZED"),
        )
        if args.receipt is None:
            raise RuntimeError("--receipt is required for an applied rollback")
        receipt = execute_verified_rollback(plan, baseline, capture_call=_live_capture)
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(receipt, indent=2))
        return 0 if receipt["result"] == "PASS" else 1
    if args.receipt is not None:
        raise RuntimeError("--receipt is valid only with --apply")
    if args.output:
        args.output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
