"""Validate the read-only owner-controlled APIVR remediation program."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING or __package__:
    from scripts.remediation_contracts import (
        EXCLUDED_PHRASES as EXCLUDED_PHRASES,
    )
    from scripts.remediation_contracts import (
        PHASE_IDS as PHASE_IDS,
    )
    from scripts.remediation_contracts import (
        PROGRAM_PATH as PROGRAM_PATH,
    )
    from scripts.remediation_contracts import (
        ROOT as ROOT,
    )
    from scripts.remediation_contracts import (
        SCHEMA_PATH as SCHEMA_PATH,
    )
    from scripts.remediation_contracts import (
        _load_object as _load_object,
    )
    from scripts.remediation_contracts import (
        _schema_errors as _schema_errors,
    )
    from scripts.remediation_contracts import (
        canonical_text_digest as canonical_text_digest,
    )
    from scripts.remediation_contracts import (
        evidence_package_hash as evidence_package_hash,
    )
else:
    from remediation_contracts import (
        EXCLUDED_PHRASES as EXCLUDED_PHRASES,
    )
    from remediation_contracts import (
        PHASE_IDS as PHASE_IDS,
    )
    from remediation_contracts import (
        PROGRAM_PATH as PROGRAM_PATH,
    )
    from remediation_contracts import (
        ROOT as ROOT,
    )
    from remediation_contracts import (
        SCHEMA_PATH as SCHEMA_PATH,
    )
    from remediation_contracts import (
        _load_object as _load_object,
    )
    from remediation_contracts import (
        _schema_errors as _schema_errors,
    )
    from remediation_contracts import (
        canonical_text_digest as canonical_text_digest,
    )
    from remediation_contracts import (
        evidence_package_hash as evidence_package_hash,
    )
if TYPE_CHECKING or __package__:
    from scripts.remediation_evidence import (
        _evidence_errors as _evidence_errors,
    )
else:
    from remediation_evidence import (
        _evidence_errors as _evidence_errors,
    )
if TYPE_CHECKING or __package__:
    from scripts.remediation_history import (
        _closure_delta_errors as _closure_delta_errors,
    )
    from scripts.remediation_history import (
        _load_object_at_commit as _load_object_at_commit,
    )
    from scripts.remediation_history import (
        _rollback_evidence_errors as _rollback_evidence_errors,
    )
else:
    from remediation_history import (
        _closure_delta_errors as _closure_delta_errors,
    )
    from remediation_history import (
        _load_object_at_commit as _load_object_at_commit,
    )
    from remediation_history import (
        _rollback_evidence_errors as _rollback_evidence_errors,
    )
if TYPE_CHECKING or __package__:
    from scripts.remediation_phase_evidence import (
        _phase_authority_errors,
        _phase_certification_errors,
        _phase_commit_errors,
        _phase_criteria_errors,
        _phase_evidence_status_errors,
        _phase_gate_evidence_errors,
        _phase_rollback_errors,
    )
else:
    from remediation_phase_evidence import (
        _phase_authority_errors,
        _phase_certification_errors,
        _phase_commit_errors,
        _phase_criteria_errors,
        _phase_evidence_status_errors,
        _phase_gate_evidence_errors,
        _phase_rollback_errors,
    )
if TYPE_CHECKING or __package__:
    from scripts.remediation_phase_review import (
        _phase_learning_errors,
        _phase_review_hash_errors,
        _phase_reviewer_identity_errors,
        _phase_verdict_errors,
    )
else:
    from remediation_phase_review import (
        _phase_learning_errors,
        _phase_review_hash_errors,
        _phase_reviewer_identity_errors,
        _phase_verdict_errors,
    )


def _current_phase_errors(program: dict[str, Any], phases: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    active = [phase for phase in phases if phase.get("status") == "IN_PROGRESS"]
    if len(active) > 1:
        errors.append("at most one phase may be IN_PROGRESS")
    current = str(program.get("current_phase", ""))
    if active and active[0].get("id") != current:
        errors.append("current_phase must identify the sole IN_PROGRESS phase")

    current_index = PHASE_IDS.index(current) if current in PHASE_IDS else -1
    if current_index >= 0:
        current_status = phases[current_index].get("status")
        all_complete = all(phase.get("status") == "COMPLETE" for phase in phases)
        if not all_complete and current_status not in {"IN_PROGRESS", "BLOCKED"}:
            errors.append(
                "current_phase must be IN_PROGRESS or BLOCKED until the program completes"
            )
    return errors


def _validate_sequence(
    program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phases = program.get("phases", [])
    ids = [phase.get("id") for phase in phases]
    if ids != PHASE_IDS:
        errors.append(f"phase order must be {PHASE_IDS}; found {ids}")
        return errors

    errors.extend(_current_phase_errors(program, phases))
    current = str(program.get("current_phase", ""))
    current_index = PHASE_IDS.index(current) if current in PHASE_IDS else -1
    for index, phase in enumerate(phases):
        status = phase.get("status")
        if index < current_index and status != "COMPLETE":
            errors.append(f"{phase['id']} precedes current_phase and must be COMPLETE")
        if index > current_index and status != "NOT_STARTED":
            errors.append(f"{phase['id']} follows current_phase and must be NOT_STARTED")
        if status == "COMPLETE":
            errors.extend(
                _validate_complete_phase(phase, program, root, authenticate_ci=authenticate_ci)
            )
    return errors


def _validate_complete_phase(
    phase: dict[str, Any],
    program: dict[str, Any],
    root: Path,
    *,
    authenticate_ci: bool = False,
) -> list[str]:
    return [
        *_phase_commit_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_rollback_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_authority_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_certification_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_criteria_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_gate_evidence_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_evidence_status_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_verdict_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_review_hash_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_reviewer_identity_errors(phase, program, root, authenticate_ci=authenticate_ci),
        *_phase_learning_errors(phase, program, root, authenticate_ci=authenticate_ci),
    ]


def _validate_candidate_complete_phase(
    phase: dict[str, Any],
    program: dict[str, Any],
    root: Path,
    *,
    authenticate_ci: bool = False,
) -> list[str]:
    """Run every non-closure COMPLETE invariant before a package is reviewed."""
    phase_id = str(phase["id"])
    candidate = copy.deepcopy(phase)
    expected_lifecycle_errors = {
        f"{phase_id} cannot be COMPLETE: review_snapshot_commit is missing",
        f"{phase_id} cannot be COMPLETE: frozen_package_commit is missing",
        f"{phase_id} cannot be COMPLETE: package certification is missing",
        f"{phase_id} requires one canonical verdict from each independent reviewer role",
        f"{phase_id} requires two APPROVE_GREAT verdicts",
        f"{phase_id} requires distinct reviewer identities and contexts",
    }
    errors = _validate_complete_phase(
        candidate,
        program,
        root,
        authenticate_ci=authenticate_ci,
    )
    return [
        f"{phase_id} candidate-complete preflight: {error}"
        for error in errors
        if error not in expected_lifecycle_errors
    ]


def _finding_reference_errors(program: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    for finding in program.get("audit_findings", []):
        for reference in finding.get("source_refs", []):
            source_path = str(reference).split("::", 1)[0]
            if not (root / source_path).exists():
                errors.append(
                    f"audit finding {finding.get('id')} references missing source {reference}"
                )

    return errors


def _criterion_context_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    criterion_ids = [
        criterion.get("id")
        for phase in program.get("phases", [])
        for criterion in phase.get("acceptance_criteria", [])
    ]
    if len(criterion_ids) != len(set(criterion_ids)):
        errors.append("acceptance criterion ids must be unique")

    reviewer_contexts = [
        context
        for phase in program.get("phases", [])
        for context in (
            item.get("context_id") for item in phase.get("review", {}).get("verdicts", [])
        )
        if context
    ]
    if len(reviewer_contexts) != len(set(reviewer_contexts)):
        errors.append("reviewer contexts cannot be reused across phases or roles")
    return errors


def _validate_program_rules(
    program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors = _validate_sequence(program, root, authenticate_ci=authenticate_ci)
    exclusions = set(program.get("exclusions", []))
    missing = sorted(EXCLUDED_PHRASES - exclusions)
    if missing:
        errors.append(f"program must preserve explicit exclusions: {missing}")
    if program.get("direct_merge_permitted") is not False:
        errors.append("the remediation program can never authorize direct merge")
    failure_ids = [item.get("id") for item in program.get("failures", [])]
    if len(failure_ids) != len(set(failure_ids)):
        errors.append("failure ids must be unique")
    learning_ids = [item.get("id") for item in program.get("learning_records", [])]
    if len(learning_ids) != len(set(learning_ids)):
        errors.append("learning record ids must be unique")
    finding_ids = [item.get("id") for item in program.get("audit_findings", [])]
    if len(finding_ids) != len(set(finding_ids)):
        errors.append("audit finding ids must be unique")
    errors.extend(_finding_reference_errors(program, root))

    errors.extend(_criterion_context_errors(program))
    known_failures = set(failure_ids)
    for record in program.get("learning_records", []):
        failure_id = record.get("failure_id")
        if failure_id is not None and failure_id not in known_failures:
            errors.append(
                f"learning record {record.get('id')} references unknown failure {failure_id}"
            )
    return errors


def validate(root: Path = ROOT, *, authenticate_ci: bool = False) -> list[str]:
    program_path = root / PROGRAM_PATH.relative_to(ROOT)
    schema_path = root / SCHEMA_PATH.relative_to(ROOT)
    try:
        program = _load_object(program_path)
        schema = _load_object(schema_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    return [
        *_schema_errors(program, schema, root),
        *_validate_program_rules(program, root, authenticate_ci=authenticate_ci),
    ]


def validate_current_candidate_complete(
    root: Path = ROOT, *, authenticate_ci: bool = False
) -> list[str]:
    """Preflight the canonical frozen current phase without requiring closure metadata."""
    try:
        program = _load_object(root / PROGRAM_PATH.relative_to(ROOT))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    current_phase = str(program.get("current_phase", ""))
    phase = next(
        (item for item in program.get("phases", []) if item.get("id") == current_phase),
        None,
    )
    if not phase or phase.get("status") != "IN_PROGRESS":
        return []
    if not phase.get("review", {}).get("evidence_package_hash"):
        return []
    return _validate_candidate_complete_phase(
        phase,
        program,
        root,
        authenticate_ci=authenticate_ci,
    )


def main() -> int:
    authenticate_ci = (
        os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
        and os.environ.get("WCSEO_AUTHENTICATE_CI_RECEIPTS", "").lower() == "true"
    )
    errors = [
        *validate(authenticate_ci=authenticate_ci),
        *validate_current_candidate_complete(authenticate_ci=authenticate_ci),
    ]
    payload = {
        "status": "PASS" if not errors else "FAIL",
        "program": str(PROGRAM_PATH.relative_to(ROOT)).replace("\\", "/"),
        "errors": errors,
        "direct_merge_permitted": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
