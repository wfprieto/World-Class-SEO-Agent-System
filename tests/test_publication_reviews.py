"""Decision tests use provider-shaped fixtures, never local role names as authority."""

from __future__ import annotations

import json

import pytest

from scripts import publication_policy as policy
from scripts.publication_provider import authenticate_decisions
from tests.test_publication_provider import (
    CANDIDATE,
    NOW,
    PREFIX,
    TREE,
    FixtureAPI,
    ci_responses,
    repository,
    subject,
)

EVIDENCE = "e" * 40
EVIDENCE_HASH = "f" * 64
SUBJECT_HASH = "a" * 64
ARCHIVE_HASH = "d" * 64
PR = 90


def composite() -> dict[str, object]:
    return {"schema_version": "1.0.0", "candidate_commit": CANDIDATE,
            "candidate_tree": TREE, "evidence_commit": EVIDENCE,
            "evidence_sha256": EVIDENCE_HASH, "subject_sha256": SUBJECT_HASH,
            "artifact_id": 88, "artifact_sha256": ARCHIVE_HASH,
            "ci_run_id": 44, "ci_attempt": 2, "prepare_run_id": 45, "prepare_attempt": 1}


def decisions_responses() -> dict[str, object]:
    responses = ci_responses()
    reviews = []
    for index, (_, (login, actor_id)) in enumerate(policy.REVIEW_ACTORS.items()):
        review_id = 701 + index
        body = {**composite(), "decision": "APPROVE_GREAT",
                "context_id": f"github:pull-request-review:{review_id}",
                "execution_id": f"github:pull-request-review:{review_id}",
                "objections": ["Artifact identity can diverge unless all approved digests are verified.",
                               "Evidence scope must remain distinct from historical fixture claims.",
                               "Owner permission cannot replace the independent producer origin proof."],
                "unresolved_findings": []}
        reviews.append({"id": review_id, "user": {"login": login, "id": actor_id, "type": "Bot"},
                        "commit_id": EVIDENCE, "state": "APPROVED", "body": json.dumps(body),
                        "submitted_at": "2026-10-31T02:40:00Z"})
    owner_body = json.dumps({**composite(), "decision": "AUTHORIZE_PUBLICATION"})
    responses.update({
        PREFIX + f"/pulls/{PR}": {"number": PR, "state": "open", "draft": False,
                                  "head": {"sha": EVIDENCE, "repo": repository()},
                                  "base": {"sha": CANDIDATE, "ref": "main", "repo": repository()}},
        PREFIX + f"/pulls/{PR}/reviews?per_page=100&page=1": reviews,
        PREFIX + "/issues/comments/901": {
            "id": 901, "node_id": "IC_verified_owner_fixture", "body": owner_body,
            "user": {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN, "type": "User"},
            "issue_url": f"https://api.github.com/repos/{policy.REPOSITORY}/issues/{PR}",
            "created_at": "2026-10-31T02:50:00Z", "updated_at": "2026-10-31T02:50:00Z"},
        "graphql": {"data": {"node": {
            "databaseId": 901, "body": owner_body, "createdAt": "2026-10-31T02:50:00Z",
            "updatedAt": "2026-10-31T02:50:00Z", "lastEditedAt": None,
            "author": {"login": policy.OWNER_LOGIN}}}},
    })
    return responses


def authorize(api: FixtureAPI) -> dict[str, object]:
    frozen = {**subject(), "prepared_at": "2026-10-31T02:30:00Z"}
    return authenticate_decisions(api, frozen, evidence_pr=PR, evidence_commit=EVIDENCE,
                                  evidence_sha256=EVIDENCE_HASH, artifact_id=88,
                                  archive_sha256=ARCHIVE_HASH, subject_sha256=SUBJECT_HASH,
                                  owner_comment_id=901, now=NOW)


def test_two_real_canonical_decisions_and_unedited_owner_bind_the_same_subject() -> None:
    result = authorize(FixtureAPI(decisions_responses()))
    assert result.get("owner_comment_id") == 901, "Actual owner decision was not authenticated"
    assert result.get("review_ids") == [701, 702]


@pytest.mark.parametrize("field,value", [
    ("state", "CHANGES_REQUESTED"), ("state", "DISMISSED"), ("state", "COMMENTED"),
    ("commit_id", "c" * 40), ("submitted_at", "2026-10-30T02:40:00Z"),
    ("submitted_at", "2026-11-01T02:40:00Z"),
])
def test_latest_role_decision_must_be_current_approved_exact_and_fresh(field, value) -> None:
    responses = decisions_responses()
    path = PREFIX + f"/pulls/{PR}/reviews?per_page=100&page=1"
    rows = responses[path]
    rows[0] = {**rows[0], field: value}
    with pytest.raises(ValueError):
        authorize(FixtureAPI(responses))


