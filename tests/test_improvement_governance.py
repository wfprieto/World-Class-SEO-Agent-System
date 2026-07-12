from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_improvement_evidence import validate_all

ROOT = Path(__file__).resolve().parents[1]


def test_improvement_governance_validator_passes():
    result = validate_all(ROOT)
    assert result == {
        "status": "PASS",
        "errors": [],
        "reviewers": 2,
        "direct_merge_permitted": False,
    }


def test_reviewer_registry_has_two_distinct_non_builder_non_merging_roles():
    registry = json.loads(
        (ROOT / "evaluation" / "reviewer-registry.json").read_text(encoding="utf-8")
    )
    reviewers = registry["reviewers"]
    assert {item["role"] for item in reviewers} == {
        "SENIOR_SCRUMMASTER_3",
        "VP_ENGINEERING",
    }
    assert len({item["reviewer_id"] for item in reviewers}) == 2
    for reviewer in reviewers:
        assert reviewer["can_modify_code"] is False
        assert reviewer["can_modify_scorecard"] is False
        assert reviewer["can_merge"] is False
        assert reviewer["requires_fresh_context"] is True
        assert reviewer["requires_three_objections"] is True


def test_reviewer_prompts_require_adversarial_objections_and_forbid_rubber_stamps():
    for name in ("senior-scrummaster-3.md", "vp-engineering.md"):
        text = (ROOT / "evaluation" / "reviewers" / name).read_text(encoding="utf-8")
        assert "at least three" in text.lower()
        assert "APPROVE_GREAT" in text
        assert "REWORK_GOOD" in text
        assert "REJECT_BAD" in text
        assert "merge" in text.lower()


def test_improvement_workflow_forbids_silent_main_writes_and_score_changes():
    text = (ROOT / "workflows" / "comparative-improvement-loop.md").read_text(
        encoding="utf-8"
    )
    assert "may not silently modify `main`" in text
    assert "never changes the scoring formula" in text
    assert "five iterations" in text
    assert "ARCHITECTURAL_REDESIGN" in text
