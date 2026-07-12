from __future__ import annotations

from scripts.run_improvement_cycle import canonical_hash, evaluate_cycle

BUILDER_CONTEXT = "builder-context-0001"


def _cycle() -> dict:
    cycle = {
        "cycle_id": "cycle-0001",
        "gap_id": "tooling-gsc-query",
        "iteration": 1,
        "state": "UNDER_REVIEW",
        "baseline": {
            "target_commit": "8e6f666506ff723eb6f8f354e4150b30073fb67f",
            "claude_commit": "6cf1ea9fe4c2088b2ad3089797f846850fd66164",
            "target_metrics": {"functional": 4},
            "claude_metrics": {"functional": 9},
        },
        "hypothesis": "A production GSC connector with truthful aggregate totals will reach parity without weakening runtime governance.",
        "files_changed": ["integrations/google/gsc.py"],
        "tests_added": ["tests/test_google_gsc.py"],
        "verification": {
            "tests_passed": True,
            "regressions": [],
            "evidence_refs": ["ci-run-1", "sandbox-smoke-1"],
            "live_state": "VERIFIED",
            "security_passed": True,
            "documentation_executed": True,
        },
        "claude_comparison": {
            "functional": 9,
            "accuracy": 10,
            "security": 10,
            "cost_control": 10,
            "documentation": 9,
            "verdict": "PARITY",
        },
        "builder_rating": "GREAT",
        "reviewer_verdicts": [],
        "lessons": ["Aggregate totals must not be inferred from anonymized query rows."],
        "next_action": "Independent review",
        "direct_merge_permitted": False,
        "created_at": "2026-07-11T00:00:00Z",
        "updated_at": "2026-07-11T00:00:00Z",
    }
    evidence = {
        "cycle_id": cycle["cycle_id"],
        "gap_id": cycle["gap_id"],
        "baseline": cycle["baseline"],
        "files_changed": cycle["files_changed"],
        "tests_added": cycle["tests_added"],
        "verification": cycle["verification"],
        "claude_comparison": cycle["claude_comparison"],
    }
    package_hash = canonical_hash(evidence)
    cycle["reviewer_verdicts"] = [
        {
            "review_id": "review-ssm3-1",
            "reviewer_id": "senior-scrummaster-3",
            "role": "SENIOR_SCRUMMASTER_3",
            "context_id": "review-context-scrum-0001",
            "provider": "provider-a",
            "model": "review-model-a",
            "evidence_package_hash": package_hash,
            "verdict": "APPROVE_GREAT",
            "strongest_objections": [
                "Live quota exhaustion remains an operational risk.",
                "Search Console data can lag and must retain source dates.",
                "Property permissions can make apparently valid requests incomplete.",
            ],
            "evidence_refs": ["ci-run-1", "sandbox-smoke-1"],
            "residual_risks": ["API quota and source latency"],
            "required_changes": [],
            "submitted_at": "2026-07-11T01:00:00Z",
            "saw_other_reviewer_verdict": False,
            "is_builder": False,
        },
        {
            "review_id": "review-vpe-1",
            "reviewer_id": "vp-engineering",
            "role": "VP_ENGINEERING",
            "context_id": "review-context-vpe-0001",
            "provider": "provider-b",
            "model": "review-model-b",
            "evidence_package_hash": package_hash,
            "verdict": "APPROVE_GREAT",
            "strongest_objections": [
                "OAuth refresh behavior requires continued monitoring.",
                "The optional dependency must remain removable.",
                "User-facing quota errors must stay sanitized and actionable.",
            ],
            "evidence_refs": ["ci-run-1", "sandbox-smoke-1"],
            "residual_risks": ["OAuth provider behavior"],
            "required_changes": [],
            "submitted_at": "2026-07-11T01:01:00Z",
            "saw_other_reviewer_verdict": False,
            "is_builder": False,
        },
    ]
    return cycle


def test_great_requires_two_independent_approvals_and_full_evidence():
    result = evaluate_cycle(_cycle(), builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "APPROVE_GREAT"
    assert result["persist_lessons"] is True
    assert result["direct_merge_permitted"] is False


def test_one_rework_verdict_blocks_approval():
    cycle = _cycle()
    cycle["reviewer_verdicts"][0]["verdict"] = "REWORK_GOOD"
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "REWORK_GOOD"
    assert result["persist_lessons"] is False


def test_one_rejection_rejects_the_cycle_without_averaging():
    cycle = _cycle()
    cycle["reviewer_verdicts"][1]["verdict"] = "REJECT_BAD"
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "REJECT_BAD"
    assert result["state"] == "REJECTED_BAD"


def test_reviewer_contexts_must_be_independent_from_each_other_and_builder():
    cycle = _cycle()
    cycle["reviewer_verdicts"][0]["context_id"] = BUILDER_CONTEXT
    cycle["reviewer_verdicts"][1]["context_id"] = BUILDER_CONTEXT
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "REWORK_GOOD"
    assert any("reviewer context" in error for error in result["errors"])


def test_reviewers_must_review_the_exact_same_evidence_package():
    cycle = _cycle()
    cycle["reviewer_verdicts"][1]["evidence_package_hash"] = "0" * 64
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "REWORK_GOOD"
    assert any("different evidence package" in error for error in result["errors"])


def test_tests_regressions_security_and_documentation_are_hard_gates():
    cycle = _cycle()
    cycle["verification"]["tests_passed"] = False
    cycle["verification"]["regressions"] = ["existing route changed"]
    cycle["verification"]["security_passed"] = False
    cycle["verification"]["documentation_executed"] = False
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "REWORK_GOOD"
    assert "tests are not passing" in result["errors"]
    assert "regressions remain unresolved" in result["errors"]
    assert "security verification is not passing" in result["errors"]


def test_inferior_to_comparator_cannot_be_rated_great():
    cycle = _cycle()
    cycle["claude_comparison"]["verdict"] = "INFERIOR"
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "REWORK_GOOD"
    assert any("remains inferior" in error for error in result["errors"])


def test_fifth_failed_iteration_triggers_architectural_redesign():
    cycle = _cycle()
    cycle["iteration"] = 5
    cycle["reviewer_verdicts"][0]["verdict"] = "REWORK_GOOD"
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "ARCHITECTURAL_REDESIGN"
    assert result["state"] == "ARCHITECTURAL_REDESIGN"


def test_cycle_can_never_authorize_direct_merge():
    cycle = _cycle()
    cycle["direct_merge_permitted"] = True
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "INVALID"
    assert result["direct_merge_permitted"] is False


def test_builder_rating_good_cannot_close_gap_even_with_reviewer_approval():
    cycle = _cycle()
    cycle["builder_rating"] = "GOOD"
    result = evaluate_cycle(cycle, builder_context_id=BUILDER_CONTEXT)
    assert result["decision"] == "REWORK_GOOD"
    assert result["persist_lessons"] is False
