from __future__ import annotations

import json
from pathlib import Path

from runtime.autonomy import evaluate_action, load_policy

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "orchestration" / "autonomy-safety-policy.json"

EXPECTED_MODES = [
    "mode_0_audit_only",
    "mode_1_recommend_only",
    "mode_2_draft_changes",
    "mode_3_approval_gated_execution",
    "mode_4_limited_autopilot",
    "mode_5_full_autopilot_reserved",
]

EXPECTED_DANGEROUS_ACTIONS = {
    "sitewide_robots_change",
    "mass_noindex_change",
    "canonical_rule_change",
    "redirect_migration",
    "disavow_submission",
    "programmatic_page_creation",
    "regulated_or_legal_publication",
    "revenue_funnel_change",
    "outreach_send",
}


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_autonomy_policy_has_ordered_modes_and_public_default() -> None:
    payload = _policy()
    modes = payload["modes"]
    assert payload["public_repo_default"] == "mode_0_audit_only"
    assert [row["id"] for row in modes] == EXPECTED_MODES
    assert [row["level"] for row in modes] == list(range(6))
    assert modes[-1]["id"] == "mode_5_full_autopilot_reserved"
    assert "public repository default use" in modes[-1]["forbids"]


def test_dangerous_actions_require_approval_and_reviewers() -> None:
    payload = _policy()
    dangerous_ids = {row["id"] for row in payload["dangerous_actions"]}
    assert EXPECTED_DANGEROUS_ACTIONS <= dangerous_ids
    for row in payload["dangerous_actions"]:
        assert row["requires_approval"] is True
        assert row["minimum_mode"] == "mode_3_approval_gated_execution"
        assert row["patterns"]
        assert row["required_reviewers"]


def test_runtime_blocks_dangerous_actions_without_approval() -> None:
    policy = load_policy(POLICY)
    audit_decision = evaluate_action(
        "Apply a robots.txt change that blocks crawling for private URLs",
        mode="mode_0_audit_only",
        approved=False,
        policy=policy,
    )
    assert audit_decision.allowed is False
    assert audit_decision.approval_required is True
    assert audit_decision.matched_dangerous_action == "sitewide_robots_change"

    execution_decision = evaluate_action(
        "Apply a robots.txt change that blocks crawling for private URLs",
        mode="mode_3_approval_gated_execution",
        approved=False,
        policy=policy,
    )
    assert execution_decision.allowed is False
    assert execution_decision.reason == "explicit human approval is required"


def test_runtime_allows_approved_gated_dangerous_action() -> None:
    decision = evaluate_action(
        "Submit disavow links after manual review",
        mode="mode_3_approval_gated_execution",
        approved=True,
        policy=load_policy(POLICY),
    )
    assert decision.allowed is True
    assert decision.approval_required is True
    assert decision.matched_dangerous_action == "disavow_submission"


def test_standard_mutation_is_not_allowed_in_audit_mode() -> None:
    decision = evaluate_action(
        "Change the homepage title tag",
        mode="mode_0_audit_only",
        approved=False,
        policy=load_policy(POLICY),
    )
    assert decision.allowed is False
    assert decision.reason == "mutation-like action requires an execution mode"


def test_autonomy_docs_and_system_map_surface_policy() -> None:
    system_map = (ROOT / "SYSTEM_MAP.md").read_text(encoding="utf-8")
    system_spec = (ROOT / "SYSTEM_SPEC.md").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "AUTONOMY-SAFETY-MODEL.md").read_text(encoding="utf-8")

    assert "orchestration/autonomy-safety-policy.json" in system_map
    assert "runtime/autonomy.py" in system_map
    assert "docs/AUTONOMY-SAFETY-MODEL.md" in system_spec
    assert "Full Autopilot Reserved" in docs
    assert "sitewide `robots.txt` changes" in docs
