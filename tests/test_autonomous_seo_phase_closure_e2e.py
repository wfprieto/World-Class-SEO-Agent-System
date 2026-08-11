from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path

from scripts import autonomous_seo_expansion_closure as closure
from scripts import autonomous_seo_program_closure as program_closure
from scripts import autonomous_seo_review_trust as trust
from scripts.validate_autonomous_seo_expansion_program import validate_program

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _copy_contracts(root: Path) -> None:
    for relative in (
        "schemas/autonomous-seo-expansion-program.schema.json",
        "schemas/autonomous-seo-expansion-policy.schema.json",
        "schemas/autonomous-seo-phase-closure.schema.json",
        "schemas/autonomous-seo-program-closure.schema.json",
        "schemas/autonomous-seo-reviewer-provenance.schema.json",
        "schemas/reviewer-verdict.schema.json",
        "evaluation/remediation/autonomous-seo-expansion-policy.json",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def _reviewer(reviewer_id: str, role: str, context: str, evidence_hash: str) -> dict:
    return {
        "review_id": f"review-{reviewer_id}",
        "reviewer_id": reviewer_id,
        "role": role,
        "context_id": context,
        "provider": "external-provider",
        "model": "independent-model",
        "evidence_package_hash": evidence_hash,
        "verdict": "APPROVE_GREAT",
        "strongest_objections": [
            "Candidate trust chain was challenged independently.",
            "Post-review source drift was explicitly inspected.",
            "Rollback and evidence binding were independently checked.",
        ],
        "evidence_refs": ["fixture-evidence"],
        "residual_risks": [],
        "required_changes": [],
        "submitted_at": "2026-08-11T17:00:00Z",
        "saw_other_reviewer_verdict": False,
        "is_builder": False,
    }


def _provenance(
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
        "provider": "external-provider",
        "model": "independent-model",
        "candidate_commit": candidate,
        "evidence_package_hash": evidence_hash,
        "execution_id": execution_id,
        "verification_method": "CI_AUTHENTICATED_EXTERNAL_EXECUTION",
        "verification_state": "VERIFIED",
        "issuer": "trusted-review-executor",
        "builder_controlled": False,
        "submitted_at": "2026-08-11T17:00:00Z",
    }


def _prepare_candidate(root: Path) -> tuple[dict, str, list[dict]]:
    _git(root, "init")
    _git(root, "config", "user.email", "fixture@example.com")
    _git(root, "config", "user.name", "fixture")
    (root / "seed.txt").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    baseline = _git(root, "rev-parse", "HEAD")
    _copy_contracts(root)
    program = json.loads(
        (ROOT / "evaluation/remediation/autonomous-seo-expansion-program.json").read_text(
            encoding="utf-8"
        )
    )
    program["baseline"]["commit"] = baseline
    program_path = root / "evaluation/remediation/autonomous-seo-expansion-program.json"
    _write(program_path, program)
    evidence_paths = []
    for index in range(3):
        path = root / f"evaluation/remediation/p0-evidence-{index}.txt"
        path.write_text(f"candidate evidence {index}\n", encoding="utf-8")
        evidence_paths.append(path)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "candidate")
    candidate = _git(root, "rev-parse", "HEAD")
    refs = []
    for path in evidence_paths:
        relative = str(path.relative_to(root)).replace("\\", "/")
        candidate_hash = trust.candidate_blob_sha256(root, candidate, relative)
        assert candidate_hash is not None
        refs.append(
            {
                "kind": "repository_file",
                "path": relative,
                "sha256": candidate_hash,
                "bound_commit": candidate,
            }
        )
    return program, candidate, refs


