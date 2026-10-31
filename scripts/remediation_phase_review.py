"""Independent reviewer identity, package binding, and recurrence learning."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from jsonschema import Draft202012Validator

if TYPE_CHECKING or __package__:
    from scripts.remediation_contracts import (
        PROGRAM_PATH,
        ROOT,
        evidence_package_hash,
    )
else:
    from remediation_contracts import (
        PROGRAM_PATH,
        ROOT,
        evidence_package_hash,
    )
if TYPE_CHECKING or __package__:
    from scripts.remediation_evidence import (
        _evidence_errors,
    )
else:
    from remediation_evidence import (
        _evidence_errors,
    )
if TYPE_CHECKING or __package__:
    from scripts.remediation_history import (
        _load_object_at_commit,
    )
else:
    from remediation_history import (
        _load_object_at_commit,
    )


def _phase_verdict_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    verified_commit = phase.get("verified_commit")
    review = phase.get("review", {})
    verdicts = review.get("verdicts", [])
    if verified_commit:
        immutable_verdict_schema = _load_object_at_commit(
            root, "schemas/reviewer-verdict.schema.json", str(verified_commit)
        )
        immutable_validator = Draft202012Validator(immutable_verdict_schema)
        for verdict in verdicts:
            for schema_error in immutable_validator.iter_errors(verdict):
                errors.append(
                    f"{phase_id} verdict violates immutable reviewer schema: {schema_error.message}"
                )
    roles = {item.get("role") for item in verdicts}
    if (len(verdicts), roles) != (2, {"SENIOR_SCRUMMASTER_3", "VP_ENGINEERING"}):
        errors.append(
            f"{phase_id} requires one canonical verdict from each independent reviewer role"
        )
    if len(verdicts) != 2 or any(item.get("verdict") != "APPROVE_GREAT" for item in verdicts):
        errors.append(f"{phase_id} requires two APPROVE_GREAT verdicts")
    return errors


def _phase_review_hash_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    review_snapshot_commit = phase.get("review_snapshot_commit")
    review = phase.get("review", {})
    verdicts = review.get("verdicts", [])
    package_hash = review.get("evidence_package_hash")
    snapshot_program = (
        _load_object_at_commit(
            root,
            str(PROGRAM_PATH.relative_to(ROOT)).replace("\\", "/"),
            str(review_snapshot_commit),
        )
        if review_snapshot_commit
        else program
    )
    snapshot_phase = next(
        (item for item in snapshot_program.get("phases", []) if item.get("id") == phase_id), phase
    )
    expected_package_hash = evidence_package_hash(snapshot_program, snapshot_phase)
    if package_hash != expected_package_hash:
        errors.append(f"{phase_id} review hash does not match the canonical evidence package")
    if not package_hash or any(
        item.get("evidence_package_hash") != package_hash for item in verdicts
    ):
        errors.append(f"{phase_id} reviewers must inspect the same immutable evidence package")
    return errors


def _phase_reviewer_identity_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    verified_commit = phase.get("verified_commit")
    verdicts = phase.get("review", {}).get("verdicts", [])
    contexts = [item.get("context_id") for item in verdicts]
    reviewer_ids = [item.get("reviewer_id") for item in verdicts]
    if len(set(contexts)) != 2 or len(set(reviewer_ids)) != 2:
        errors.append(f"{phase_id} requires distinct reviewer identities and contexts")
    reviewer_registry = _load_object_at_commit(
        root, "evaluation/reviewer-registry.json", str(verified_commit) if verified_commit else None
    )
    registered = {
        item.get("role"): item.get("reviewer_id") for item in reviewer_registry.get("reviewers", [])
    }
    for verdict in verdicts:
        if registered.get(verdict.get("role")) != verdict.get("reviewer_id"):
            errors.append(
                f"{phase_id} reviewer {verdict.get('role')} is not the canonical registered identity"
            )

    return errors


def _failure_evidence_errors(
    failure: dict[str, Any],
    linked: list[dict[str, Any]],
    verified_commit: str | None,
    root: Path,
    phase_id: str,
    *,
    authenticate_ci: bool,
) -> list[str]:
    errors: list[str] = []
    for evidence in failure.get("evidence_refs", []):
        errors.extend(
            _evidence_errors(
                evidence,
                str(verified_commit) if verified_commit else None,
                root,
                f"{phase_id} cannot be COMPLETE: failure {failure.get('id')}",
                authenticate_ci=authenticate_ci,
            )
        )
    for record in linked:
        for evidence in record.get("observed_evidence", []):
            errors.extend(
                _evidence_errors(
                    evidence,
                    str(verified_commit) if verified_commit else None,
                    root,
                    f"{phase_id} cannot be COMPLETE: learning {record.get('id')}",
                    allow_ancestor=True,
                    require_unchanged=False,
                    authenticate_ci=authenticate_ci,
                )
            )
        errors.extend(
            _evidence_errors(
                record.get("verification_evidence", {}),
                str(verified_commit) if verified_commit else None,
                root,
                f"{phase_id} cannot be COMPLETE: learning {record.get('id')} verification",
                authenticate_ci=authenticate_ci,
            )
        )
    return errors


def _failure_learning_errors(
    failure: dict[str, Any],
    learning: list[dict[str, Any]],
    verified_commit: str | None,
    root: Path,
    phase_id: str,
    *,
    authenticate_ci: bool,
) -> list[str]:
    errors: list[str] = []
    if failure.get("status") != "RESOLVED":
        errors.append(f"{phase_id} cannot be COMPLETE: failure {failure.get('id')} remains open")
        return errors
    linked = [item for item in learning if item.get("failure_id") == failure.get("id")]
    if not linked:
        errors.append(
            f"{phase_id} cannot be COMPLETE: resolved failure {failure.get('id')} has no learning record"
        )
    elif not any(
        item.get("status") == "CONFIRMED"
        and item.get("guardrail")
        and item.get("verification_evidence")
        for item in linked
    ):
        errors.append(
            f"{phase_id} cannot be COMPLETE: failure {failure.get('id')} lacks a confirmed guardrail"
        )
    errors.extend(
        _failure_evidence_errors(
            failure, linked, verified_commit, root, phase_id, authenticate_ci=authenticate_ci
        )
    )
    return errors


def _phase_learning_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    verified_commit = phase.get("verified_commit")
    failures = [item for item in program.get("failures", []) if item.get("phase_id") == phase_id]
    findings = [
        item for item in program.get("audit_findings", []) if item.get("phase_id") == phase_id
    ]
    for finding in findings:
        if finding.get("status") != "RESOLVED":
            errors.append(
                f"{phase_id} cannot be COMPLETE: audit finding {finding.get('id')} is "
                f"{finding.get('status')}"
            )
    learning = program.get("learning_records", [])
    for failure in failures:
        errors.extend(
            _failure_learning_errors(
                failure, learning, verified_commit, root, phase_id, authenticate_ci=authenticate_ci
            )
        )
    return errors