@pytest.mark.parametrize("field,value", [
    ("candidate_commit", "c" * 40), ("candidate_tree", "d" * 40),
    ("evidence_commit", "c" * 40), ("evidence_sha256", "c" * 64),
    ("subject_sha256", "c" * 64), ("artifact_id", 89),
    ("artifact_sha256", "c" * 64), ("ci_run_id", 999), ("ci_attempt", True),
    ("prepare_attempt", True), ("context_id", "self-asserted-context"),
    ("execution_id", "self-asserted-execution"),
    ("objections", ["three", "short", "words"]),
    ("unresolved_findings", [{"severity": "IMPORTANT", "finding": "Unresolved source mismatch"}]),
])
def test_role_json_cannot_substitute_local_subject_labels_or_ignore_objections(field, value) -> None:
    responses = decisions_responses()
    rows = responses[PREFIX + f"/pulls/{PR}/reviews?per_page=100&page=1"]
    body = json.loads(rows[0]["body"])
    body[field] = value
    rows[0]["body"] = json.dumps(body)
    with pytest.raises(ValueError):
        authorize(FixtureAPI(responses))


def test_later_revocation_cannot_fall_back_to_older_approval() -> None:
    responses = decisions_responses()
    rows = responses[PREFIX + f"/pulls/{PR}/reviews?per_page=100&page=1"]
    rows.append({**rows[0], "id": 703, "state": "DISMISSED", "submitted_at": "2026-10-31T02:45:00Z"})
    with pytest.raises(ValueError):
        authorize(FixtureAPI(responses))


def test_display_name_with_wrong_provider_numeric_id_is_not_independent_review() -> None:
    responses = decisions_responses()
    rows = responses[PREFIX + f"/pulls/{PR}/reviews?per_page=100&page=1"]
    rows[0]["user"]["id"] = 999
    with pytest.raises(ValueError, match="identity"):
        authorize(FixtureAPI(responses))


@pytest.mark.parametrize("mutation", ["edited", "same_second_edit", "wrong_pr", "wrong_owner", "before_reviews"])
def test_owner_authorization_requires_actual_unedited_later_exact_pr_comment(mutation) -> None:
    responses = decisions_responses()
    comment = responses[PREFIX + "/issues/comments/901"]
    if mutation == "edited":
        comment["updated_at"] = "2026-10-31T02:50:01Z"
    elif mutation == "same_second_edit":
        responses["graphql"]["data"]["node"]["lastEditedAt"] = "2026-10-31T02:50:00Z"
    elif mutation == "wrong_pr":
        comment["issue_url"] = comment["issue_url"] + "0"
    elif mutation == "wrong_owner":
        comment["user"]["id"] = 999
    else:
        comment["created_at"] = comment["updated_at"] = "2026-10-31T02:35:00Z"
    with pytest.raises(ValueError):
        authorize(FixtureAPI(responses))


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "nonfinite", "wrong_composite"])
def test_owner_json_body_must_be_exact_duplicate_free_and_finite(mutation) -> None:
    responses = decisions_responses()
    comment = responses[PREFIX + "/issues/comments/901"]
    body = json.loads(comment["body"])
    if mutation == "unknown":
        body["ignored_override"] = True
        raw = json.dumps(body)
    elif mutation == "duplicate":
        raw = comment["body"][:-1] + ', "decision":"AUTHORIZE_PUBLICATION"}'
    elif mutation == "nonfinite":
        body["prepare_attempt"] = float("nan")
        raw = json.dumps(body)
    else:
        body["evidence_sha256"] = "0" * 64
        raw = json.dumps(body)
    comment["body"] = responses["graphql"]["data"]["node"]["body"] = raw
    with pytest.raises(ValueError):
        authorize(FixtureAPI(responses))


def test_malformed_unresolved_severity_rejects_as_a_contract_error() -> None:
    responses = decisions_responses()
    rows = responses[PREFIX + f"/pulls/{PR}/reviews?per_page=100&page=1"]
    body = json.loads(rows[0]["body"])
    body["unresolved_findings"] = [{"severity": ["IMPORTANT"], "finding": "Malformed severity"}]
    rows[0]["body"] = json.dumps(body)
    with pytest.raises(ValueError):
        authorize(FixtureAPI(responses))


def test_owner_decision_must_be_strictly_after_both_review_timestamps() -> None:
    responses = decisions_responses()
    comment = responses[PREFIX + "/issues/comments/901"]
    comment["created_at"] = comment["updated_at"] = "2026-10-31T02:40:00Z"
    responses["graphql"]["data"]["node"].update(
        createdAt="2026-10-31T02:40:00Z", updatedAt="2026-10-31T02:40:00Z")
    with pytest.raises(ValueError, match="follow"):
        authorize(FixtureAPI(responses))
