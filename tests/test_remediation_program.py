from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from scripts.validate_remediation_program import (
    PROGRAM_PATH,
    ROOT,
    SCHEMA_PATH,
    evidence_package_hash,
    validate,
)


def _program() -> dict:
    return json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, payload: dict) -> Path:
    fixture_payload = copy.deepcopy(payload)
    for finding in fixture_payload["audit_findings"]:
        finding["source_refs"] = ["schemas/remediation-program.schema.json"]
    for phase in fixture_payload["phases"]:
        verdicts = phase.get("review", {}).get("verdicts", [])
        if verdicts:
            package_hash = evidence_package_hash(fixture_payload, phase)
            phase["review"]["evidence_package_hash"] = package_hash
            for verdict in verdicts:
                verdict["evidence_package_hash"] = package_hash
    program_path = tmp_path / PROGRAM_PATH.relative_to(ROOT)
    schema_path = tmp_path / SCHEMA_PATH.relative_to(ROOT)
    program_path.parent.mkdir(parents=True)
    schema_path.parent.mkdir(parents=True)
    program_path.write_text(json.dumps(fixture_payload, indent=2), encoding="utf-8")
    schema_path.write_bytes(SCHEMA_PATH.read_bytes())
    reviewer_path = tmp_path / "schemas" / "reviewer-verdict.schema.json"
    reviewer_path.write_text(
        (ROOT / "schemas" / "reviewer-verdict.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return tmp_path


def _complete_phase(payload: dict, phase_index: int) -> None:
    phase = payload["phases"][phase_index]
    phase["status"] = "COMPLETE"
    phase["verified_commit"] = payload["baseline"]["commit"]
    schema_digest = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
    for criterion in phase["acceptance_criteria"]:
        criterion["status"] = "PASS"
        criterion["evidence_refs"] = [
            {
                "class": "AUTOMATED",
                "ref": "schemas/remediation-program.schema.json",
                "commit": phase["verified_commit"],
                "sha256": schema_digest,
                "environment": "LOCAL",
                "status": "PASS",
                "assertion": f"{criterion['id']} passed the isolated validator fixture.",
            }
        ]
    phase["acceptance_criteria"][0]["evidence_refs"].extend(
        [
            {
                "class": "SOURCE",
                "ref": "schemas/remediation-program.schema.json",
                "commit": phase["verified_commit"],
                "sha256": schema_digest,
                "environment": "LOCAL",
                "status": "OBSERVED",
                "assertion": "The frozen source schema was inspected.",
            },
            {
                "class": "CI",
                "ref": "https://ci.example.invalid/runs/phase",
                "commit": phase["verified_commit"],
                "sha256": None,
                "environment": "CI",
                "status": "PASS",
                "assertion": "The exact verified commit passed certification.",
            },
        ]
    )
    for evidence_class in phase["required_evidence_classes"]:
        if evidence_class in {"PROVIDER", "DEPLOYED", "OPERATIONAL"}:
            phase["acceptance_criteria"][0]["evidence_refs"].append(
                {
                    "class": evidence_class,
                    "ref": f"https://provider.example.invalid/{evidence_class.lower()}",
                    "commit": phase["verified_commit"],
                    "sha256": None,
                    "environment": evidence_class,
                    "status": "PASS",
                    "assertion": f"The required {evidence_class} state was observed.",
                }
            )
    phase["gates"] = {
        "implementation_audit": "PASS",
        "focused_tests": "PASS",
        "full_certification": "PASS",
        "security_review": "PASS",
        "documentation": "PASS",
        "learning": "NO_MATERIAL_LEARNING",
        "unexpected_change_scan": "PASS",
    }
    phase["evidence_status"] = {
        "SOURCE": "PASS",
        "AUTOMATED": "PASS",
        "CI": "PASS",
        "PROVIDER": "OUT_OF_SCOPE",
        "DEPLOYED": "OUT_OF_SCOPE",
        "OPERATIONAL": "OUT_OF_SCOPE",
    }
    for evidence_class in phase["required_evidence_classes"]:
        phase["evidence_status"][evidence_class] = "PASS"
    for finding in payload["audit_findings"]:
        if finding["phase_id"] == phase["id"]:
            finding["status"] = "RESOLVED"
    _refresh_review(payload, phase)


def _verdict(phase_id: str, role: str, reviewer: str, package_hash: str) -> dict:
    return {
        "review_id": f"review-{phase_id.lower()}-{reviewer}",
        "reviewer_id": f"reviewer-{reviewer}-{phase_id.lower()}",
        "role": role,
        "context_id": f"context-{reviewer}-{phase_id.lower()}-fresh",
        "provider": "test-provider",
        "model": "test-model",
        "evidence_package_hash": package_hash,
        "verdict": "APPROVE_GREAT",
        "strongest_objections": [
            "The exact commit must stay immutable.",
            "The rollback path must stay executable.",
            "The evidence must remain independently reproducible.",
        ],
        "evidence_refs": ["test-evidence-package"],
        "residual_risks": [],
        "required_changes": [],
        "submitted_at": "2026-08-01T00:00:00Z",
        "saw_other_reviewer_verdict": False,
        "is_builder": False,
    }


def _refresh_review(payload: dict, phase: dict) -> None:
    package_hash = evidence_package_hash(payload, phase)
    phase["review"] = {
        "evidence_package_hash": package_hash,
        "verdicts": [
            _verdict(phase["id"], "SENIOR_SCRUMMASTER_3", "scrum", package_hash),
            _verdict(phase["id"], "VP_ENGINEERING", "vpeng", package_hash),
        ],
    }


def test_current_remediation_program_is_valid() -> None:
    assert validate() == []


def test_phase_skipping_is_rejected(tmp_path: Path) -> None:
    payload = _program()
    payload["current_phase"] = "P2"
    payload["phases"][0]["status"] = "NOT_STARTED"
    payload["phases"][2]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert "P0 precedes current_phase and must be COMPLETE" in errors
    assert "P1 precedes current_phase and must be COMPLETE" in errors


def test_phase_completion_requires_every_gate_evidence_and_independent_review(
    tmp_path: Path,
) -> None:
    payload = _program()
    payload["phases"][0]["status"] = "COMPLETE"
    payload["phases"][0]["verified_commit"] = None
    for criterion in payload["phases"][0]["acceptance_criteria"]:
        criterion["status"] = "NOT_RUN"
        criterion["evidence_refs"] = []
    payload["phases"][0]["evidence_status"]["AUTOMATED"] = "NOT_RUN"
    payload["phases"][0]["evidence_status"]["CI"] = "NOT_RUN"
    payload["phases"][0]["gates"] = {
        key: "NOT_RUN" for key in payload["phases"][0]["gates"]
    }
    payload["phases"][0]["review"] = {"evidence_package_hash": None, "verdicts": []}
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("P0 cannot be COMPLETE: gate focused_tests is NOT_RUN" in item for item in errors)
    assert any("P0-AC-01 is not PASS" in item for item in errors)
    assert any("requires one canonical verdict from each" in item for item in errors)
    assert any("requires two APPROVE_GREAT" in item for item in errors)


def test_resolved_failure_requires_confirmed_recurrence_guardrail(tmp_path: Path) -> None:
    payload = _program()
    payload["failures"] = []
    payload["learning_records"] = []
    _complete_phase(payload, 0)
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"
    payload["failures"] = [
        {
            "id": "FAIL-0001",
            "phase_id": "P0",
            "summary": "The production-path validator initially accepted a skipped phase.",
            "status": "RESOLVED",
            "evidence_refs": ["tests/test_remediation_program.py"],
        }
    ]

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("resolved failure FAIL-0001 has no learning record" in item for item in errors)


def test_confirmed_learning_allows_resolved_failure_to_close(tmp_path: Path) -> None:
    payload = _program()
    payload["failures"] = []
    payload["learning_records"] = []
    _complete_phase(payload, 0)
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"
    payload["failures"] = [
        {
            "id": "FAIL-0001",
            "phase_id": "P0",
            "summary": "The production-path validator initially accepted a skipped phase.",
            "status": "RESOLVED",
            "evidence_refs": ["tests/test_remediation_program.py"],
        }
    ]
    payload["learning_records"] = [
        {
            "id": "LEARN-0001",
            "phase_id": "P0",
            "failure_id": "FAIL-0001",
            "status": "CONFIRMED",
            "affected_invariant": "Phases advance only in canonical order.",
            "expected_result": "The validator rejects every skipped predecessor phase.",
            "observed_evidence": [
                {
                    "class": "AUTOMATED",
                    "ref": "schemas/remediation-program.schema.json",
                        "commit": payload["baseline"]["commit"],
                        "sha256": hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(),
                    "environment": "LOCAL",
                    "status": "PASS",
                    "assertion": "The phase-skip regression is passing.",
                }
            ],
            "learning": "Phase ordering must be checked by the production validator.",
            "recurrence_signature": "A later phase starts while a predecessor is incomplete.",
            "guardrail": "Keep a child-fixture regression that skips P1.",
            "verification_ref": "tests/test_remediation_program.py::test_phase_skipping_is_rejected",
            "rollback_position": "Revert the validator and its schema together.",
            "residual_risk": "Manual artifacts outside this program remain advisory.",
            "owner": "Quality owner",
            "due_phase": "P0",
            "apivr_next_action": "Retain the regression in every certification run.",
        }
    ]
    _refresh_review(payload, payload["phases"][0])

    assert validate(_write_fixture(tmp_path, payload)) == []


def test_reviewer_contexts_must_be_distinct(tmp_path: Path) -> None:
    payload = _program()
    _complete_phase(payload, 0)
    payload["phases"][0]["review"]["verdicts"][1]["context_id"] = payload["phases"][0][
        "review"
    ]["verdicts"][0]["context_id"]
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("requires distinct reviewer identities and contexts" in item for item in errors)


def test_exclusions_and_no_direct_merge_are_immutable(tmp_path: Path) -> None:
    payload = copy.deepcopy(_program())
    payload["exclusions"] = ["something else", "another exclusion"]
    payload["direct_merge_permitted"] = True

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("must preserve explicit exclusions" in item for item in errors)
    assert any("direct_merge_permitted" in item or "direct merge" in item for item in errors)


def test_excluded_evidence_classes_cannot_be_promoted(tmp_path: Path) -> None:
    payload = _program()
    _complete_phase(payload, 0)
    payload["phases"][0]["evidence_status"]["PROVIDER"] = "PASS"
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert any("passing evidence class PROVIDER has no structured record" in item for item in errors)


def test_open_audit_finding_blocks_phase_completion(tmp_path: Path) -> None:
    payload = _program()
    _complete_phase(payload, 0)
    payload["audit_findings"][0]["status"] = "OPEN"
    payload["current_phase"] = "P1"
    payload["phases"][1]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert "P0 cannot be COMPLETE: audit finding AUD-001 is OPEN" in errors


def test_reviewer_context_cannot_be_reused_across_phases(tmp_path: Path) -> None:
    payload = _program()
    _complete_phase(payload, 0)
    _complete_phase(payload, 1)
    payload["phases"][1]["review"]["verdicts"][1]["context_id"] = payload["phases"][0][
        "review"
    ]["verdicts"][0]["context_id"]
    payload["current_phase"] = "P2"
    payload["phases"][2]["status"] = "IN_PROGRESS"

    errors = validate(_write_fixture(tmp_path, payload))

    assert "reviewer contexts cannot be reused across phases or roles" in errors
