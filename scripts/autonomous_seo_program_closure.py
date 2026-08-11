"""Whole-program closure validation for autonomous SEO expansion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts import autonomous_seo_expansion_closure as phase_closure

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
    errors.extend(_phase_closure_reference_errors(closure, root, policy))
    errors.extend(_program_evidence_errors(closure, root))
    errors.extend(phase_closure.reviewer_file_errors(closure, root))
    if closure.get("evidence_package_hash") != phase_closure.canonical_hash(
        _program_closure_payload(closure)
    ):
        errors.append("program closure evidence_package_hash is invalid")
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
        "evidence_package_hash",
        "closure_state",
    }
    return {key: value for key, value in closure.items() if key not in excluded}
