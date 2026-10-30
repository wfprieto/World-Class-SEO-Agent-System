from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.validate_phase6_readiness import REQUIRED, validate

ROOT = Path(__file__).resolve().parents[1]


def test_phase6_artifacts_are_consistent():
    assert validate() == []


def test_release_is_truthfully_blocked_until_external_gates_pass():
    data = json.loads((ROOT / "evaluation/comparative/final-release-readiness.json").read_text(encoding="utf-8"))
    assert data["release_decision"] == "BLOCKED"
    assert data["gates"]["final_push_ci"] == "NOT_RUN"
    assert data["gates"]["dependency_audit"] == "PASS"
    assert data["gates"]["seven_archetype_benchmark"] == "NOT_RUN"
    assert data["gates"]["external_reproduction"] == "NOT_RUN"
    assert data["gates"]["version_tag"] == "NOT_RUN"
    assert data["gates"]["public_release_artifacts"] == "NOT_RUN"
    assert data["verification_state"] == {
        "code_verified": "PASS",
        "live_verified": "INCOMPLETE",
        "externally_reproduced": "NOT_RUN",
    }


def test_publication_mode_rejects_the_current_blocked_decision():
    assert "release publication requires release_decision APPROVED" in validate(
        require_approved=True
    )
    result = subprocess.run(
        [sys.executable, "scripts/validate_phase6_readiness.py", "--require-approved"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "release publication requires release_decision APPROVED" in result.stdout


def test_benchmark_framework_covers_required_scope():
    data = json.loads((ROOT / "evaluation/comparative/benchmark-cases.json").read_text(encoding="utf-8"))
    assert len(data["archetypes"]) == 7
    assert len(data["tasks"]) == 15
    assert data["gates"]["unsupported_claims_max"] == 0


def test_approved_release_requires_complete_gates_and_actual_evidence(tmp_path: Path) -> None:
    for relative in REQUIRED:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    readiness_path = tmp_path / "evaluation/comparative/final-release-readiness.json"
    readiness = json.loads(readiness_path.read_text())
    readiness["release_decision"] = "APPROVED"
    readiness["gates"] = {}
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    errors = validate(require_approved=True, root=tmp_path)
    assert any("missing" in error and "gate" in error for error in errors), (
        "an empty gate mapping must not authorize publication"
    )
    readiness["gates"] = {key: "PASS" for key in json.loads((ROOT / "evaluation/comparative/final-release-readiness.json").read_text())["gates"]}
    readiness["gates"].update(scrummaster3_verdict="APPROVE_GREAT", vp_engineering_verdict="APPROVE_GREAT")
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    errors = validate(require_approved=True, root=tmp_path)
    assert any("reviewer" in error for error in errors), "declared gates cannot override actual REWORK verdicts"
    assert any("verification" in error for error in errors), "incomplete live/external verification cannot be approved"


def test_approved_release_requires_candidate_bound_external_evidence(tmp_path: Path) -> None:
    from scripts import autonomous_seo_review_trust as trust
    from tests.test_source_integrity import _git

    for relative in REQUIRED:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    for name in ("live-smoke.txt", "external-reproduction.txt"):
        (tmp_path / name).write_text(f"synthetic controlled evidence: {name}\n", encoding="utf-8")
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.name", "Release fixture")
    _git(tmp_path, "config", "user.email", "release@example.invalid")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "controlled candidate evidence")
    candidate = _git(tmp_path, "rev-parse", "HEAD")
    readiness_path = tmp_path / "evaluation/comparative/final-release-readiness.json"
    readiness = json.loads(readiness_path.read_text())
    readiness.update(release_decision="APPROVED", evaluated_target_commit=candidate)
    readiness["gates"] = {key: "PASS" for key in readiness["gates"]}
    readiness["gates"].update(scrummaster3_verdict="APPROVE_GREAT", vp_engineering_verdict="APPROVE_GREAT")
    readiness["verification_state"] = dict.fromkeys(readiness["verification_state"], "PASS")
    readiness["verified_ci"]["commit"] = candidate
    for name in ("final-scrummaster-3-verdict.json", "final-vp-engineering-verdict.json"):
        path = tmp_path / "evaluation/reviewers" / name
        verdict = json.loads(path.read_text())
        verdict.update(verdict="APPROVE_GREAT", candidate_commit=candidate)
        path.write_text(json.dumps(verdict), encoding="utf-8")
    benchmark_path = tmp_path / "evaluation/comparative/benchmark-cases.json"
    benchmark = json.loads(benchmark_path.read_text())
    benchmark["execution_state"] = "PASS"
    benchmark_path.write_text(json.dumps(benchmark), encoding="utf-8")
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    assert any("verification_evidence" in error for error in validate(require_approved=True, root=tmp_path)), (
        "PASS labels without actual source-bound live/external evidence must not authorize release"
    )
    readiness["verification_evidence"] = {}
    for gate, name in (("live_authorized_smokes", "live-smoke.txt"),
                       ("external_reproduction", "external-reproduction.txt")):
        readiness["verification_evidence"][gate] = {
            "state": "PASS", "candidate_commit": candidate,
            "evidence_refs": [{"kind": "repository_file", "path": name, "bound_commit": candidate,
                               "sha256": trust.candidate_blob_sha256(tmp_path, candidate, name)}],
        }
    readiness_path.write_text(json.dumps(readiness), encoding="utf-8")
    assert validate(require_approved=True, root=tmp_path) == []
    (tmp_path / "external-reproduction.txt").write_text("tampered after review\n", encoding="utf-8")
    assert any("changed after candidate freeze" in error for error in validate(require_approved=True, root=tmp_path))
