"""Validate the governed WCSEO autonomous SEO expansion program."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts import autonomous_seo_expansion_closure as closure

ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PATH = ROOT / "evaluation" / "remediation" / "autonomous-seo-expansion-program.json"
POLICY_PATH = ROOT / "evaluation" / "remediation" / "autonomous-seo-expansion-policy.json"
SCHEMA_PATH = ROOT / "schemas" / "autonomous-seo-expansion-program.schema.json"
POLICY_SCHEMA_PATH = ROOT / "schemas" / "autonomous-seo-expansion-policy.schema.json"
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


def _sequence_errors(program: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    phases = [phase for phase in program.get("phases", []) if isinstance(phase, dict)]
    order = list(policy["phase_order"])
    ids = [phase.get("id") for phase in phases]
    if ids != order:
        return [f"phase order must match canonical lifecycle policy {order}; found {ids}"]
    errors = _active_phase_errors(program, phases, order)
    errors.extend(_dependency_errors(phases, order))
    return errors


def _active_phase_errors(
    program: dict[str, Any], phases: list[dict[str, Any]], order: list[str]
) -> list[str]:
    current = str(program.get("current_phase", ""))
    if current not in order:
        return ["current_phase is not a canonical phase id"]
    all_complete = all(phase.get("status") == "COMPLETE" for phase in phases)
    active = [phase for phase in phases if phase.get("status") in {"IN_PROGRESS", "BLOCKED"}]
    if all_complete:
        errors = [] if not active else ["a completed program cannot retain an active phase"]
        if current != order[-1]:
            errors.append(f"a completed program must leave current_phase at {order[-1]}")
        return errors
    errors: list[str] = []
    if len(active) != 1:
        errors.append("exactly one phase must be IN_PROGRESS or BLOCKED before completion")
    elif active[0].get("id") != current:
        errors.append("current_phase must identify the sole active or blocked phase")
    current_index = order.index(current)
    for index, phase in enumerate(phases):
        status = phase.get("status")
        if index < current_index and status != "COMPLETE":
            errors.append(f"{phase['id']} precedes current_phase and must be COMPLETE")
        elif index == current_index and status not in {"IN_PROGRESS", "BLOCKED"}:
            errors.append(f"{phase['id']} is current_phase and must be IN_PROGRESS or BLOCKED")
        elif index > current_index and status != "NOT_STARTED":
            errors.append(f"{phase['id']} follows current_phase and must be NOT_STARTED")
    return errors


def _dependency_errors(phases: list[dict[str, Any]], order: list[str]) -> list[str]:
    index = {phase_id: position for position, phase_id in enumerate(order)}
    statuses = {str(phase.get("id")): str(phase.get("status")) for phase in phases}
    errors: list[str] = []
    for phase in phases:
        phase_id = str(phase.get("id"))
        for dependency in phase.get("depends_on", []):
            if dependency not in index:
                errors.append(f"{phase_id} depends on unknown phase {dependency}")
                continue
            if index[dependency] >= index[phase_id]:
                errors.append(f"{phase_id} dependency {dependency} must precede the phase")
            if phase.get("status") in {"IN_PROGRESS", "BLOCKED", "COMPLETE"} and statuses.get(dependency) != "COMPLETE":
                errors.append(f"{phase_id} cannot advance before dependency {dependency} is COMPLETE")
    return errors


def _maturity_errors(program: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if program.get("capability_maturity_order") != policy.get("maturity_order"):
        errors.append("program maturity order must mirror the canonical lifecycle policy")
    targets = policy["phase_maturity_targets"]
    forensic = set(policy["forensic_phases"])
    write_index = policy["phase_order"].index(policy["write_safety_phase"])
    maturity_order = list(policy["maturity_order"])
    draft_index = maturity_order.index("G4_DRAFT_WRITE_VERIFIED")
    for phase in program.get("phases", []):
        if not isinstance(phase, dict):
            continue
        phase_id = str(phase.get("id"))
        maturity = str(phase.get("maturity_target"))
        if targets.get(phase_id) != maturity:
            errors.append(f"{phase_id} maturity_target must match canonical lifecycle policy")
        if phase_id in forensic and phase.get("apivr_tier") != "FORENSIC":
            errors.append(f"{phase_id} must use FORENSIC APIVR")
        phase_index = policy["phase_order"].index(phase_id)
        if phase_index < write_index and maturity_order.index(maturity) >= draft_index:
            errors.append(f"{phase_id} cannot target write maturity before write-safety phase")
    return errors


def _completion_errors(
    program: dict[str, Any], root: Path, policy: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    allowed_outcomes = set(policy["complete_phase_allowed_outcomes"])
    for phase in program.get("phases", []):
        if not isinstance(phase, dict) or phase.get("status") != "COMPLETE":
            continue
        phase_id = str(phase.get("id"))
        if phase.get("technical_verification") != "PASS":
            errors.append(f"{phase_id} cannot be COMPLETE without technical_verification PASS")
        if phase.get("outcome_verification") not in allowed_outcomes:
            errors.append(f"{phase_id} COMPLETE requires explicit PASS, NOT_REQUIRED, or PENDING outcome state")
        if phase_id in set(policy["outcome_pass_required_phases"]) and phase.get("outcome_verification") != "PASS":
            errors.append(f"{phase_id} requires outcome_verification PASS")
        errors.extend(closure.phase_closure_errors(phase, root, policy))
    errors.extend(_program_terminal_errors(program, root, policy))
    return errors


def _program_terminal_errors(
    program: dict[str, Any], root: Path, policy: dict[str, Any]
) -> list[str]:
    phases = program.get("phases", [])
    all_complete = all(isinstance(phase, dict) and phase.get("status") == "COMPLETE" for phase in phases)
    evidence_state = program.get("program_evidence_state")
    errors: list[str] = []
    if evidence_state == "VERIFIED" and not all_complete:
        errors.append("program_evidence_state cannot be VERIFIED before every core phase is COMPLETE")
    if all_complete and evidence_state != "VERIFIED":
        errors.append("all core phases COMPLETE requires program_evidence_state VERIFIED")
    if evidence_state == "VERIFIED":
        unresolved = [
            str(lane.get("id"))
            for lane in program.get("extension_lanes", [])
            if isinstance(lane, dict) and lane.get("status") not in {"COMPLETE", "DEFERRED"}
        ]
        if unresolved:
            errors.append(f"program VERIFIED requires every extension lane COMPLETE or DEFERRED: {unresolved}")
        errors.extend(closure.program_closure_errors(program, root, policy))
    return errors


def _lane_errors(
    program: dict[str, Any], root: Path, policy: dict[str, Any]
) -> list[str]:
    lanes = [lane for lane in program.get("extension_lanes", []) if isinstance(lane, dict)]
    expected = list(policy["extension_lane_order"])
    ids = [lane.get("id") for lane in lanes]
    if ids != expected:
        return [f"extension lane order must match canonical lifecycle policy {expected}; found {ids}"]
    phase_status = {
        str(phase.get("id")): str(phase.get("status"))
        for phase in program.get("phases", [])
        if isinstance(phase, dict)
    }
    errors: list[str] = []
    for lane in lanes:
        if lane.get("status") in {"IN_PROGRESS", "COMPLETE"}:
            for dependency in lane.get("depends_on", []):
                if phase_status.get(dependency) != "COMPLETE":
                    errors.append(f"{lane['id']} cannot advance before dependency {dependency} is COMPLETE")
        if lane.get("status") == "DEFERRED":
            deferral = lane.get("deferral", {})
            candidate = str(deferral.get("evidence_refs", [{}])[0].get("bound_commit", "")) if deferral.get("evidence_refs") else ""
            errors.extend(closure.evidence_ref_errors(deferral.get("evidence_refs", []), root, candidate))
    return errors


def _governance_errors(program: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if program.get("direct_merge_permitted") is not False:
        errors.append("direct merge is forbidden for the autonomous expansion program")
    close_blob = "\n".join(str(item) for item in program.get("phase_close_requires", [])).lower()
    for marker in ESSENTIAL_CLOSE_CONTROLS:
        if marker.lower() not in close_blob:
            errors.append(f"phase_close_requires is missing essential control: {marker}")
    exclusion_blob = "\n".join(str(item) for item in program.get("exclusions", [])).lower()
    for marker in ("read-only flagship", "ranking", "pbn", "global autonomy"):
        if marker not in exclusion_blob:
            errors.append(f"program exclusions is missing essential control: {marker}")
    return errors


def validate_program(
    program: dict[str, Any],
    schema: dict[str, Any],
    root: Path = ROOT,
    policy: dict[str, Any] | None = None,
) -> list[str]:
    policy = policy or closure.load_object(root / POLICY_PATH.relative_to(ROOT))
    errors = closure.schema_errors(program, schema)
    errors.extend(closure.schema_errors(policy, closure.load_object(root / POLICY_SCHEMA_PATH.relative_to(ROOT)), "lifecycle policy"))
    if errors:
        return errors
    errors.extend(_baseline_errors(program, root))
    errors.extend(_sequence_errors(program, policy))
    errors.extend(_maturity_errors(program, policy))
    errors.extend(_completion_errors(program, root, policy))
    errors.extend(_governance_errors(program))
    errors.extend(_lane_errors(program, root, policy))
    return errors


def main() -> int:
    program = closure.load_object(PROGRAM_PATH)
    policy = closure.load_object(POLICY_PATH)
    errors = validate_program(program, closure.load_object(SCHEMA_PATH), ROOT, policy)
    if errors:
        print("Autonomous SEO expansion program validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Autonomous SEO expansion program validation passed; live and outcome claims remain separately gated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
