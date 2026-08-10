"""Validate the governed WCSEO autonomous SEO expansion program.

This validator intentionally governs only the expansion program contract. It does not
claim that any future provider, write, ranking, traffic, conversion, local, or AI-search
outcome is verified merely because the program is structurally valid.
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PATH = ROOT / "evaluation" / "remediation" / "autonomous-seo-expansion-program.json"
SCHEMA_PATH = ROOT / "schemas" / "autonomous-seo-expansion-program.schema.json"
PHASE_IDS = [f"P{index}" for index in range(14)]
LANE_IDS = ["L-A", "L-B", "L-C", "L-D"]
MATURITY_ORDER = [
    "G0_DOCUMENTED",
    "G1_FIXTURE_VERIFIED",
    "G2_SHADOW_VERIFIED",
    "G3_LIVE_READ_VERIFIED",
    "G4_DRAFT_WRITE_VERIFIED",
    "G5_CANARY_WRITE_VERIFIED",
    "G6_BOUNDED_AUTONOMOUS",
]
REQUIRED_FORENSIC_PHASES = {"P10", "P11", "P12", "P13"}
EXPECTED_MATURITY = {
    "P0": "G0_DOCUMENTED",
    "P1": "G1_FIXTURE_VERIFIED",
    "P2": "G1_FIXTURE_VERIFIED",
    "P3": "G1_FIXTURE_VERIFIED",
    "P4": "G3_LIVE_READ_VERIFIED",
    "P5": "G3_LIVE_READ_VERIFIED",
    "P6": "G2_SHADOW_VERIFIED",
    "P7": "G2_SHADOW_VERIFIED",
    "P8": "G2_SHADOW_VERIFIED",
    "P9": "G2_SHADOW_VERIFIED",
    "P10": "G1_FIXTURE_VERIFIED",
    "P11": "G4_DRAFT_WRITE_VERIFIED",
    "P12": "G5_CANARY_WRITE_VERIFIED",
    "P13": "G6_BOUNDED_AUTONOMOUS",
}
WRITE_MATURITY = {
    "G4_DRAFT_WRITE_VERIFIED",
    "G5_CANARY_WRITE_VERIFIED",
    "G6_BOUNDED_AUTONOMOUS",
}
ESSENTIAL_CLOSE_CONTROLS = (
    "exact source baseline",
    "implementation audit",
    "regression tests",
    "repository and schema validators",
    "rollback",
    "Senior ScrumMaster 3",
    "VP Engineering",
    "technical verification",
    "re-audit",
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return payload


def _schema_errors(program: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    Draft202012Validator.check_schema(schema)
    normalized = copy.deepcopy(program)
    normalized.pop("$schema", None)
    validator = Draft202012Validator(schema)
    return [
        f"schema {'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(normalized), key=lambda item: list(item.absolute_path))
    ]


def _baseline_errors(program: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    baseline = program.get("baseline", {})
    commit = str(baseline.get("commit", ""))
    if baseline.get("branch") != "main":
        errors.append("baseline branch must remain main")
    if baseline.get("working_branch") == "main":
        errors.append("working_branch must not be main")
    if (root / ".git").exists() and len(commit) == 40:
        try:
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                timeout=20,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            errors.append("baseline commit must be an immutable ancestor of the candidate HEAD")
    return errors


def _sequence_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    phases = program.get("phases", [])
    ids = [phase.get("id") for phase in phases if isinstance(phase, dict)]
    if ids != PHASE_IDS:
        return [f"phase order must be {PHASE_IDS}; found {ids}"]

    active = [phase for phase in phases if phase.get("status") in {"IN_PROGRESS", "BLOCKED"}]
    if len(active) != 1:
        errors.append("exactly one phase must be IN_PROGRESS or BLOCKED until all phases are COMPLETE")
    current = str(program.get("current_phase", ""))
    if active and active[0].get("id") != current:
        errors.append("current_phase must identify the sole active or blocked phase")
    if current not in PHASE_IDS:
        errors.append("current_phase is not a canonical phase id")
        return errors

    current_index = PHASE_IDS.index(current)
    all_complete = all(phase.get("status") == "COMPLETE" for phase in phases)
    if all_complete:
        if current != "P13":
            errors.append("a completed program must leave current_phase at P13")
    else:
        for index, phase in enumerate(phases):
            status = phase.get("status")
            if index < current_index and status != "COMPLETE":
                errors.append(f"{phase['id']} precedes current_phase and must be COMPLETE")
            if index == current_index and status not in {"IN_PROGRESS", "BLOCKED"}:
                errors.append(f"{phase['id']} is current_phase and must be IN_PROGRESS or BLOCKED")
            if index > current_index and status != "NOT_STARTED":
                errors.append(f"{phase['id']} follows current_phase and must be NOT_STARTED")

    phase_index = {phase_id: index for index, phase_id in enumerate(PHASE_IDS)}
    status_by_id = {str(phase.get("id")): str(phase.get("status")) for phase in phases}
    for phase in phases:
        phase_id = str(phase.get("id"))
        for dependency in phase.get("depends_on", []):
            if dependency not in phase_index:
                errors.append(f"{phase_id} depends on unknown phase {dependency}")
                continue
            if phase_index[dependency] >= phase_index[phase_id]:
                errors.append(f"{phase_id} dependency {dependency} must precede the phase")
            if phase.get("status") in {"IN_PROGRESS", "BLOCKED", "COMPLETE"} and status_by_id.get(dependency) != "COMPLETE":
                errors.append(f"{phase_id} cannot advance before dependency {dependency} is COMPLETE")
    return errors


def _maturity_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if program.get("capability_maturity_order") != MATURITY_ORDER:
        errors.append("capability maturity order must remain the canonical G0 through G6 sequence")
    phases = program.get("phases", [])
    for phase in phases:
        phase_id = str(phase.get("id"))
        maturity = str(phase.get("maturity_target"))
        if EXPECTED_MATURITY.get(phase_id) != maturity:
            errors.append(
                f"{phase_id} maturity_target must be {EXPECTED_MATURITY.get(phase_id)}; found {maturity}"
            )
        if phase_id in REQUIRED_FORENSIC_PHASES and phase.get("apivr_tier") != "FORENSIC":
            errors.append(f"{phase_id} must use FORENSIC APIVR because it governs external writes or autonomy")
        if int(phase_id[1:]) < 10 and maturity in WRITE_MATURITY:
            errors.append(f"{phase_id} cannot target write maturity before write-safety Phase P10")
    return errors


def _completion_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    phases = program.get("phases", [])
    for phase in phases:
        if phase.get("status") != "COMPLETE":
            continue
        phase_id = str(phase.get("id"))
        if phase.get("technical_verification") != "PASS":
            errors.append(f"{phase_id} cannot be COMPLETE without technical_verification PASS")
        if phase.get("outcome_verification") in {"FAIL", "BLOCKED", "PARTIAL"}:
            errors.append(f"{phase_id} cannot be COMPLETE with unresolved outcome_verification")
        if not phase.get("rollback") or len(str(phase.get("rollback")).strip()) < 12:
            errors.append(f"{phase_id} cannot be COMPLETE without a rollback or containment contract")
        if len(phase.get("stop_conditions", [])) < 2:
            errors.append(f"{phase_id} cannot be COMPLETE without stop conditions")

    all_complete = all(phase.get("status") == "COMPLETE" for phase in phases)
    evidence_state = program.get("program_evidence_state")
    if evidence_state == "VERIFIED" and not all_complete:
        errors.append("program_evidence_state cannot be VERIFIED before every core phase is COMPLETE")
    if all_complete and evidence_state != "VERIFIED":
        errors.append("all core phases COMPLETE requires program_evidence_state VERIFIED")
    return errors


def _governance_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if program.get("direct_merge_permitted") is not False:
        errors.append("direct merge is forbidden for the autonomous expansion program")

    close_controls = [str(item) for item in program.get("phase_close_requires", [])]
    close_blob = "\n".join(close_controls).lower()
    for marker in ESSENTIAL_CLOSE_CONTROLS:
        if marker.lower() not in close_blob:
            errors.append(f"phase_close_requires is missing essential control: {marker}")

    exclusions = "\n".join(str(item) for item in program.get("exclusions", [])).lower()
    for required in (
        "read-only flagship",
        "ranking",
        "pbn",
        "global autonomy",
    ):
        if required not in exclusions:
            errors.append(f"program exclusions must preserve boundary: {required}")
    return errors


def _lane_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lanes = program.get("extension_lanes", [])
    ids = [lane.get("id") for lane in lanes if isinstance(lane, dict)]
    if ids != LANE_IDS:
        errors.append(f"extension lane order must be {LANE_IDS}; found {ids}")
        return errors
    phase_status = {
        str(phase.get("id")): str(phase.get("status")) for phase in program.get("phases", [])
    }
    for lane in lanes:
        if lane.get("status") in {"IN_PROGRESS", "COMPLETE"}:
            for dependency in lane.get("depends_on", []):
                if phase_status.get(dependency) != "COMPLETE":
                    errors.append(
                        f"{lane['id']} cannot advance before dependency {dependency} is COMPLETE"
                    )
    return errors


def validate_program(program: dict[str, Any], schema: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    errors.extend(_schema_errors(program, schema))
    if errors:
        return errors
    errors.extend(_baseline_errors(program, root))
    errors.extend(_sequence_errors(program))
    errors.extend(_maturity_errors(program))
    errors.extend(_completion_errors(program))
    errors.extend(_governance_errors(program))
    errors.extend(_lane_errors(program))
    return errors


def main() -> int:
    program = _load(PROGRAM_PATH)
    schema = _load(SCHEMA_PATH)
    errors = validate_program(program, schema)
    if errors:
        print("Autonomous SEO expansion program validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Autonomous SEO expansion program validation passed. "
        "This proves program-contract integrity only; future live reads, writes, and SEO outcomes remain separately gated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
