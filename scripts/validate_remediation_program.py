"""Validate the owner-controlled APIVR remediation program.

The validator is intentionally read-only. It prevents phase skipping, false
completion, reviewer-context reuse, and failure closure without a reusable
learning guardrail. It never edits source, advances a phase, or merges work.
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PATH = ROOT / "evaluation" / "remediation" / "owner-controlled-remediation-program.json"
SCHEMA_PATH = ROOT / "schemas" / "remediation-program.schema.json"
PHASE_IDS = [f"P{index}" for index in range(9)]
COMPLETION_GATES: dict[str, str | set[str]] = {
    "implementation_audit": "PASS",
    "focused_tests": "PASS",
    "full_certification": "PASS",
    "documentation": {"PASS", "NOT_APPLICABLE"},
    "learning": {"PASS", "NO_MATERIAL_LEARNING"},
    "unexpected_change_scan": "PASS",
}
EXCLUDED_PHRASES = {
    "public packaging and release maturity",
    "real-world SEO effectiveness and external reproduction",
}


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def _schema_errors(program: dict[str, Any], schema: dict[str, Any], root: Path) -> list[str]:
    Draft202012Validator.check_schema(schema)
    reviewer_schema = _load_object(root / "schemas" / "reviewer-verdict.schema.json")
    Draft202012Validator.check_schema(reviewer_schema)
    registry: Registry[Any] = Registry().with_resources(
        [
            (str(schema["$id"]), Resource.from_contents(schema)),
            (str(reviewer_schema["$id"]), Resource.from_contents(reviewer_schema)),
        ]
    )
    validator = Draft202012Validator(schema, registry=registry)
    return [
        f"schema {'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(program), key=lambda item: list(item.absolute_path))
    ]


def _gate_passes(actual: str, required: str | set[str]) -> bool:
    return actual in required if isinstance(required, set) else actual == required


def _validate_sequence(program: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    phases = program.get("phases", [])
    ids = [phase.get("id") for phase in phases]
    if ids != PHASE_IDS:
        errors.append(f"phase order must be {PHASE_IDS}; found {ids}")
        return errors

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
            errors.append("current_phase must be IN_PROGRESS or BLOCKED until the program completes")
    for index, phase in enumerate(phases):
        status = phase.get("status")
        if index < current_index and status != "COMPLETE":
            errors.append(f"{phase['id']} precedes current_phase and must be COMPLETE")
        if index > current_index and status != "NOT_STARTED":
            errors.append(f"{phase['id']} follows current_phase and must be NOT_STARTED")
        if status == "COMPLETE":
            errors.extend(_validate_complete_phase(phase, program, root))
    return errors


def _validate_complete_phase(
    phase: dict[str, Any], program: dict[str, Any], root: Path
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase["id"])
    verified_commit = phase.get("verified_commit")
    if not verified_commit:
        errors.append(f"{phase_id} cannot be COMPLETE: verified_commit is missing")
    elif (root / ".git").exists():
        try:
            subprocess.run(
                ["git", "cat-file", "-e", f"{verified_commit}^{{commit}}"],
                cwd=root,
                check=True,
                capture_output=True,
                timeout=20,
            )
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", str(verified_commit), "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                timeout=20,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            errors.append(f"{phase_id} cannot be COMPLETE: verified_commit is not an ancestor of HEAD")
    for key, required in COMPLETION_GATES.items():
        actual = str(phase["gates"].get(key, ""))
        if not _gate_passes(actual, required):
            errors.append(f"{phase_id} cannot be COMPLETE: gate {key} is {actual}")
    security = str(phase["gates"].get("security_review", ""))
    if security not in {"PASS", "NOT_APPLICABLE"}:
        errors.append(f"{phase_id} cannot be COMPLETE: gate security_review is {security}")

    for criterion in phase.get("acceptance_criteria", []):
        if criterion.get("status") != "PASS":
            errors.append(f"{phase_id} cannot be COMPLETE: {criterion.get('id')} is not PASS")
        if not criterion.get("evidence_refs"):
            errors.append(f"{phase_id} cannot be COMPLETE: {criterion.get('id')} has no evidence")
        for evidence in criterion.get("evidence_refs", []):
            evidence_class = str(evidence.get("class", ""))
            reference = str(evidence.get("ref", ""))
            if evidence.get("commit") != verified_commit:
                errors.append(
                    f"{phase_id} cannot be COMPLETE: {criterion.get('id')} evidence is not bound to verified_commit"
                )
            source_path = reference.split("::", 1)[0]
            if evidence_class in {"SOURCE", "AUTOMATED"}:
                expected_digest = evidence.get("sha256")
                content: bytes | None = None
                if (root / ".git").exists() and verified_commit:
                    try:
                        content = subprocess.check_output(
                            ["git", "show", f"{verified_commit}:{source_path}"],
                            cwd=root,
                            stderr=subprocess.DEVNULL,
                            timeout=20,
                        )
                    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                        content = None
                elif (root / source_path).is_file():
                    content = (root / source_path).read_bytes()
                if content is None:
                    errors.append(
                        f"{phase_id} cannot be COMPLETE: {criterion.get('id')} evidence does not exist at verified_commit: {reference}"
                    )
                elif not expected_digest or hashlib.sha256(content).hexdigest() != expected_digest:
                    errors.append(
                        f"{phase_id} cannot be COMPLETE: {criterion.get('id')} evidence digest is not immutable: {reference}"
                    )
            if evidence.get("status") not in {"OBSERVED", "PASS"}:
                errors.append(
                    f"{phase_id} cannot be COMPLETE: {criterion.get('id')} evidence {reference} is not passing"
                )

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

    review = phase.get("review", {})
    verdicts = review.get("verdicts", [])
    roles = {item.get("role") for item in verdicts}
    if len(verdicts) != 2 or roles != {"SENIOR_SCRUMMASTER_3", "VP_ENGINEERING"}:
        errors.append(f"{phase_id} requires one canonical verdict from each independent reviewer role")
    if len(verdicts) != 2 or any(item.get("verdict") != "APPROVE_GREAT" for item in verdicts):
        errors.append(f"{phase_id} requires two APPROVE_GREAT verdicts")
    package_hash = review.get("evidence_package_hash")
    if not package_hash or any(item.get("evidence_package_hash") != package_hash for item in verdicts):
        errors.append(f"{phase_id} reviewers must inspect the same immutable evidence package")
    contexts = [item.get("context_id") for item in verdicts]
    reviewer_ids = [item.get("reviewer_id") for item in verdicts]
    if len(set(contexts)) != 2 or len(set(reviewer_ids)) != 2:
        errors.append(f"{phase_id} requires distinct reviewer identities and contexts")

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
        if failure.get("status") != "RESOLVED":
            errors.append(f"{phase_id} cannot be COMPLETE: failure {failure.get('id')} remains open")
            continue
        linked = [item for item in learning if item.get("failure_id") == failure.get("id")]
        if not linked:
            errors.append(
                f"{phase_id} cannot be COMPLETE: resolved failure {failure.get('id')} has no learning record"
            )
        elif not any(
            item.get("status") == "CONFIRMED"
            and item.get("guardrail")
            and item.get("verification_ref")
            for item in linked
        ):
            errors.append(
                f"{phase_id} cannot be COMPLETE: failure {failure.get('id')} lacks a confirmed guardrail"
            )
    return errors


def _validate_program_rules(program: dict[str, Any], root: Path) -> list[str]:
    errors = _validate_sequence(program, root)
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
    for finding in program.get("audit_findings", []):
        for reference in finding.get("source_refs", []):
            source_path = str(reference).split("::", 1)[0]
            if not (root / source_path).exists():
                errors.append(
                    f"audit finding {finding.get('id')} references missing source {reference}"
                )

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
            item.get("context_id")
            for item in phase.get("review", {}).get("verdicts", [])
        )
        if context
    ]
    if len(reviewer_contexts) != len(set(reviewer_contexts)):
        errors.append("reviewer contexts cannot be reused across phases or roles")
    known_failures = set(failure_ids)
    for record in program.get("learning_records", []):
        failure_id = record.get("failure_id")
        if failure_id is not None and failure_id not in known_failures:
            errors.append(f"learning record {record.get('id')} references unknown failure {failure_id}")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    program_path = root / PROGRAM_PATH.relative_to(ROOT)
    schema_path = root / SCHEMA_PATH.relative_to(ROOT)
    try:
        program = _load_object(program_path)
        schema = _load_object(schema_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    return [*_schema_errors(program, schema, root), *_validate_program_rules(program, root)]


def main() -> int:
    errors = validate()
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
