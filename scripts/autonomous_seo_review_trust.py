"""Trust-chain validation for WCSEO autonomous SEO review evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPOSITORY_FULL_NAME = "wfprieto/World-Class-SEO-Agent-System"
REQUIRED_REVIEWERS = {
    "senior-scrummaster-3": "SENIOR_SCRUMMASTER_3",
    "vp-engineering": "VP_ENGINEERING",
}
EXPECTED_ACTORS = {
    "senior-scrummaster-3": "claude[bot]",
    "vp-engineering": "chatgpt-codex-connector[bot]",
}
EXPECTED_PROVIDERS = {
    "senior-scrummaster-3": "GITHUB_CLAUDE_AGENT",
    "vp-engineering": "GITHUB_CODEX_AGENT",
}


def _safe_path(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _git_bytes(root: Path, arguments: list[str]) -> bytes | None:
    if not (root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout


def _working_tree_matches_candidate(root: Path, commit: str, relative: str) -> bool:
    if not (root / ".git").exists():
        return False
    try:
        result = subprocess.run(
            ["git", "diff", "--quiet", commit, "--", relative],
            cwd=root,
            check=False,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def git_commit_exists(root: Path, commit: str) -> bool:
    if len(commit) != 40 or not (root / ".git").exists():
        return False
    return _git_bytes(root, ["cat-file", "-e", f"{commit}^{{commit}}"] ) is not None


def candidate_blob_sha256(root: Path, commit: str, relative: str) -> str | None:
    if not git_commit_exists(root, commit):
        return None
    payload = _git_bytes(root, ["show", f"{commit}:{relative}"])
    if payload is None:
        return None
    return hashlib.sha256(payload).hexdigest()


def review_subject_hash(
    repository_full_name: str,
    pull_request_number: int,
    base_commit: str,
    candidate_commit: str,
    canonical_ci_run_id: int,
) -> str:
    payload = {
        "base_commit": base_commit,
        "candidate_commit": candidate_commit,
        "canonical_ci_run_id": canonical_ci_run_id,
        "pull_request_number": pull_request_number,
        "repository_full_name": repository_full_name,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def candidate_evidence_ref_errors(
    refs: list[dict[str, Any]], root: Path, candidate_commit: str
) -> list[str]:
    if not (root / ".git").exists():
        return ["candidate-bound evidence requires Git history"]
    if not git_commit_exists(root, candidate_commit):
        return [f"candidate commit does not exist: {candidate_commit}"]
    errors: list[str] = []
    for ref in refs:
        errors.extend(_one_candidate_evidence_error(ref, root, candidate_commit))
    return errors


def _one_candidate_evidence_error(
    ref: dict[str, Any], root: Path, candidate_commit: str
) -> list[str]:
    relative = str(ref.get("path", ""))
    path = _safe_path(root, relative)
    if path is None or not path.is_file():
        return [f"evidence path is missing or unsafe: {relative}"]
    if ref.get("bound_commit") != candidate_commit:
        return [f"evidence {relative} is not bound to candidate {candidate_commit}"]
    candidate_hash = candidate_blob_sha256(root, candidate_commit, relative)
    if candidate_hash is None:
        return [f"evidence {relative} does not exist at candidate {candidate_commit}"]
    errors: list[str] = []
    if ref.get("sha256") != candidate_hash:
        errors.append(f"candidate evidence hash mismatch: {relative}")
    if not _working_tree_matches_candidate(root, candidate_commit, relative):
        errors.append(f"evidence changed after candidate freeze: {relative}")
    return errors


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _schema_errors(payload: dict[str, Any], schema: dict[str, Any], label: str) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    return [
        f"{label} {'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(
            validator.iter_errors(payload),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        )
    ]


def reviewer_provenance_errors(
    closure: dict[str, Any], verdicts: list[dict[str, Any]], root: Path
) -> list[str]:
    files = closure.get("reviewer_provenance_files", [])
    if len(files) != 2:
        return ["closure requires exactly two live-authentication provenance manifests"]
    schema = _load(root / "schemas" / "autonomous-seo-reviewer-provenance.schema.json")
    receipts, errors = _load_provenance_files(files, schema, root)
    if errors:
        return errors
    return _provenance_identity_errors(closure, verdicts, receipts)


def _load_provenance_files(
    files: list[Any], schema: dict[str, Any], root: Path
) -> tuple[list[dict[str, Any]], list[str]]:
    receipts: list[dict[str, Any]] = []
    errors: list[str] = []
    for relative in files:
        path = _safe_path(root, str(relative))
        if path is None or not path.is_file():
            errors.append(f"reviewer provenance file is missing or unsafe: {relative}")
            continue
        receipt = _load(path)
        errors.extend(_schema_errors(receipt, schema, f"review provenance {relative}"))
        receipts.append(receipt)
    return receipts, errors


def _provenance_identity_errors(
    closure: dict[str, Any], verdicts: list[dict[str, Any]], receipts: list[dict[str, Any]]
) -> list[str]:
    verdict_map = {str(item.get("reviewer_id")): item for item in verdicts}
    receipt_map = {str(item.get("reviewer_id")): item for item in receipts}
    if set(receipt_map) != set(REQUIRED_REVIEWERS):
        return ["review provenance must cover both canonical reviewer identities"]
    errors = _execution_identity_errors(receipts)
    for reviewer_id, receipt in receipt_map.items():
        errors.extend(_receipt_identity_errors(reviewer_id, receipt, verdict_map.get(reviewer_id, {})))
        errors.extend(_receipt_binding_errors(reviewer_id, receipt, closure))
    return errors


def _execution_identity_errors(receipts: list[dict[str, Any]]) -> list[str]:
    executions = {str(item.get("execution_id")) for item in receipts}
    triggers = {int(item.get("trigger_comment_id", 0)) for item in receipts}
    results = {(str(item.get("result_kind")), int(item.get("result_id", 0))) for item in receipts}
    pull_requests = {int(item.get("pull_request_number", 0)) for item in receipts}
    errors: list[str] = []
    if len(executions) != 2:
        errors.append("review provenance execution IDs must be distinct")
    if len(triggers) != 2:
        errors.append("review provenance trigger comments must be distinct")
    if len(results) != 2:
        errors.append("review provenance result identities must be distinct")
    if len(pull_requests) != 1 or next(iter(pull_requests), 0) < 1:
        errors.append("review provenance must bind both reviewers to one positive pull request number")
    return errors


def _receipt_identity_errors(
    reviewer_id: str, receipt: dict[str, Any], verdict: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if receipt.get("role") != REQUIRED_REVIEWERS[reviewer_id]:
        errors.append(f"review provenance role mismatch: {reviewer_id}")
    if receipt.get("provider") != EXPECTED_PROVIDERS[reviewer_id]:
        errors.append(f"review provenance provider mismatch: {reviewer_id}")
    if receipt.get("result_actor_login") != EXPECTED_ACTORS[reviewer_id]:
        errors.append(f"review provenance actor mismatch: {reviewer_id}")
    for field in ("context_id", "provider", "model"):
        if receipt.get(field) != verdict.get(field):
            errors.append(f"review provenance {field} mismatch: {reviewer_id}")
    return errors


def _receipt_binding_errors(
    reviewer_id: str, receipt: dict[str, Any], closure: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if receipt.get("repository_full_name") != REPOSITORY_FULL_NAME:
        errors.append(f"review provenance repository mismatch: {reviewer_id}")
    if int(receipt.get("pull_request_number", 0)) < 1:
        errors.append(f"review provenance PR must be positive: {reviewer_id}")
    if receipt.get("candidate_commit") != closure.get("candidate_commit"):
        errors.append(f"review provenance candidate mismatch: {reviewer_id}")
    if receipt.get("evidence_package_hash") != closure.get("evidence_package_hash"):
        errors.append(f"review provenance evidence hash mismatch: {reviewer_id}")
    if receipt.get("context_id") == closure.get("builder_context_id"):
        errors.append(f"review provenance reuses builder context: {reviewer_id}")
    if receipt.get("verification_state") != "REQUIRES_LIVE_VERIFICATION":
        errors.append(f"review provenance may not self-assert VERIFIED: {reviewer_id}")
    return errors