def test_full_phase_closure_advances_program_end_to_end(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    program, candidate, refs = _prepare_candidate(root)
    final_program = copy.deepcopy(program)
    final_program["phases"][0]["status"] = "COMPLETE"
    final_program["phases"][0]["technical_verification"] = "PASS"
    final_program["phases"][0]["outcome_verification"] = "NOT_REQUIRED"
    final_program["current_phase"] = "P1"
    final_program["phases"][1]["status"] = "IN_PROGRESS"
    closure_payload = {
        "$schema": "../../schemas/autonomous-seo-phase-closure.schema.json",
        "schema_version": "1.2.0",
        "program_id": "autonomous-seo-expansion",
        "phase_id": "P0",
        "candidate_commit": candidate,
        "builder_context_id": "builder-fixture-01",
        "apivr": {
            "audit": "PASS",
            "plan": "PASS",
            "implement": "PASS",
            "audit_implementation": "PASS",
            "verify": "PASS",
            "re_audit": "PASS",
        },
        "twenty_pass": {
            "passes_completed": 20,
            "improvements": [f"material fixture improvement {index:02d}" for index in range(20)],
        },
        "reviewer_verdict_files": [
            "evaluation/remediation/p0-scrummaster-verdict.json",
            "evaluation/remediation/p0-vp-verdict.json",
        ],
        "reviewer_provenance_files": [
            "evaluation/remediation/p0-scrummaster-provenance.json",
            "evaluation/remediation/p0-vp-provenance.json",
        ],
        "rollback": {"state": "PASS", "evidence_refs": [refs[0]]},
        "technical_verification": {"state": "PASS", "evidence_refs": [refs[1]]},
        "outcome_verification": {
            "state": "NOT_REQUIRED",
            "reason": "P0 establishes governance contracts only.",
            "evidence_refs": [],
        },
        "unexpected_change_scan": "PASS",
        "security_review": "PASS",
        "documentation_review": "PASS",
        "evidence_refs": refs,
        "evidence_package_hash": "0" * 64,
        "closure_state": "APPROVED_GREAT",
    }
    closure_payload["evidence_package_hash"] = closure.canonical_hash(
        closure.closure_evidence_payload(closure_payload)
    )
    evidence_hash = closure_payload["evidence_package_hash"]
    reviewers = [
        (
            "senior-scrummaster-3",
            "SENIOR_SCRUMMASTER_3",
            "review-context-01",
            "external-execution-01",
            "p0-scrummaster",
        ),
        (
            "vp-engineering",
            "VP_ENGINEERING",
            "review-context-02",
            "external-execution-02",
            "p0-vp",
        ),
    ]
    for reviewer_id, role, context, execution_id, prefix in reviewers:
        _write(
            root / f"evaluation/remediation/{prefix}-verdict.json",
            _reviewer(reviewer_id, role, context, evidence_hash),
        )
        _write(
            root / f"evaluation/remediation/{prefix}-provenance.json",
            _provenance(reviewer_id, role, context, candidate, evidence_hash, execution_id),
        )
    _write(root / "evaluation/remediation/autonomous-seo-expansion-p0-closure.json", closure_payload)
    _write(root / "evaluation/remediation/autonomous-seo-expansion-program.json", final_program)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "phase closure finalization")
    schema = json.loads(
        (root / "schemas/autonomous-seo-expansion-program.schema.json").read_text(encoding="utf-8")
    )
    policy = json.loads(
        (root / "evaluation/remediation/autonomous-seo-expansion-policy.json").read_text(encoding="utf-8")
    )
    assert validate_program(final_program, schema, root, policy) == []


def test_candidate_evidence_detects_post_freeze_mutation(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _, candidate, refs = _prepare_candidate(root)
    evidence = root / refs[0]["path"]
    evidence.write_text("tampered after candidate\n", encoding="utf-8")
    errors = closure.evidence_ref_errors([refs[0]], root, candidate)
    assert any("changed after candidate freeze" in error for error in errors)


def test_reviewer_provenance_is_mandatory(tmp_path: Path) -> None:
    closure_payload = {
        "reviewer_provenance_files": [],
        "candidate_commit": "a" * 40,
        "builder_context_id": "builder-context",
        "evidence_package_hash": "b" * 64,
    }
    verdicts = [
        {"reviewer_id": "senior-scrummaster-3"},
        {"reviewer_id": "vp-engineering"},
    ]
    errors = trust.reviewer_provenance_errors(closure_payload, verdicts, tmp_path)
    assert any("authenticated reviewer provenance" in error for error in errors)


def test_program_closure_rejects_nonexistent_candidate(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "fixture@example.com")
    _git(root, "config", "user.name", "fixture")
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "seed")
    program = {"program_evidence_state": "VERIFIED"}
    closure_payload = {"candidate_commit": "a" * 40}
    errors = program_closure._candidate_freeze_errors(program, closure_payload, root)
    assert any("existing commit" in error for error in errors)


def test_program_closure_rejects_post_review_source_drift(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "fixture@example.com")
    _git(root, "config", "user.name", "fixture")
    program_path = root / closure.PROGRAM_RELATIVE
    _write(program_path, {"program_evidence_state": "PARTIAL", "stable": True})
    _git(root, "add", ".")
    _git(root, "commit", "-m", "review freeze")
    candidate = _git(root, "rev-parse", "HEAD")
    (root / "source.py").write_text("material source drift\n", encoding="utf-8")
    final_program = {"program_evidence_state": "VERIFIED", "stable": True}
    _write(program_path, final_program)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "illegal finalization")
    closure_payload = {
        "candidate_commit": candidate,
        "reviewer_verdict_files": [],
        "reviewer_provenance_files": [],
    }
    errors = program_closure._candidate_freeze_errors(final_program, closure_payload, root)
    assert any("post-review source drift" in error for error in errors)
