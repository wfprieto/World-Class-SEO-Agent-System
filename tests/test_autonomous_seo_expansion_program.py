from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_autonomous_seo_expansion_program import (
    PROGRAM_PATH,
    ROOT,
    SCHEMA_PATH,
    validate_program,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _errors(program: dict) -> list[str]:
    return validate_program(program, _load(SCHEMA_PATH), ROOT)


def test_canonical_autonomous_expansion_program_passes() -> None:
    assert _errors(_load(PROGRAM_PATH)) == []


def test_rejects_direct_merge() -> None:
    program = _load(PROGRAM_PATH)
    program["direct_merge_permitted"] = True
    errors = _errors(program)
    assert any("direct_merge_permitted" in error or "direct merge" in error for error in errors)


def test_rejects_phase_skipping() -> None:
    program = _load(PROGRAM_PATH)
    program["current_phase"] = "P2"
    program["phases"][0]["status"] = "COMPLETE"
    program["phases"][0]["technical_verification"] = "PASS"
    program["phases"][1]["status"] = "NOT_STARTED"
    program["phases"][2]["status"] = "IN_PROGRESS"
    errors = _errors(program)
    assert any("P1 precedes current_phase" in error for error in errors)


def test_rejects_multiple_active_phases() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][1]["status"] = "BLOCKED"
    errors = _errors(program)
    assert any("exactly one phase" in error for error in errors)


def test_rejects_unmet_dependency_for_active_phase() -> None:
    program = _load(PROGRAM_PATH)
    program["current_phase"] = "P1"
    program["phases"][0]["status"] = "NOT_STARTED"
    program["phases"][1]["status"] = "IN_PROGRESS"
    errors = _errors(program)
    assert any("P1 cannot advance before dependency P0 is COMPLETE" in error for error in errors)


def test_rejects_write_maturity_before_write_safety() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][8]["maturity_target"] = "G4_DRAFT_WRITE_VERIFIED"
    errors = _errors(program)
    assert any("P8" in error and "write maturity" in error for error in errors)


def test_rejects_nonforensic_write_phase() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][10]["apivr_tier"] = "COMPREHENSIVE"
    errors = _errors(program)
    assert any("P10 must use FORENSIC" in error for error in errors)


def test_rejects_premature_program_verified_state() -> None:
    program = _load(PROGRAM_PATH)
    program["program_evidence_state"] = "VERIFIED"
    errors = _errors(program)
    assert any("cannot be VERIFIED before every core phase" in error for error in errors)


def test_rejects_active_extension_lane_before_dependencies() -> None:
    program = _load(PROGRAM_PATH)
    program["extension_lanes"][0]["status"] = "IN_PROGRESS"
    errors = _errors(program)
    assert any("L-A cannot advance before dependency" in error for error in errors)


def test_rejects_missing_independent_reviewer() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][0]["owners"]["independent_reviewer"] = "Implementer"
    errors = _errors(program)
    assert any("independent_reviewer" in error for error in errors)


def test_rejects_missing_rollback_contract() -> None:
    program = _load(PROGRAM_PATH)
    program["phases"][0]["rollback"] = ""
    errors = _errors(program)
    assert any("rollback" in error for error in errors)


def test_rejects_weakening_core_exclusions() -> None:
    program = _load(PROGRAM_PATH)
    program["exclusions"] = [
        "changing the current flagship",
        "unsupported outcomes",
        "unsafe automation",
    ]
    errors = _errors(program)
    assert any("program exclusions must preserve boundary" in error for error in errors)


def test_rejects_lane_order_drift() -> None:
    program = _load(PROGRAM_PATH)
    program["extension_lanes"] = list(reversed(copy.deepcopy(program["extension_lanes"])))
    errors = _errors(program)
    assert any("extension lane order" in error for error in errors)
