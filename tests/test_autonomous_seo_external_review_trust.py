from __future__ import annotations

from scripts import autonomous_seo_review_trust as trust
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


def test_issue_url_must_belong_to_declared_pr() -> None:
    repository = "wfprieto/World-Class-SEO-Agent-System"
    item = {"issue_url": f"https://api.github.com/repos/{repository}/issues/38"}
    assert external_review._issue_url_matches_pr(item, repository, 38)
    assert not external_review._issue_url_matches_pr(item, repository, 37)


def test_reviewer_receipts_must_share_one_dynamic_pr() -> None:
    receipts = [
        {
            "execution_id": "github:issue-comment:101",
            "trigger_comment_id": 201,
            "result_kind": "ISSUE_COMMENT",
            "result_id": 101,
            "pull_request_number": 38,
        },
        {
            "execution_id": "github:issue-comment:102",
            "trigger_comment_id": 202,
            "result_kind": "ISSUE_COMMENT",
            "result_id": 102,
            "pull_request_number": 38,
        },
    ]
    assert trust._execution_identity_errors(receipts) == []


def test_reviewer_receipts_reject_cross_pr_evidence() -> None:
    receipts = [
        {
            "execution_id": "github:issue-comment:101",
            "trigger_comment_id": 201,
            "result_kind": "ISSUE_COMMENT",
            "result_id": 101,
            "pull_request_number": 37,
        },
        {
            "execution_id": "github:issue-comment:102",
            "trigger_comment_id": 202,
            "result_kind": "ISSUE_COMMENT",
            "result_id": 102,
            "pull_request_number": 38,
        },
    ]
    errors = trust._execution_identity_errors(receipts)
    assert any("one positive pull request" in error for error in errors)
