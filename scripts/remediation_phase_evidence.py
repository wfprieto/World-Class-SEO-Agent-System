"""Ordered remediation phase evidence and immutable authority checks."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING or __package__:
    from scripts.remediation_contracts import (
        COMPLETION_GATES,
        GATE_EVIDENCE_CLASSES,
        _gate_passes,
        _load_object,
        canonical_text_digest,
    )
else:
    from remediation_contracts import (
        COMPLETION_GATES,
        GATE_EVIDENCE_CLASSES,
        _gate_passes,
        _load_object,
        canonical_text_digest,
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
        _closure_delta_errors,
        _rollback_evidence_errors,
    )
else:
    from remediation_history import (
        _closure_delta_errors,
        _rollback_evidence_errors,
    )
if TYPE_CHECKING or __package__:
    from scripts.remediation_squash_integration import (
        accepted_history_errors,
    )
else:
    from remediation_squash_integration import (
        accepted_history_errors,
    )


def _phase_commit_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    verified_commit = phase.get("verified_commit")
    review_snapshot_commit = phase.get("review_snapshot_commit")
    frozen_package_commit = phase.get("frozen_package_commit")
    if not verified_commit:
        errors.append(f"{phase_id} cannot be COMPLETE: verified_commit is missing")
    elif not re.fullmatch(r"[0-9a-f]{40}", str(verified_commit)):
        errors.append(f"{phase_id} cannot be COMPLETE: verified_commit is malformed")
    elif (root / ".git").exists():
        errors.extend(
            f"{phase_id} cannot be COMPLETE: {item}"
            for item in accepted_history_errors(
                root,
                str(program.get("baseline", {}).get("commit", "")),
                str(verified_commit),
            )
        )
    if not review_snapshot_commit:
        errors.append(f"{phase_id} cannot be COMPLETE: review_snapshot_commit is missing")
    if not frozen_package_commit:
        errors.append(f"{phase_id} cannot be COMPLETE: frozen_package_commit is missing")
    elif frozen_package_commit != review_snapshot_commit:
        errors.append(
            f"{phase_id} cannot be COMPLETE: frozen package must equal review_snapshot_commit"
        )
    if review_snapshot_commit:
        errors.extend(_closure_delta_errors(program, phase, root, str(review_snapshot_commit)))
    return errors


def _phase_rollback_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    rollback_path = (
        root / "evaluation" / "remediation" / f"phase{phase_id[1:]}-rollback-evidence.json"
    )
    expected_rollback_digest = phase.get("rollback_evidence_sha256")
    if not rollback_path.is_file() or not expected_rollback_digest:
        errors.append(f"{phase_id} cannot be COMPLETE: rollback evidence is missing")
    elif canonical_text_digest(rollback_path.read_bytes()) != expected_rollback_digest:
        errors.append(
            f"{phase_id} cannot be COMPLETE: rollback evidence digest does not match reviewed package"
        )
    else:
        try:
            rollback_payload = _load_object(rollback_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{phase_id} cannot be COMPLETE: rollback evidence is invalid: {exc}")
        else:
            errors.extend(
                _rollback_evidence_errors(
                    rollback_payload, program, root, f"{phase_id} rollback evidence"
                )
            )

    return errors


def _phase_authority_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    verified_commit = phase.get("verified_commit")
    authority = phase.get("authority_evidence", [])
    required_authority = {
        "evaluation/reviewer-registry.json",
        "schemas/reviewer-verdict.schema.json",
        "evaluation/reviewers/senior-scrummaster-3.md",
        "evaluation/reviewers/vp-engineering.md",
    }
    observed_authority = {str(item.get("ref", "")).split("::", 1)[0] for item in authority}
    if observed_authority != required_authority:
        errors.append(f"{phase_id} cannot be COMPLETE: reviewer authority package is incomplete")
    for evidence in authority:
        errors.extend(
            _evidence_errors(
                evidence,
                str(verified_commit) if verified_commit else None,
                root,
                f"{phase_id} authority",
                allow_ancestor=True,
                authenticate_ci=authenticate_ci,
            )
        )
        if verified_commit and (root / ".git").exists():
            source_path = str(evidence.get("ref", "")).split("::", 1)[0]
            expected_digest = evidence.get("sha256")
            for commit_label in (str(verified_commit), "HEAD"):
                try:
                    content = subprocess.check_output(
                        ["git", "show", f"{commit_label}:{source_path}"],
                        cwd=root,
                        stderr=subprocess.DEVNULL,
                        timeout=20,
                    )
                except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    errors.append(
                        f"{phase_id} authority {source_path} is missing at {commit_label}"
                    )
                    continue
                if hashlib.sha256(content).hexdigest() != expected_digest:
                    errors.append(f"{phase_id} authority {source_path} changed by {commit_label}")
    return errors


def _phase_certification_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    review_snapshot_commit = phase.get("review_snapshot_commit")
    package_certification = phase.get("package_certification", [])
    if not package_certification:
        errors.append(f"{phase_id} cannot be COMPLETE: package certification is missing")
    for evidence in package_certification:
        errors.extend(
            _evidence_errors(
                evidence,
                str(review_snapshot_commit) if review_snapshot_commit else None,
                root,
                f"{phase_id} package certification",
                authenticate_ci=authenticate_ci,
            )
        )
    for key, required in COMPLETION_GATES.items():
        actual = str(phase["gates"].get(key, ""))
        if not _gate_passes(actual, required):
            errors.append(f"{phase_id} cannot be COMPLETE: gate {key} is {actual}")
    security = str(phase["gates"].get("security_review", ""))
    if security not in {"PASS", "NOT_APPLICABLE"}:
        errors.append(f"{phase_id} cannot be COMPLETE: gate security_review is {security}")

    return errors


def _phase_criteria_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    verified_commit = phase.get("verified_commit")
    for criterion in phase.get("acceptance_criteria", []):
        if criterion.get("status") != "PASS":
            errors.append(f"{phase_id} cannot be COMPLETE: {criterion.get('id')} is not PASS")
        if not criterion.get("evidence_refs"):
            errors.append(f"{phase_id} cannot be COMPLETE: {criterion.get('id')} has no evidence")
        for evidence in criterion.get("evidence_refs", []):
            errors.extend(
                _evidence_errors(
                    evidence,
                    str(verified_commit) if verified_commit else None,
                    root,
                    f"{phase_id} cannot be COMPLETE: {criterion.get('id')}",
                    allow_ancestor=True,
                    authenticate_ci=authenticate_ci,
                )
            )

    return errors


def _phase_gate_evidence_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    verified_commit = phase.get("verified_commit")
    gate_evidence = phase.get("gate_evidence", {})
    gate_keys: set[tuple[str, str, str]] = set()
    for gate, result in phase.get("gates", {}).items():
        records = gate_evidence.get(gate, [])
        if result in {"PASS", "NO_MATERIAL_LEARNING"} and not records:
            errors.append(f"{phase_id} cannot be COMPLETE: gate {gate} has no structured evidence")
        for evidence in records:
            evidence_class = str(evidence.get("class", ""))
            if evidence_class not in GATE_EVIDENCE_CLASSES.get(gate, set()):
                errors.append(
                    f"{phase_id} cannot be COMPLETE: gate {gate} rejects evidence class {evidence_class}"
                )
            assertion = str(evidence.get("assertion", ""))
            if not assertion.startswith(f"[{gate}] "):
                errors.append(
                    f"{phase_id} cannot be COMPLETE: gate {gate} evidence lacks a gate-specific assertion"
                )
            identity = (gate, str(evidence.get("ref", "")), assertion)
            if identity in gate_keys:
                errors.append(
                    f"{phase_id} cannot be COMPLETE: gate {gate} contains duplicate evidence"
                )
            gate_keys.add(identity)
            errors.extend(
                _evidence_errors(
                    evidence,
                    str(verified_commit) if verified_commit else None,
                    root,
                    f"{phase_id} cannot be COMPLETE: gate {gate}",
                    allow_ancestor=True,
                    authenticate_ci=authenticate_ci,
                )
            )

    return errors


def _phase_evidence_status_errors(
    phase: dict[str, Any], program: dict[str, Any], root: Path, *, authenticate_ci: bool = False
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    evidence_status = phase.get("evidence_status", {})
    required_evidence = set(phase.get("required_evidence_classes", []))
    all_evidence = [
        evidence
        for criterion in phase.get("acceptance_criteria", [])
        for evidence in criterion.get("evidence_refs", [])
    ]
    for evidence_class in required_evidence:
        if evidence_status.get(evidence_class) != "PASS":
            errors.append(
                f"{phase_id} cannot be COMPLETE: evidence class {evidence_class} is "
                f"{evidence_status.get(evidence_class)}"
            )
        if not any(
            evidence.get("class") == evidence_class
            and evidence.get("status") in {"OBSERVED", "PASS"}
            for evidence in all_evidence
        ):
            errors.append(
                f"{phase_id} cannot be COMPLETE: evidence class {evidence_class} has no structured record"
            )
    for evidence_class, status in evidence_status.items():
        if status == "PASS" and not any(
            evidence.get("class") == evidence_class
            and evidence.get("status") in {"OBSERVED", "PASS"}
            for evidence in all_evidence
        ):
            errors.append(
                f"{phase_id} cannot be COMPLETE: passing evidence class {evidence_class} has no structured record"
            )

    return errors
