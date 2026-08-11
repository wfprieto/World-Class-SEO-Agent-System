from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import autonomous_seo_expansion_closure as closure
from scripts.validate_autonomous_seo_expansion_program import (
    POLICY_PATH,
    PROGRAM_PATH,
    ROOT,
    SCHEMA_PATH,
    validate_program,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _policy() -> dict:
    return _load(POLICY_PATH)


def _errors(program: dict) -> list[str]:
    return validate_program(program, _load(SCHEMA_PATH), ROOT, _policy())


def test_canonical_program_passes_while_p0_is_in_progress() -> None:
    assert _errors(_load(PROGRAM_PATH)) == []


def test_rejects_direct_merge() -> None:
    program = _load(PROGRAM_PATH)
    program["direct_merge_permitted"] = True
    assert any("direct merge" in error for error in _errors(program))


def test_rejects_phase_skipping() -> None:
    program = _load(PROGRAM_PATH)
    program["current_phase"] = "P2"
    program["phases"][2]["status"] = "IN_PROGRESS"
    program["phases"][0]["status"] = "COMPLETE"
    program["phases"][0]["technical_verification"] = "PASS"
    program["phases"][0]["outcome_verification"] = "NOT_REQUIRED"
    assert any("P1 precedes current_phase" in error for error in _errors(program))


def test_rejects_multiple_active_phases() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][1]["status"] = "BLOCKED"
    assert any("exactly one phase" in error for error in _errors(program))


def test_rejects_policy_maturity_drift() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][8]["maturity_target"] = "G4_DRAFT_WRITE_VERIFIED"
    assert any("maturity_target must match" in error for error in _errors(program))


def test_rejects_nonforensic_write_phase() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][10]["apivr_tier"] = "COMPREHENSIVE"
    assert any("P10 must use FORENSIC" in error for error in _errors(program))


def test_complete_phase_rejects_not_run_outcome() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][0]["status"] = "COMPLETE"
    program["phases"][0]["technical_verification"] = "PASS"
    program["phases"][0]["outcome_verification"] = "NOT_RUN"
    program["current_phase"] = "P1"
    program["phases"][1]["status"] = "IN_PROGRESS"
    errors = _errors(program)
    assert any("explicit PASS, NOT_REQUIRED, or PENDING" in error for error in errors)


def test_deferred_lane_requires_structured_deferral() -> None:
    program = _load(PROGRAM_PATH)
    program["extension_lanes"][0]["status"] = "DEFERRED"
    errors = _errors(program)
    assert any("deferral" in error.lower() for error in errors)


def test_program_verified_requires_final_program_closure() -> None:
    program = _load(PROGRAM_PATH)
    for phase in program["phases"]:
        phase["status"] = "COMPLETE"
        phase["technical_verification"] = "PASS"
        phase["outcome_verification"] = "PASS"
    for lane in program["extension_lanes"]:
        lane["status"] = "COMPLETE"
    program["current_phase"] = "P13"
    program["program_evidence_state"] = "VERIFIED"
    errors = closure.program_closure_errors(program, ROOT, _policy())
    assert any("program-closure" in error for error in errors)


def test_field_bounded_transition_accepts_only_phase_finalization() -> None:
    before = _load(PROGRAM_PATH)
    after = copy.deepcopy(before)
    after["phases"][0]["status"] = "COMPLETE"
    after["phases"][0]["technical_verification"] = "PASS"
    after["phases"][0]["outcome_verification"] = "NOT_REQUIRED"
    after["current_phase"] = "P1"
    after["phases"][1]["status"] = "IN_PROGRESS"
    assert closure.field_bounded_transition_errors(before, after, "P0", _policy()) == []


def test_field_bounded_transition_rejects_future_phase_policy_change() -> None:
    before = _load(PROGRAM_PATH)
    after = copy.deepcopy(before)
    after["phases"][0]["status"] = "COMPLETE"
    after["phases"][0]["technical_verification"] = "PASS"
    after["phases"][0]["outcome_verification"] = "NOT_REQUIRED"
    after["current_phase"] = "P1"
    after["phases"][1]["status"] = "IN_PROGRESS"
    after["phases"][5]["acceptance_criteria"].append("unreviewed new rule")
    errors = closure.field_bounded_transition_errors(before, after, "P0", _policy())
    assert any("P5.acceptance_criteria" in error or "unreviewed phase" in error for error in errors)


def test_field_bounded_transition_rejects_program_policy_change() -> None:
    before = _load(PROGRAM_PATH)
    after = copy.deepcopy(before)
    after["objective"] = "Changed after review " + after["objective"]
    errors = closure.field_bounded_transition_errors(before, after, "P0", _policy())
    assert any("immutable program field changed: objective" in error for error in errors)


def test_evidence_ref_rejects_hash_spoof(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("real evidence", encoding="utf-8")
    ref = {
        "kind": "repository_file",
        "path": "evidence.txt",
        "sha256": "0" * 64,
        "bound_commit": "a" * 40,
    }
    errors = closure.evidence_ref_errors([ref], tmp_path, "a" * 40)
    assert any("hash mismatch" in error for error in errors)


def test_evidence_ref_rejects_candidate_mismatch(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("real evidence", encoding="utf-8")
    ref = {
        "kind": "repository_file",
        "path": "evidence.txt",
        "sha256": closure.file_sha256(evidence),
        "bound_commit": "b" * 40,
    }
    errors = closure.evidence_ref_errors([ref], tmp_path, "a" * 40)
    assert any("not bound to candidate" in error for error in errors)


def test_reviewer_contexts_must_be_independent() -> None:
    evidence_hash = "a" * 64
    closure_payload = {"builder_context_id": "builder-0001", "evidence_package_hash": evidence_hash}
    verdicts = [
        {
            "reviewer_id": "senior-scrummaster-3",
            "role": "SENIOR_SCRUMMASTER_3",
            "context_id": "builder-0001",
            "evidence_package_hash": evidence_hash,
            "verdict": "APPROVE_GREAT",
        },
        {
            "reviewer_id": "vp-engineering",
            "role": "VP_ENGINEERING",
            "context_id": "review-0002",
            "evidence_package_hash": evidence_hash,
            "verdict": "APPROVE_GREAT",
        },
    ]
    assert any("reviewer contexts" in error for error in closure.reviewer_independence_errors(closure_payload, verdicts))


def test_rejects_lane_order_drift() -> None:
    program = _load(PROGRAM_PATH)
    program["extension_lanes"] = list(reversed(program["extension_lanes"]))
    assert any("extension lane order" in error for error in _errors(program))
