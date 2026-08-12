from __future__ import annotations

from scripts import validate_autonomous_seo_external_reviews as external_review


def _receipt(reviewer_id: str, actor: str) -> dict:
    return {
        "reviewer_id": reviewer_id,
        "result_actor_login": actor,
    }


def test_provider_actor_rejects_builder_identity() -> None:
    receipt = _receipt("senior-scrummaster-3", "wfprieto")
    result = {"user": {"login": "wfprieto"}}
    errors = external_review._provider_actor_errors(receipt, result)
    assert any("approved reviewer actor" in error for error in errors)


def test_provider_actor_accepts_expected_claude_identity() -> None:
    receipt = _receipt("senior-scrummaster-3", "claude[bot]")
    result = {"user": {"login": "claude[bot]"}}
    assert external_review._provider_actor_errors(receipt, result) == []


def test_provider_actor_rejects_cross_role_bot_identity() -> None:
    receipt = _receipt("senior-scrummaster-3", "chatgpt-codex-connector[bot]")
    result = {"user": {"login": "chatgpt-codex-connector[bot]"}}
    errors = external_review._provider_actor_errors(receipt, result)
    assert any("approved reviewer actor" in error for error in errors)
