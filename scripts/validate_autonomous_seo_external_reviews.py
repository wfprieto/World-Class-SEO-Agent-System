"""Live-authenticate autonomous SEO reviewer provenance against GitHub.

Repository provenance manifests are pointers to external evidence. They never
self-authorize a reviewer. This validator is the trust root and must run with a
GitHub token in the provider-authentication CI job before repository
certification can pass a completed phase.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts import autonomous_seo_phase_closure as phase_closure
from scripts import autonomous_seo_review_trust as trust

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = "https://api.github.com"
EXPECTED_MODELS = {
    "senior-scrummaster-3": "github-claude-agent",
    "vp-engineering": "github-codex-agent",
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _api_json(path: str, token: str) -> Any:
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "wcseo-external-review-verifier",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub provider lookup failed for {path}: {exc}") from exc


def _iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _expected_execution_id(receipt: dict[str, Any]) -> str:
    kind = str(receipt["result_kind"]).lower().replace("_", "-")
    return f"github:{kind}:{int(receipt['result_id'])}"


def _review_package_hash(receipt: dict[str, Any]) -> str:
    return trust.review_subject_hash(
        str(receipt["repository_full_name"]),
        int(receipt["pull_request_number"]),
        str(receipt["base_commit"]),
        str(receipt["candidate_commit"]),
        int(receipt["canonical_ci_run_id"]),
    )


def _subject_errors(receipt: dict[str, Any], verdict: dict[str, Any]) -> list[str]:
    reviewer_id = str(receipt["reviewer_id"])
    errors: list[str] = []
    if receipt["evidence_package_hash"] != _review_package_hash(receipt):
        errors.append(f"external review package hash mismatch: {reviewer_id}")
    if receipt["execution_id"] != _expected_execution_id(receipt):
        errors.append(f"external review execution ID is not provider-derived: {reviewer_id}")
    if receipt["context_id"] != receipt["execution_id"]:
        errors.append(f"external review context is not provider-derived: {reviewer_id}")
    if receipt["model"] != EXPECTED_MODELS[reviewer_id]:
        errors.append(f"external review model identifier mismatch: {reviewer_id}")
    if verdict.get("verdict") != "APPROVE_GREAT":
        errors.append(f"external reviewer did not APPROVE_GREAT: {reviewer_id}")
    return errors


def _pr_and_run_errors(receipt: dict[str, Any], token: str) -> tuple[list[str], dict[str, Any]]:
    repository = str(receipt["repository_full_name"])
    pr_number = int(receipt["pull_request_number"])
    candidate = str(receipt["candidate_commit"])
    run_id = int(receipt["canonical_ci_run_id"])
    pr = _api_json(f"/repos/{repository}/pulls/{pr_number}", token)
    run = _api_json(f"/repos/{repository}/actions/runs/{run_id}", token)
    errors: list[str] = []
    if pr.get("base", {}).get("sha") != receipt["base_commit"]:
        errors.append("external review PR base does not match receipt")
    if run.get("head_sha") != candidate:
        errors.append("external review canonical CI run is not bound to candidate")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        errors.append("external review canonical CI run is not completed/success")
    if run.get("name") != "Validate repository":
        errors.append("external review canonical CI run has wrong workflow name")
    return errors, run


def _trigger_errors(
    receipt: dict[str, Any], token: str, run: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    repository = str(receipt["repository_full_name"])
    trigger_id = int(receipt["trigger_comment_id"])
    trigger = _api_json(f"/repos/{repository}/issues/comments/{trigger_id}", token)
    body = str(trigger.get("body", ""))
    errors: list[str] = []
    if trigger.get("user", {}).get("login") != "wfprieto":
        errors.append("external review trigger is not owned by repository owner")
    for required in (
        str(receipt["candidate_commit"]),
        str(receipt["canonical_ci_run_id"]),
        str(receipt["evidence_package_hash"]),
    ):
        if required not in body:
            errors.append(f"external review trigger omits bound subject: {required}")
    agent = "@claude" if receipt["reviewer_id"] == "senior-scrummaster-3" else "@codex"
    if agent not in body.lower():
        errors.append(f"external review trigger omits expected agent: {agent}")
    if run.get("updated_at") and trigger.get("created_at"):
        if _iso(str(trigger["created_at"])) < _iso(str(run["updated_at"])):
            errors.append("external review was triggered before canonical CI completed")
    return errors, trigger


def _issue_comment_result(
    receipt: dict[str, Any], verdict: dict[str, Any], token: str
) -> tuple[list[str], dict[str, Any]]:
    repository = str(receipt["repository_full_name"])
    result = _api_json(f"/repos/{repository}/issues/comments/{int(receipt['result_id'])}", token)
    body = str(result.get("body", ""))
    errors: list[str] = []
    if result.get("user", {}).get("login") != receipt["result_actor_login"]:
        errors.append("external review result actor mismatch")
    for required in (
        str(receipt["candidate_commit"]),
        str(receipt["canonical_ci_run_id"]),
        str(receipt["evidence_package_hash"]),
        str(verdict["verdict"]),
    ):
        if required not in body:
            errors.append(f"external review result omits bound subject: {required}")
    return errors, result


def _review_result(
    receipt: dict[str, Any], verdict: dict[str, Any], token: str
) -> tuple[list[str], dict[str, Any]]:
    repository = str(receipt["repository_full_name"])
    pr_number = int(receipt["pull_request_number"])
    result = _api_json(
        f"/repos/{repository}/pulls/{pr_number}/reviews/{int(receipt['result_id'])}", token
    )
    errors: list[str] = []
    if result.get("user", {}).get("login") != receipt["result_actor_login"]:
        errors.append("external review result actor mismatch")
    if result.get("commit_id") != receipt["candidate_commit"]:
        errors.append("external pull-request review is not bound to candidate")
    if verdict["verdict"] != "APPROVE_GREAT" or result.get("state") != "APPROVED":
        errors.append("external pull-request review is not an authenticated approval")
    return errors, result


def _reaction_result(
    receipt: dict[str, Any], verdict: dict[str, Any], token: str
) -> tuple[list[str], dict[str, Any]]:
    repository = str(receipt["repository_full_name"])
    trigger_id = int(receipt["trigger_comment_id"])
    reactions = _api_json(
        f"/repos/{repository}/issues/comments/{trigger_id}/reactions?per_page=100", token
    )
    result = next(
        (item for item in reactions if int(item.get("id", 0)) == int(receipt["result_id"])),
        {},
    )
    errors: list[str] = []
    if result.get("user", {}).get("login") != receipt["result_actor_login"]:
        errors.append("external review reaction actor mismatch")
    if result.get("content") != "+1" or verdict["verdict"] != "APPROVE_GREAT":
        errors.append("external review reaction is not an authenticated approval")
    return errors, result


def _result_errors(
    receipt: dict[str, Any], verdict: dict[str, Any], token: str
) -> tuple[list[str], dict[str, Any]]:
    kind = receipt["result_kind"]
    if kind == "ISSUE_COMMENT":
        return _issue_comment_result(receipt, verdict, token)
    if kind == "PULL_REQUEST_REVIEW":
        return _review_result(receipt, verdict, token)
    return _reaction_result(receipt, verdict, token)


def _time_errors(
    receipt: dict[str, Any], trigger: dict[str, Any], result: dict[str, Any]
) -> list[str]:
    result_time = result.get("created_at") or result.get("submitted_at")
    if not result_time or not trigger.get("created_at"):
        return ["external review provider timestamps are unavailable"]
    errors: list[str] = []
    if _iso(str(result_time)) < _iso(str(trigger["created_at"])):
        errors.append("external review result predates its trigger")
    if _iso(str(receipt["submitted_at"])) != _iso(str(result_time)):
        errors.append("external review receipt timestamp is not provider-derived")
    return errors


def _authenticate_one(
    receipt: dict[str, Any], verdict: dict[str, Any], token: str
) -> list[str]:
    errors = _subject_errors(receipt, verdict)
    pr_errors, run = _pr_and_run_errors(receipt, token)
    trigger_errors, trigger = _trigger_errors(receipt, token, run)
    result_errors, result = _result_errors(receipt, verdict, token)
    errors.extend(pr_errors)
    errors.extend(trigger_errors)
    errors.extend(result_errors)
    errors.extend(_time_errors(receipt, trigger, result))
    return errors


def validate_live_external_reviews(root: Path, token: str) -> list[str]:
    program_path = root / phase_closure.PROGRAM_RELATIVE
    if not program_path.is_file():
        return ["autonomous SEO program is missing"]
    program = _load(program_path)
    completed = [phase for phase in program.get("phases", []) if phase.get("status") == "COMPLETE"]
    if not completed:
        return []
    errors: list[str] = []
    for phase in completed:
        phase_id = str(phase["id"])
        closure_path = phase_closure.closure_path(root, phase_id)
        if not closure_path.is_file():
            errors.append(f"{phase_id} external review closure is missing")
            continue
        closure = _load(closure_path)
        verdicts = [_load(root / str(item)) for item in closure["reviewer_verdict_files"]]
        receipts = [_load(root / str(item)) for item in closure["reviewer_provenance_files"]]
        verdict_map = {str(item["reviewer_id"]): item for item in verdicts}
        for receipt in receipts:
            reviewer_id = str(receipt["reviewer_id"])
            errors.extend(_authenticate_one(receipt, verdict_map[reviewer_id], token))
    return errors


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print(json.dumps({"status": "FAIL", "errors": ["GITHUB_TOKEN is required"]}))
        return 1
    try:
        errors = validate_live_external_reviews(ROOT, token)
    except (KeyError, ValueError, RuntimeError) as exc:
        errors = [str(exc)]
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
