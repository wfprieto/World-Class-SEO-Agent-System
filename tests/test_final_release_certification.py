from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CERTIFICATION = ROOT / "evaluation" / "final-release-certification.json"


def _certification() -> dict:
    return json.loads(CERTIFICATION.read_text(encoding="utf-8"))


def test_final_certification_references_all_completed_phase_closeouts() -> None:
    certification = _certification()
    phases = certification["verified_phase_closeouts"]
    assert len(phases) == 8
    for index in range(1, 9):
        assert any(f"PHASE-{index}-" in phase for phase in phases), index
    for relative in phases:
        assert (ROOT / relative).is_file(), relative


def test_final_certification_required_artifacts_exist() -> None:
    certification = _certification()
    for relative in certification["required_public_artifacts"]:
        assert (ROOT / relative).exists(), relative


def test_final_certification_is_honest_about_merge_blockers() -> None:
    certification = _certification()
    assert certification["release_decision"] == "BLOCKED"
    blocker_ids = {blocker["id"] for blocker in certification["blockers"]}
    assert "working-tree-reconciliation" in blocker_ids
    assert "external-live-proof" in blocker_ids
    assert certification["vp_engineering_decision"] == "BLOCKED_FOR_MERGE_UNTIL_PUSHED_AND_PR_GATED"


def test_final_certification_records_release_branch_reconciliation() -> None:
    certification = _certification()
    artifacts = set(certification["required_public_artifacts"])
    assert "docs/RELEASE-BRANCH-RECONCILIATION.md" in artifacts
    blocker_text = json.dumps(certification["blockers"])
    assert "release/v1.7.0-final-certification" in blocker_text
    assert "26d3bc9" in blocker_text


def test_final_certification_contains_current_verification_battery() -> None:
    commands = "\n".join(_certification()["verification_commands"])
    assert "python -m pytest -q --basetemp .pytest_tmp" in commands
    assert "python -m ruff check . --select E9,F63,F7,F82 --no-cache" in commands
    assert "python scripts/scan_secrets.py" in commands
    assert "python scripts/validate_reference_freshness.py" in commands
