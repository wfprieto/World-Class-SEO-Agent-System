from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

from scripts import autonomous_seo_expansion_closure as closure
from scripts.validate_autonomous_seo_expansion_program import validate_program

ROOT = Path(__file__).resolve().parents[1]


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True, timeout=20
    )
    return result.stdout.strip()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _phase(phase_id: str, status: str, dependency: list[str]) -> dict:
    return {
        "id": phase_id,
        "title": f"Phase {phase_id} test contract",
        "status": status,
        "apivr_tier": "COMPREHENSIVE",
        "objective": "Exercise the real autonomous phase closure validation path.",
        "depends_on": dependency,
        "owners": {
            "lead": "Test owner",
            "scrummaster": "Senior ScrumMaster 3",
            "independent_reviewer": "VP Engineering",
        },
        "scope": ["closure validation"],
        "non_goals": ["production mutation"],
        "maturity_target": "G0_DOCUMENTED" if phase_id == "P0" else "G1_FIXTURE_VERIFIED",
        "acceptance_criteria": ["Valid closure passes all gates", "Spoofed closure fails closed"],
        "rollback": "Revert the temporary test repository commit safely.",
        "stop_conditions": ["Evidence mismatch is observed", "Reviewer independence is violated"],
        "technical_verification": "NOT_RUN",
        "outcome_verification": "NOT_RUN",
    }


def _policy() -> dict:
    return {
        "$schema": "../../schemas/autonomous-seo-expansion-policy.schema.json",
        "schema_version": "1.0.0",
        "policy_id": "autonomous-seo-expansion-lifecycle",
        "phase_order": ["P0", "P1"],
        "extension_lane_order": ["L-A"],
        "maturity_order": ["G0_DOCUMENTED", "G1_FIXTURE_VERIFIED", "G4_DRAFT_WRITE_VERIFIED"],
        "phase_maturity_targets": {"P0": "G0_DOCUMENTED", "P1": "G1_FIXTURE_VERIFIED"},
        "forensic_phases": [],
        "write_safety_phase": "P1",
        "outcome_pass_required_phases": [],
        "complete_phase_allowed_outcomes": ["PASS", "NOT_REQUIRED", "PENDING"],
        "final_program_closure_required": True,
        "final_program_reviewer_roles": ["SENIOR_SCRUMMASTER_3", "VP_ENGINEERING"],
        "post_review_program_transition": {
            "reviewed_phase_status_from": ["IN_PROGRESS", "BLOCKED"],
            "reviewed_phase_status_to": "COMPLETE",
            "technical_verification_to": "PASS",
            "next_phase_status_from": "NOT_STARTED",
            "next_phase_status_to": "IN_PROGRESS",
            "immutable_fields": [
                "schema_version",
                "program_id",
                "objective",
                "baseline",
                "apivr_tier",
                "direct_merge_permitted",
                "capability_maturity_order",
                "phase_close_requires",
                "scope",
                "exclusions",
            ],
            "immutable_phase_fields": [
                "id",
                "title",
                "apivr_tier",
                "objective",
                "depends_on",
                "owners",
                "scope",
                "non_goals",
                "maturity_target",
                "acceptance_criteria",
                "rollback",
                "stop_conditions",
            ],
            "immutable_lane_fields": [
                "id",
                "title",
                "depends_on",
                "owner",
                "maturity_ceiling_without_separate_authorization",
                "scope",
            ],
        },
    }


def _program(baseline: str) -> dict:
    return {
        "$schema": "../../schemas/autonomous-seo-expansion-program.schema.json",
        "schema_version": "1.0.0",
        "program_id": "autonomous-seo-expansion",
        "objective": "Exercise a complete governed autonomous SEO phase transition with immutable evidence.",
        "baseline": {
            "commit": baseline,
            "branch": "main",
            "working_branch": "agent/test",
            "captured_at": "2026-08-11T12:00:00Z",
        },
        "apivr_tier": "COMPREHENSIVE",
        "current_phase": "P0",
        "direct_merge_permitted": False,
        "capability_maturity_order": [
            "G0_DOCUMENTED",
            "G1_FIXTURE_VERIFIED",
            "G4_DRAFT_WRITE_VERIFIED",
        ],
        "phase_close_requires": [
            "exact source baseline recorded",
            "implementation audit completed",
            "regression tests pass",
            "repository and schema validators pass",
            "rollback demonstrated",
            "Senior ScrumMaster 3 returns APPROVE_GREAT",
            "VP Engineering independently approves",
            "technical verification complete",
            "re-audit complete",
        ],
        "scope": ["phase closure", "evidence binding", "review independence", "state transition"],
        "exclusions": [
            "preserve read-only flagship",
            "no unsupported ranking claims",
            "no pbn search spam",
            "no global autonomy switch",
        ],
        "phases": [_phase("P0", "IN_PROGRESS", []), _phase("P1", "NOT_STARTED", ["P0"])],
        "extension_lanes": [
            {
                "id": "L-A",
                "title": "Test extension lane",
                "status": "NOT_STARTED",
                "depends_on": ["P0"],
                "owner": "Test owner",
                "maturity_ceiling_without_separate_authorization": "G1_FIXTURE_VERIFIED",
                "scope": ["test lane"],
            }
        ],
        "program_evidence_state": "NOT_RUN",
    }


