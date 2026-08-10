"""Validate the governed WCSEO autonomous SEO expansion program."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts import autonomous_seo_expansion_closure as closure


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


def _baseline_errors(program: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    baseline = program.get("baseline", {})
    commit = str(baseline.get("commit", ""))
    if baseline.get("branch") != "main":
        errors.append("baseline branch must remain main")
    if baseline.get("working_branch") == "main":
        errors.append("working_branch must not be main")
    if (
        (root / ".git").exists()
        and len(commit) == 40
        and not closure.git_command_ok(root, ["merge-base", "--is-ancestor", commit, "HEAD"])
    ):
        errors.append("baseline commit must be an immutable ancestor of the candidate HEAD")
    return errors


def _phase_order_errors(phases: list[dict[str, Any]]) -> list[str]:
    ids = [phase.get("id") for phase in phases]
    if ids == PHASE_IDS:
        return []
    return [f"phase order must be {PHASE_IDS}; found {ids}"]


def _active_phase_errors(program: dict[str, Any], phases: list[dict[str, Any]]) -> list[str]:
    current = str(program.get("current_phase", ""))
    if current not in PHASE_IDS:
        return ["current_phase is not a canonical phase id"]
    all_complete = all(phase.get("status") == "COMPLETE" for phase in phases)
    active = [phase for phase in phases if phase.get("status") in {"IN_PROGRESS", "BLOCKED"}]
    if all_complete:
        return _completed_program_phase_state_errors(current, active)
    return _in_progress_phase_state_errors(current, active, phases)


def _completed_program_phase_state_errors(
    current: str,
    active: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if active:
        errors.append("a completed program cannot retain an IN_PROGRESS or BLOCKED phase")
    if current != "P13":
        errors.append("a completed program must leave current_phase at P13")
    return errors


def _in_progress_phase_state_errors(
    current: str,
    active: list[dict[str, Any]],
    phases: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    if len(active) != 1:
        errors.append("exactly one phase must be IN_PROGRESS or BLOCKED before completion")
    elif active[0].get("id") != current:
        errors.append("current_phase must identify the sole active or blocked phase")
    current_index = PHASE_IDS.index(current)
    for index, phase in enumerate(phases):
        errors.extend(_relative_phase_state_errors(phase, index, current_index))
    return errors


def _relative_phase_state_errors(
    phase: dict[str, Any],
    index: int,
    current_index: int,
) -> list[str]:
    phase_id = str(phase.get("id"))
    status = phase.get("status")
    if index < current_index and status != "COMPLETE":
        return [f"{phase_id} precedes current_phase and must be COMPLETE"]
    if index == current_index and status not in {"IN_PROGRESS", "BLOCKED"}:
        return [f"{phase_id} is current_phase and must be IN_PROGRESS or BLOCKED"]
    if index > current_index and status != "NOT_STARTED":
        return [f"{phase_id} follows current_phase and must be NOT_STARTED"]
    return []


def _dependency_errors(phases: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    phase_index = {phase_id: index for index, phase_id in enumerate(PHASE_IDS)}
    status_by_id = {str(phase.get("id")): str(phase.get("status")) for phase in phases}
    for phase in phases:
        errors.extend(_one_phase_dependency_errors(phase, phase_index, status_by_id))
    return errors


def _one_phase_dependency_errors(
    phase: dict[str, Any],
    phase_index: dict[str, int],
    status_by_id: dict[str, str],
) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase.get("id"))
    for dependency in phase.get("depends_on", []):
        if dependency not in phase_index:
            errors.append(f"{phase_id} depends on unknown phase {dependency}")
            continue
        if phase_index[dependency] >= phase_index[phase_id]:
            errors.append(f"{phase_id} dependency {dependency} must precede the phase")
        if _dependency_must_be_complete(phase, status_by_id, dependency):
            errors.append(f"{phase_id} cannot advance before dependency {dependency} is COMPLETE")
    return errors


def _dependency_must_be_complete(
    phase: dict[str, Any],
    status_by_id: dict[str, str],
    dependency: str,
) -> bool:
    active_states = {"IN_PROGRESS", "BLOCKED", "COMPLETE"}
    return phase.get("status") in active_states and status_by_id.get(dependency) != "COMPLETE"


def _sequence_errors(program: dict[str, Any]) -> list[str]:
    phases = [phase for phase in program.get("phases", []) if isinstance(phase, dict)]
    errors = _phase_order_errors(phases)
    if errors:
        return errors
    return _active_phase_errors(program, phases) + _dependency_errors(phases)


def _maturity_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if program.get("capability_maturity_order") != MATURITY_ORDER:
        errors.append("capability maturity order must remain the canonical G0 through G6 sequence")
    for phase in program.get("phases", []):
        if isinstance(phase, dict):
            errors.extend(_one_phase_maturity_errors(phase))
    return errors


def _one_phase_maturity_errors(phase: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    phase_id = str(phase.get("id"))
    maturity = str(phase.get("maturity_target"))
    if EXPECTED_MATURITY.get(phase_id) != maturity:
        errors.append(
            f"{phase_id} maturity_target must be {EXPECTED_MATURITY.get(phase_id)}; "
            f"found {maturity}"
        )
    if phase_id in REQUIRED_FORENSIC_PHASES and phase.get("apivr_tier") != "FORENSIC":
        errors.append(f"{phase_id} must use FORENSIC APIVR because it governs writes or autonomy")
    if phase_id in PHASE_IDS[:10] and maturity in WRITE_MATURITY:
        errors.append(f"{phase_id} cannot target write maturity before write-safety Phase P10")
    return errors


def _completed_phase_errors(phase: dict[str, Any], root: Path) -> list[str]:
    if phase.get("status") != "COMPLETE":
        return []
    phase_id = str(phase.get("id"))
    errors: list[str] = []
    if phase.get("technical_verification") != "PASS":
        errors.append(f"{phase_id} cannot be COMPLETE without technical_verification PASS")
    if phase.get("outcome_verification") in {"FAIL", "BLOCKED", "PARTIAL"}:
        errors.append(f"{phase_id} cannot be COMPLETE with unresolved outcome_verification")
    errors.extend(closure.phase_closure_errors(phase, root))
    return errors


def _program_terminal_errors(program: dict[str, Any]) -> list[str]:
    phases = program.get("phases", [])
    all_complete = all(
        isinstance(phase, dict) and phase.get("status") == "COMPLETE" for phase in phases
    )
    evidence_state = program.get("program_evidence_state")
    errors: list[str] = []
    if evidence_state == "VERIFIED" and not all_complete:
        errors.append("program_evidence_state cannot be VERIFIED before every core phase is COMPLETE")
    if all_complete and evidence_state != "VERIFIED":
        errors.append("all core phases COMPLETE requires program_evidence_state VERIFIED")
    if evidence_state == "VERIFIED":
        errors.extend(_terminal_lane_errors(program))
    return errors


def _terminal_lane_errors(program: dict[str, Any]) -> list[str]:
    unresolved = [
        str(lane.get("id"))
        for lane in program.get("extension_lanes", [])
        if isinstance(lane, dict) and lane.get("status") not in {"COMPLETE", "DEFERRED"}
    ]
    if unresolved:
        return [f"program VERIFIED requires every extension lane COMPLETE or DEFERRED: {unresolved}"]
    return []


def _completion_errors(program: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    for phase in program.get("phases", []):
        if isinstance(phase, dict):
            errors.extend(_completed_phase_errors(phase, root))
    errors.extend(_program_terminal_errors(program))
    return errors


def _governance_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if program.get("direct_merge_permitted") is not False:
        errors.append("direct merge is forbidden for the autonomous expansion program")
    close_blob = "\n".join(str(item) for item in program.get("phase_close_requires", [])).lower()
    errors.extend(
        _required_marker_errors(close_blob, ESSENTIAL_CLOSE_CONTROLS, "phase_close_requires")
    )
    exclusion_blob = "\n".join(str(item) for item in program.get("exclusions", [])).lower()
    required_boundaries = ("read-only flagship", "ranking", "pbn", "global autonomy")
    errors.extend(
        _required_marker_errors(exclusion_blob, required_boundaries, "program exclusions")
    )
    return errors


def _required_marker_errors(blob: str, markers: tuple[str, ...], label: str) -> list[str]:
    return [
        f"{label} is missing essential control: {marker}"
        for marker in markers
        if marker.lower() not in blob
    ]


def _lane_errors(program: dict[str, Any]) -> list[str]:
    lanes = [lane for lane in program.get("extension_lanes", []) if isinstance(lane, dict)]
    ids = [lane.get("id") for lane in lanes]
    if ids != LANE_IDS:
        return [f"extension lane order must be {LANE_IDS}; found {ids}"]
    phase_status = {
        str(phase.get("id")): str(phase.get("status"))
        for phase in program.get("phases", [])
        if isinstance(phase, dict)
    }
    errors: list[str] = []
    for lane in lanes:
        errors.extend(_one_lane_dependency_errors(lane, phase_status))
    return errors


def _one_lane_dependency_errors(
    lane: dict[str, Any],
    phase_status: dict[str, str],
) -> list[str]:
    if lane.get("status") not in {"IN_PROGRESS", "COMPLETE"}:
        return []
    return [
        f"{lane['id']} cannot advance before dependency {dependency} is COMPLETE"
        for dependency in lane.get("depends_on", [])
        if phase_status.get(dependency) != "COMPLETE"
    ]


def validate_program(
    program: dict[str, Any],
    schema: dict[str, Any],
    root: Path = ROOT,
) -> list[str]:
    errors = closure.schema_errors(program, schema)
    if errors:
        return errors
    errors = _baseline_errors(program, root)
    errors.extend(_sequence_errors(program))
    errors.extend(_maturity_errors(program))
    errors.extend(_completion_errors(program, root))
    errors.extend(_governance_errors(program))
    errors.extend(_lane_errors(program))
    return errors


def main() -> int:
    program = closure.load_object(PROGRAM_PATH)
    errors = validate_program(program, closure.load_object(SCHEMA_PATH))
    if errors:
        print("Autonomous SEO expansion program validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "Autonomous SEO expansion program validation passed. "
        "This proves program-contract integrity only; future live reads, writes, "
        "and SEO outcomes remain separately gated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
