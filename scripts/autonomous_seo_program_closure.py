"""Whole-program closure validation for autonomous SEO expansion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import autonomous_seo_phase_closure as phase_closure
from scripts import autonomous_seo_review_trust as trust

PROGRAM_CLOSURE_RELATIVE = "evaluation/remediation/autonomous-seo-expansion-program-closure.json"


def program_closure_errors(
    program: dict[str, Any], root: Path, policy: dict[str, Any]
) -> list[str]:
    if program.get("program_evidence_state") != "VERIFIED":
        return []
    path = root / PROGRAM_CLOSURE_RELATIVE
    if not path.is_file():
        return ["program VERIFIED requires autonomous-seo-expansion-program-closure.json"]
    closure = phase_closure.load_object(path)
    schema = phase_closure.load_object(
        root / "schemas" / "autonomous-seo-program-closure.schema.json"
    )
    errors = phase_closure.schema_errors(closure, schema, "program closure")
    if errors:
        return errors
    errors.extend(_candidate_freeze_errors(program, closure, root))
    errors.extend(_phase_closure_reference_errors(closure, root, policy))
    errors.extend(_program_evidence_errors(closure, root))
    errors.extend(phase_closure.reviewer_file_errors(closure, root))
    if closure.get("evidence_package_hash") != phase_closure.canonical_hash(
        _program_closure_payload(closure)
    ):
        errors.append("program closure evidence_package_hash is invalid")
    return errors


def _candidate_freeze_errors(
    program: dict[str, Any], closure: dict[str, Any], root: Path
) -> list[str]:
    if not (root / ".git").exists():
        return ["program closure requires Git history or an authenticated immutable manifest"]
    candidate = str(closure.get("candidate_commit", ""))
    if not trust.git_commit_exists(root, candidate):
        return ["program closure candidate_commit must identify an existing commit"]
    if not phase_closure.git_command_ok(root, ["merge-base", "--is-ancestor", candidate, "HEAD"]):
        return ["program closure candidate_commit must be an ancestor of final HEAD"]
    errors = _post_review_file_errors(closure, root, candidate)
    errors.extend(_program_transition_errors(program, root, candidate))
    return errors


def _post_review_file_errors(
    closure: dict[str, Any], root: Path, candidate: str
) -> list[str]:
    changed = phase_closure.git_stdout(root, ["diff", "--name-only", f"{candidate}..HEAD"])
    paths = [] if not changed else changed.splitlines()
    allowed = {
        phase_closure.PROGRAM_RELATIVE,
        PROGRAM_CLOSURE_RELATIVE,
        "evaluation/remediation/autonomous-seo-expansion-ledger.md",
    }
    allowed.update(str(item) for item in closure.get("reviewer_verdict_files", []))
    allowed.update(str(item) for item in closure.get("reviewer_provenance_files", []))
    unexpected = sorted(path for path in paths if path not in allowed)
    return [] if not unexpected else [f"program has post-review source drift: {unexpected}"]


def _program_transition_errors(
    program: dict[str, Any], root: Path, candidate: str
) -> list[str]:
    content = phase_closure.git_stdout(
        root, ["show", f"{candidate}:{phase_closure.PROGRAM_RELATIVE}"]
    )
    if content is None:
        return ["program closure cannot load reviewed program state"]
    before = json.loads(content)
    if not isinstance(before, dict):
        return ["reviewed program state is not an object"]
    before_state = before.pop("program_evidence_state", None)
    after = dict(program)
    after_state = after.pop("program_evidence_state", None)
    errors: list[str] = []
    if before != after:
        errors.append("program policy/state changed after final program review freeze")
    if before_state == "VERIFIED" or after_state != "VERIFIED":
        errors.append("finalization may only advance program_evidence_state to VERIFIED")
    return errors


def _phase_closure_reference_errors(
    closure: dict[str, Any], root: Path, policy: dict[str, Any]
) -> list[str]:
    expected = {
        str(phase_closure.closure_path(root, phase_id).relative_to(root))
        for phase_id in policy["phase_order"]
    }
    actual = set(closure.get("phase_closure_files", []))
    if actual == expected:
        return []
    return ["program closure must reference every canonical phase closure exactly once"]


def _program_evidence_errors(closure: dict[str, Any], root: Path) -> list[str]:
    candidate = str(closure.get("candidate_commit"))
    errors = phase_closure.evidence_ref_errors(
        closure.get("evidence_refs", []), root, candidate
    )
    errors.extend(
        phase_closure.evidence_ref_errors(
            closure.get("rollback_summary", {}).get("evidence_refs", []),
            root,
            candidate,
        )
    )
    return errors


def _program_closure_payload(closure: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "$schema",
        "schema_version",
        "reviewer_verdict_files",
        "reviewer_provenance_files",
        "evidence_package_hash",
        "closure_state",
    }
    return {key: value for key, value in closure.items() if key not in excluded}