def _copy_schemas(root: Path) -> None:
    for name in (
        "autonomous-seo-expansion-program.schema.json",
        "autonomous-seo-expansion-policy.schema.json",
        "autonomous-seo-phase-closure.schema.json",
        "autonomous-seo-reviewer-provenance.schema.json",
        "reviewer-verdict.schema.json",
    ):
        target = root / "schemas" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "schemas" / name, target)


def _setup_candidate(tmp_path: Path) -> tuple[Path, str, dict, dict, list[dict]]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "WCSEO Test")
    (root / "baseline.txt").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    baseline = _git(root, "rev-parse", "HEAD")
    _copy_schemas(root)
    policy = _policy()
    program = _program(baseline)
    _write_json(root / "evaluation/remediation/autonomous-seo-expansion-policy.json", policy)
    _write_json(root / closure.PROGRAM_RELATIVE, program)
    evidence_refs: list[dict] = []
    for index in range(3):
        relative = f"evaluation/remediation/evidence-{index}.txt"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"immutable evidence {index}\n", encoding="utf-8")
        evidence_refs.append({
            "kind": "repository_file",
            "path": relative,
            "sha256": "pending",
            "bound_commit": "pending",
        })
    _git(root, "add", ".")
    _git(root, "commit", "-m", "candidate")
    candidate = _git(root, "rev-parse", "HEAD")
    for ref in evidence_refs:
        ref["sha256"] = closure.file_sha256(root / ref["path"])
        ref["bound_commit"] = candidate
    return root, candidate, program, policy, evidence_refs


def _reviewer_verdict(
    reviewer_id: str, role: str, context: str, evidence_hash: str
) -> dict:
    return {
        "review_id": f"P0-{reviewer_id}",
        "reviewer_id": reviewer_id,
        "role": role,
        "context_id": context,
        "provider": "test-provider",
        "model": "test-model",
        "evidence_package_hash": evidence_hash,
        "verdict": "APPROVE_GREAT",
        "strongest_objections": [
            "objection one resolved",
            "objection two resolved",
            "objection three resolved",
        ],
        "evidence_refs": ["candidate diff", "canonical tests"],
        "submitted_at": "2026-08-11T12:30:00Z",
        "saw_other_reviewer_verdict": False,
        "is_builder": False,
    }


def _reviewer_provenance(
    reviewer_id: str,
    role: str,
    context: str,
    candidate: str,
    evidence_hash: str,
    execution_id: str,
) -> dict:
    return {
        "$schema": "../../schemas/autonomous-seo-reviewer-provenance.schema.json",
        "schema_version": "1.0.0",
        "receipt_id": f"receipt-{reviewer_id}",
        "reviewer_id": reviewer_id,
        "role": role,
        "context_id": context,
        "provider": "test-provider",
        "model": "test-model",
        "candidate_commit": candidate,
        "evidence_package_hash": evidence_hash,
        "execution_id": execution_id,
        "verification_method": "CI_AUTHENTICATED_EXTERNAL_EXECUTION",
        "verification_state": "VERIFIED",
        "issuer": "trusted-test-review-executor",
        "builder_controlled": False,
        "submitted_at": "2026-08-11T12:30:00Z",
    }


