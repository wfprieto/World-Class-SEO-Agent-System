"""Per-phase closure validation for autonomous SEO expansion."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts import autonomous_seo_review_trust as trust

PROGRAM_RELATIVE = "evaluation/remediation/autonomous-seo-expansion-program.json"
REQUIRED_REVIEWERS = trust.REQUIRED_REVIEWERS


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def schema_errors(payload: dict[str, Any], schema: dict[str, Any], label: str = "schema") -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    return [
        f"{label} {'.'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_stdout(root: Path, arguments: list[str]) -> str | None:
    result = _run_git(root, arguments)
    if result is None:
        return None
    value = result.stdout.strip()
    return value or None


def git_command_ok(root: Path, arguments: list[str]) -> bool:
    return _run_git(root, arguments) is not None


def _run_git(root: Path, arguments: list[str]) -> subprocess.CompletedProcess[str] | None:
    if not (root / ".git").exists():
        return None
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def safe_repo_path(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def evidence_ref_errors(refs: list[dict[str, Any]], root: Path, candidate_commit: str) -> list[str]:
    return trust.candidate_evidence_ref_errors(refs, root, candidate_commit)


def reviewer_file_errors(closure: dict[str, Any], root: Path) -> list[str]:
    reviewer_schema = load_object(root / "schemas" / "reviewer-verdict.schema.json")
    verdicts: list[dict[str, Any]] = []
    errors: list[str] = []
    for relative in closure.get("reviewer_verdict_files", []):
        path = safe_repo_path(root, str(relative))
        if path is None or not path.is_file():
            errors.append(f"reviewer verdict file is missing or unsafe: {relative}")
            continue
        verdict = load_object(path)
        errors.extend(schema_errors(verdict, reviewer_schema, f"reviewer {relative}"))
        verdicts.append(verdict)
    if errors:
        return errors
    errors.extend(reviewer_independence_errors(closure, verdicts))
    errors.extend(trust.reviewer_provenance_errors(closure, verdicts, root))
    return errors


def reviewer_independence_errors(closure: dict[str, Any], verdicts: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(verdicts) != 2:
        return ["phase closure requires exactly two reviewer verdicts"]
    ids = {str(item.get("reviewer_id")): str(item.get("role")) for item in verdicts}
    if ids != REQUIRED_REVIEWERS:
        errors.append(f"phase closure reviewers must be {REQUIRED_REVIEWERS}; found {ids}")
    contexts = [str(item.get("context_id")) for item in verdicts]
    if len(set(contexts)) != 2 or closure.get("builder_context_id") in contexts:
        errors.append("reviewer contexts must be distinct and different from builder context")
    expected_hash = closure.get("evidence_package_hash")
    if any(item.get("evidence_package_hash") != expected_hash for item in verdicts):
        errors.append("both reviewers must review the exact phase evidence package hash")
    if any(item.get("verdict") != "APPROVE_GREAT" for item in verdicts):
        errors.append("both independent reviewers must return APPROVE_GREAT")
    return errors


def closure_evidence_payload(closure: dict[str, Any]) -> dict[str, Any]:
    included = (
        "program_id",
        "phase_id",
        "candidate_commit",
        "builder_context_id",
        "apivr",
        "twenty_pass",
        "rollback",
        "technical_verification",
        "outcome_verification",
        "unexpected_change_scan",
        "security_review",
        "documentation_review",
        "evidence_refs",
    )
    return {key: closure[key] for key in included}


def closure_hash_errors(closure: dict[str, Any]) -> list[str]:
    expected = canonical_hash(closure_evidence_payload(closure))
    if closure.get("evidence_package_hash") == expected:
        return []
    return ["phase closure evidence_package_hash does not match its canonical evidence payload"]


def closure_path(root: Path, phase_id: str) -> Path:
    name = f"autonomous-seo-expansion-{phase_id.lower()}-closure.json"
    return root / "evaluation" / "remediation" / name


def phase_closure_errors(phase: dict[str, Any], root: Path, policy: dict[str, Any]) -> list[str]:
    phase_id = str(phase.get("id"))
    path = closure_path(root, phase_id)
    if not path.is_file():
        return [f"{phase_id} cannot be COMPLETE without {path.relative_to(root)}"]
    closure = load_object(path)
    schema = load_object(root / "schemas" / "autonomous-seo-phase-closure.schema.json")
    errors = schema_errors(closure, schema, f"{phase_id} closure")
    if errors:
        return errors
    candidate = str(closure.get("candidate_commit"))
    errors.extend(closure_hash_errors(closure))
    errors.extend(_all_evidence_errors(closure, root, candidate))
    errors.extend(_closure_identity_errors(phase, closure, root, policy))
    errors.extend(reviewer_file_errors(closure, root))
    return errors


def _all_evidence_errors(closure: dict[str, Any], root: Path, candidate: str) -> list[str]:
    refs = list(closure.get("evidence_refs", []))
    refs.extend(closure.get("rollback", {}).get("evidence_refs", []))
    refs.extend(closure.get("technical_verification", {}).get("evidence_refs", []))
    refs.extend(closure.get("outcome_verification", {}).get("evidence_refs", []))
    return evidence_ref_errors(refs, root, candidate)


def _closure_identity_errors(
    phase: dict[str, Any], closure: dict[str, Any], root: Path, policy: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase.get("id"))
    candidate = str(closure.get("candidate_commit"))
    if closure.get("phase_id") != phase_id:
        errors.append(f"{phase_id} closure phase_id does not match")
    if (root / ".git").exists():
        errors.extend(_reviewed_candidate_errors(root, phase_id, candidate, closure, policy))
    required = set(policy.get("outcome_pass_required_phases", []))
    if phase_id in required and closure.get("outcome_verification", {}).get("state") != "PASS":
        errors.append(f"{phase_id} requires outcome_verification PASS before closure")
    return errors


def _reviewed_candidate_errors(
    root: Path, phase_id: str, candidate: str, closure: dict[str, Any], policy: dict[str, Any]
) -> list[str]:
    if not trust.git_commit_exists(root, candidate):
        return [f"{phase_id} closure candidate_commit must identify an existing commit"]
    if not git_command_ok(root, ["merge-base", "--is-ancestor", candidate, "HEAD"]):
        return [f"{phase_id} closure candidate_commit must be an ancestor of final HEAD"]
    errors = _post_review_file_errors(root, phase_id, candidate, closure)
    errors.extend(_program_transition_errors(root, phase_id, candidate, policy))
    return errors


def _post_review_file_errors(
    root: Path, phase_id: str, candidate: str, closure: dict[str, Any]
) -> list[str]:
    changed = git_stdout(root, ["diff", "--name-only", f"{candidate}..HEAD"])
    paths = [] if not changed else changed.splitlines()
    allowed = {
        PROGRAM_RELATIVE,
        "evaluation/remediation/autonomous-seo-expansion-ledger.md",
        f"evaluation/remediation/autonomous-seo-expansion-{phase_id.lower()}-closure.json",
    }
    allowed.update(str(item) for item in closure.get("reviewer_verdict_files", []))
    allowed.update(str(item) for item in closure.get("reviewer_provenance_files", []))
    unexpected = sorted(path for path in paths if path not in allowed)
    return [] if not unexpected else [f"{phase_id} has post-review source drift: {unexpected}"]


def _program_at_commit(root: Path, commit: str) -> dict[str, Any] | None:
    content = git_stdout(root, ["show", f"{commit}:{PROGRAM_RELATIVE}"])
    if content is None:
        return None
    payload = json.loads(content)
    return payload if isinstance(payload, dict) else None


def _program_transition_errors(
    root: Path, phase_id: str, candidate: str, policy: dict[str, Any]
) -> list[str]:
    before = _program_at_commit(root, candidate)
    after_path = root / PROGRAM_RELATIVE
    if before is None or not after_path.is_file():
        return ["cannot compare reviewed and final program state"]
    after = load_object(after_path)
    return field_bounded_transition_errors(before, after, phase_id, policy)


def field_bounded_transition_errors(
    before: dict[str, Any], after: dict[str, Any], phase_id: str, policy: dict[str, Any]
) -> list[str]:
    transition = policy["post_review_program_transition"]
    errors = _immutable_program_errors(before, after, transition)
    errors.extend(_phase_transition_errors(before, after, phase_id, policy))
    errors.extend(_lane_transition_errors(before, after, transition))
    return errors


def _immutable_program_errors(
    before: dict[str, Any], after: dict[str, Any], transition: dict[str, Any]
) -> list[str]:
    return [
        f"post-review immutable program field changed: {field}"
        for field in transition["immutable_fields"]
        if before.get(field) != after.get(field)
    ]


def _phase_transition_errors(
    before: dict[str, Any], after: dict[str, Any], phase_id: str, policy: dict[str, Any]
) -> list[str]:
    order = list(policy["phase_order"])
    before_map = {item["id"]: item for item in before["phases"]}
    after_map = {item["id"]: item for item in after["phases"]}
    if set(before_map) != set(after_map):
        return ["post-review phase set changed"]
    errors = _immutable_phase_errors(before_map, after_map, policy)
    errors.extend(_reviewed_and_next_phase_errors(before, after, before_map, after_map, phase_id, policy))
    errors.extend(_unreviewed_phase_errors(before_map, after_map, phase_id, order))
    return errors


def _immutable_phase_errors(
    before_map: dict[str, dict[str, Any]],
    after_map: dict[str, dict[str, Any]],
    policy: dict[str, Any],
) -> list[str]:
    fields = policy["post_review_program_transition"]["immutable_phase_fields"]
    return [
        f"post-review immutable phase field changed: {phase_id}.{field}"
        for phase_id, before_phase in before_map.items()
        for field in fields
        if before_phase.get(field) != after_map[phase_id].get(field)
    ]


def _reviewed_and_next_phase_errors(
    before: dict[str, Any],
    after: dict[str, Any],
    before_map: dict[str, dict[str, Any]],
    after_map: dict[str, dict[str, Any]],
    phase_id: str,
    policy: dict[str, Any],
) -> list[str]:
    order = list(policy["phase_order"])
    transition = policy["post_review_program_transition"]
    index = order.index(phase_id)
    errors = _reviewed_phase_state_errors(before_map[phase_id], after_map[phase_id], transition)
    if index + 1 >= len(order):
        if after.get("current_phase") != phase_id:
            errors.append("terminal phase must remain current_phase")
        return errors
    next_id = order[index + 1]
    if after.get("current_phase") != next_id:
        errors.append(f"current_phase must advance only to {next_id}")
    if before_map[next_id]["status"] != transition["next_phase_status_from"]:
        errors.append(f"next phase {next_id} must start from NOT_STARTED")
    if after_map[next_id]["status"] != transition["next_phase_status_to"]:
        errors.append(f"next phase {next_id} must advance to IN_PROGRESS")
    return errors


def _unreviewed_phase_errors(
    before_map: dict[str, dict[str, Any]],
    after_map: dict[str, dict[str, Any]],
    phase_id: str,
    order: list[str],
) -> list[str]:
    index = order.index(phase_id)
    allowed = {phase_id}
    if index + 1 < len(order):
        allowed.add(order[index + 1])
    return [
        f"unreviewed phase changed after review: {pid}"
        for pid in order
        if pid not in allowed and before_map[pid] != after_map[pid]
    ]


def _reviewed_phase_state_errors(
    before: dict[str, Any], after: dict[str, Any], transition: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if before.get("status") not in transition["reviewed_phase_status_from"]:
        errors.append("reviewed phase must start IN_PROGRESS or BLOCKED")
    if after.get("status") != transition["reviewed_phase_status_to"]:
        errors.append("reviewed phase must finish COMPLETE")
    if after.get("technical_verification") != transition["technical_verification_to"]:
        errors.append("reviewed phase technical_verification must become PASS")
    if after.get("outcome_verification") not in {"PASS", "NOT_REQUIRED", "PENDING"}:
        errors.append("reviewed phase outcome_verification must be explicit at closure")
    return errors


def _lane_transition_errors(
    before: dict[str, Any], after: dict[str, Any], transition: dict[str, Any]
) -> list[str]:
    before_map = {item["id"]: item for item in before["extension_lanes"]}
    after_map = {item["id"]: item for item in after["extension_lanes"]}
    if set(before_map) != set(after_map):
        return ["post-review extension lane set changed"]
    errors: list[str] = []
    for lane_id, lane in before_map.items():
        for field in transition["immutable_lane_fields"]:
            if lane.get(field) != after_map[lane_id].get(field):
                errors.append(f"post-review immutable lane field changed: {lane_id}.{field}")
        if lane != after_map[lane_id]:
            errors.append(f"extension lane changed during phase finalization: {lane_id}")
    return errors
