"""Evaluate one bounded comparative improvement cycle.

The runner validates evidence and reviewer independence. It never edits source
files, executes providers, opens pull requests or merges changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from runtime.schema_registry import SchemaRegistry

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ROLES = {"SENIOR_SCRUMMASTER_3", "VP_ENGINEERING"}
APPROVAL = "APPROVE_GREAT"


def canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_reviewer_independence(
    verdicts: list[dict[str, Any]],
    *,
    builder_context_id: str,
    evidence_package_hash: str,
) -> list[str]:
    errors: list[str] = []
    if len(verdicts) != 2:
        return ["exactly two independent reviewer verdicts are required"]

    roles = {str(item.get("role", "")) for item in verdicts}
    if roles != REQUIRED_ROLES:
        errors.append(f"reviewer roles must be {sorted(REQUIRED_ROLES)}; found {sorted(roles)}")

    reviewer_ids = [str(item.get("reviewer_id", "")) for item in verdicts]
    if len(set(reviewer_ids)) != 2:
        errors.append("reviewer ids must be distinct")

    contexts = [str(item.get("context_id", "")) for item in verdicts]
    if len(set(contexts)) != 2:
        errors.append("reviewer context ids must be distinct")
    if builder_context_id in contexts:
        errors.append("reviewer context cannot equal the builder context")

    for verdict in verdicts:
        if verdict.get("is_builder") is not False:
            errors.append(f"{verdict.get('reviewer_id')} must explicitly declare is_builder=false")
        if verdict.get("saw_other_reviewer_verdict") is not False:
            errors.append(
                f"{verdict.get('reviewer_id')} must submit before seeing the other verdict"
            )
        if verdict.get("evidence_package_hash") != evidence_package_hash:
            errors.append(
                f"{verdict.get('reviewer_id')} reviewed a different evidence package"
            )
        objections = verdict.get("strongest_objections")
        if not isinstance(objections, list) or len(objections) < 3:
            errors.append(f"{verdict.get('reviewer_id')} must provide at least three objections")
    return errors


def evaluate_cycle(cycle: dict[str, Any], *, builder_context_id: str) -> dict[str, Any]:
    registry = SchemaRegistry(ROOT)
    schema_errors = registry.errors("improvement-cycle", cycle)
    if schema_errors:
        return {
            "decision": "INVALID",
            "state": cycle.get("state", "UNKNOWN"),
            "errors": schema_errors,
            "persist_lessons": False,
            "direct_merge_permitted": False,
        }

    errors: list[str] = []
    verification = cycle["verification"]
    comparison = cycle["claude_comparison"]
    verdicts = cycle["reviewer_verdicts"]
    evidence_package = {
        "cycle_id": cycle["cycle_id"],
        "gap_id": cycle["gap_id"],
        "baseline": cycle["baseline"],
        "files_changed": cycle["files_changed"],
        "tests_added": cycle["tests_added"],
        "verification": verification,
        "claude_comparison": comparison,
    }
    evidence_hash = canonical_hash(evidence_package)

    if cycle.get("direct_merge_permitted") is not False:
        errors.append("improvement cycles can never authorize direct merge")
    if not verification.get("tests_passed"):
        errors.append("tests are not passing")
    if verification.get("regressions"):
        errors.append("regressions remain unresolved")
    if verification.get("security_passed") is not True:
        errors.append("security verification is not passing")
    if verification.get("documentation_executed") is not True:
        errors.append("operator documentation has not been executed successfully")
    if comparison.get("verdict") not in {"SUPERIOR", "PARITY", "REJECTED"}:
        errors.append("the implementation remains inferior to the pinned comparator")

    errors.extend(
        validate_reviewer_independence(
            verdicts,
            builder_context_id=builder_context_id,
            evidence_package_hash=evidence_hash,
        )
    )

    review_values = [str(item.get("verdict", "")) for item in verdicts]
    if "REJECT_BAD" in review_values:
        decision = "REJECT_BAD"
        state = "REJECTED_BAD"
        next_action = "Revert or redesign the correction; do not close the parity gap."
    elif errors or "REWORK_GOOD" in review_values or len(verdicts) != 2:
        if int(cycle["iteration"]) >= 5:
            decision = "ARCHITECTURAL_REDESIGN"
            state = "ARCHITECTURAL_REDESIGN"
            next_action = "Stop incremental patching and start a new architecture hypothesis."
        else:
            decision = "REWORK_GOOD"
            state = "REWORK_REQUIRED"
            next_action = "Address every failed gate and reviewer objection, then repeat the cycle."
    elif review_values.count(APPROVAL) == 2 and cycle["builder_rating"] == "GREAT":
        decision = "APPROVE_GREAT"
        state = "APPROVED_GREAT"
        next_action = "Persist verified lessons and submit the branch for normal human-controlled merge."
    else:
        decision = "REWORK_GOOD"
        state = "REWORK_REQUIRED"
        next_action = "Builder and independent reviewers have not all rated the work GREAT."

    return {
        "decision": decision,
        "state": state,
        "errors": errors,
        "reviewer_verdicts": review_values,
        "evidence_package_hash": evidence_hash,
        "persist_lessons": decision == "APPROVE_GREAT",
        "direct_merge_permitted": False,
        "next_action": next_action,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a controlled SEO-system improvement cycle.")
    parser.add_argument("cycle", type=Path)
    parser.add_argument("--builder-context-id", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cycle = json.loads(args.cycle.read_text(encoding="utf-8-sig"))
    result = evaluate_cycle(cycle, builder_context_id=args.builder_context_id)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["decision"] == "APPROVE_GREAT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