def _finalize(root: Path, candidate: str, program: dict, evidence_refs: list[dict]) -> None:
    final_program = copy.deepcopy(program)
    final_program["phases"][0]["status"] = "COMPLETE"
    final_program["phases"][0]["technical_verification"] = "PASS"
    final_program["phases"][0]["outcome_verification"] = "NOT_REQUIRED"
    final_program["current_phase"] = "P1"
    final_program["phases"][1]["status"] = "IN_PROGRESS"
    _write_json(root / closure.PROGRAM_RELATIVE, final_program)
    (root / "evaluation/remediation/autonomous-seo-expansion-ledger.md").write_text(
        "P0 closed\n", encoding="utf-8"
    )
    closure_payload = {
        "$schema": "../../schemas/autonomous-seo-phase-closure.schema.json",
        "schema_version": "1.2.0",
        "program_id": "autonomous-seo-expansion",
        "phase_id": "P0",
        "candidate_commit": candidate,
        "builder_context_id": "builder-0001",
        "apivr": {
            key: "PASS"
            for key in (
                "audit",
                "plan",
                "implement",
                "audit_implementation",
                "verify",
                "re_audit",
            )
        },
        "twenty_pass": {
            "passes_completed": 20,
            "improvements": [f"material improvement number {i:02d}" for i in range(20)],
        },
        "reviewer_verdict_files": [
            "evaluation/remediation/p0-scrummaster.json",
            "evaluation/remediation/p0-vp.json",
        ],
        "reviewer_provenance_files": [
            "evaluation/remediation/p0-scrummaster-provenance.json",
            "evaluation/remediation/p0-vp-provenance.json",
        ],
        "rollback": {"state": "PASS", "evidence_refs": [evidence_refs[0]]},
        "technical_verification": {"state": "PASS", "evidence_refs": [evidence_refs[1]]},
        "outcome_verification": {
            "state": "NOT_REQUIRED",
            "reason": "P0 is a governance-only phase",
            "evidence_refs": [],
        },
        "unexpected_change_scan": "PASS",
        "security_review": "PASS",
        "documentation_review": "PASS",
        "evidence_refs": evidence_refs,
        "evidence_package_hash": "pending",
        "closure_state": "APPROVED_GREAT",
    }
    closure_payload["evidence_package_hash"] = closure.canonical_hash(
        closure.closure_evidence_payload(closure_payload)
    )
    evidence_hash = closure_payload["evidence_package_hash"]
    reviewers = (
        (
            "senior-scrummaster-3",
            "SENIOR_SCRUMMASTER_3",
            "review-0001",
            "p0-scrummaster.json",
            "p0-scrummaster-provenance.json",
            "external-exec-0001",
        ),
        (
            "vp-engineering",
            "VP_ENGINEERING",
            "review-0002",
            "p0-vp.json",
            "p0-vp-provenance.json",
            "external-exec-0002",
        ),
    )
    for reviewer_id, role, context, verdict_name, provenance_name, execution_id in reviewers:
        _write_json(
            root / "evaluation/remediation" / verdict_name,
            _reviewer_verdict(reviewer_id, role, context, evidence_hash),
        )
        _write_json(
            root / "evaluation/remediation" / provenance_name,
            _reviewer_provenance(
                reviewer_id,
                role,
                context,
                candidate,
                evidence_hash,
                execution_id,
            ),
        )
    _write_json(
        root / "evaluation/remediation/autonomous-seo-expansion-p0-closure.json",
        closure_payload,
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "finalize p0")


def test_real_validator_accepts_complete_phase_closure(tmp_path: Path) -> None:
    root, candidate, program, policy, evidence_refs = _setup_candidate(tmp_path)
    _finalize(root, candidate, program, evidence_refs)
    final_program = closure.load_object(root / closure.PROGRAM_RELATIVE)
    schema = closure.load_object(root / "schemas/autonomous-seo-expansion-program.schema.json")
    assert validate_program(final_program, schema, root, policy) == []


def test_real_validator_rejects_post_review_future_phase_drift(tmp_path: Path) -> None:
    root, candidate, program, policy, evidence_refs = _setup_candidate(tmp_path)
    _finalize(root, candidate, program, evidence_refs)
    final_program = closure.load_object(root / closure.PROGRAM_RELATIVE)
    final_program["phases"][1]["objective"] = (
        "Unreviewed objective mutation after the candidate review."
    )
    _write_json(root / closure.PROGRAM_RELATIVE, final_program)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "spoof future phase")
    schema = closure.load_object(root / "schemas/autonomous-seo-expansion-program.schema.json")
    errors = validate_program(final_program, schema, root, policy)
    assert any(
        "immutable phase field changed" in error or "unreviewed phase changed" in error
        for error in errors
    )


def test_real_validator_rejects_evidence_content_spoof(tmp_path: Path) -> None:
    root, candidate, program, policy, evidence_refs = _setup_candidate(tmp_path)
    _finalize(root, candidate, program, evidence_refs)
    evidence = root / evidence_refs[0]["path"]
    evidence.write_text("tampered evidence\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "tamper evidence")
    final_program = closure.load_object(root / closure.PROGRAM_RELATIVE)
    schema = closure.load_object(root / "schemas/autonomous-seo-expansion-program.schema.json")
    errors = validate_program(final_program, schema, root, policy)
    assert any(
        "hash mismatch" in error
        or "post-review source drift" in error
        or "changed after candidate freeze" in error
        for error in errors
    )
