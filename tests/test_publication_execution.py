"""Registered-origin tests are synthetic offline provider fixtures, not evidence."""

from __future__ import annotations

import pytest

from scripts import publication_policy as policy
from scripts.publication_provider import authenticate_execution
from tests.test_publication_provider import CANDIDATE, NOW, FixtureAPI, subject

REPRO_REPO = "independent-lab/seo-reproducer"
REPRO_PREFIX = f"/repos/{REPRO_REPO}"
PRODUCER_COMMIT = "c" * 40


def authority() -> dict[str, object]:
    return {"repository": REPRO_REPO, "repository_id": 555, "owner_id": 777,
            "actor_id": 888, "workflow": ".github/workflows/reproduce.yml",
            "source_commit": PRODUCER_COMMIT, "source_ref": "refs/heads/main",
            "independent": True}


def pointer() -> dict[str, object]:
    return {"authority_index": 0, "run_id": 66, "run_attempt": 2,
            "artifact_id": 99, "artifact_sha256": "f" * 64,
            "member_name": "execution.json", "member_sha256": "e" * 64}


def execution_responses() -> dict[str, object]:
    repo = {"id": 555, "full_name": REPRO_REPO,
            "owner": {"id": 777, "login": "independent-lab"}}
    actor = {"id": 888, "login": "lab-operator", "type": "User"}
    run = {"id": 66, "repository": repo, "head_repository": repo, "workflow_id": 999,
           "path": ".github/workflows/reproduce.yml", "event": "workflow_dispatch",
           "head_branch": "main", "head_sha": PRODUCER_COMMIT, "status": "completed",
           "conclusion": "success", "run_attempt": 2, "actor": actor, "triggering_actor": actor,
           "created_at": "2026-10-30T02:00:00Z", "run_started_at": "2026-10-30T02:00:00Z",
           "updated_at": "2026-10-30T02:30:00Z"}
    return {REPRO_PREFIX: repo,
            REPRO_PREFIX + "/actions/workflows/reproduce.yml":
                {"id": 999, "path": ".github/workflows/reproduce.yml", "state": "active"},
            REPRO_PREFIX + "/actions/runs/66": run,
            REPRO_PREFIX + "/actions/runs/66/attempts/2": run,
            REPRO_PREFIX + "/actions/artifacts/99": {
                "id": 99, "name": "independent-execution", "size_in_bytes": 500,
                "digest": "sha256:" + "f" * 64, "expired": False,
                "created_at": "2026-10-30T02:20:00Z", "updated_at": "2026-10-30T02:20:00Z",
                "expires_at": "2026-11-07T02:20:00Z", "workflow_run": {
                    "id": 66, "repository_id": 555, "head_repository_id": 555,
                    "head_sha": PRODUCER_COMMIT}},
            }


def test_registered_external_origin_derives_independence_from_real_provider_ids() -> None:
    result = authenticate_execution(FixtureAPI(execution_responses()), pointer=pointer(),
                                    authority=authority(), subject=subject(), now=NOW)
    assert result.get("execution_context") == "github:555:run:66:attempt:2"
    assert result.get("candidate_commit") == CANDIDATE
    assert result.get("independent") is True


@pytest.mark.parametrize("field,value", [
    ("repository", "../outside"), ("repository_id", True), ("owner_id", policy.OWNER_ID),
    ("actor_id", policy.OWNER_ID), ("workflow", "../execute.py"),
    ("source_commit", "branch-not-pin"), ("source_ref", "refs/heads/../main"),
    ("independent", "yes"),
])
def test_registry_identity_and_independence_cannot_be_supplied_as_local_labels(field, value) -> None:
    entry = {**authority(), field: value}
    with pytest.raises(ValueError):
        authenticate_execution(FixtureAPI(execution_responses()), pointer=pointer(),
                               authority=entry, subject=subject(), now=NOW)


@pytest.mark.parametrize("field,value", [
    ("authority_index", True), ("authority_index", -1), ("run_attempt", True),
    ("member_name", "../result.json"), ("member_sha256", "fuzzy"),
    ("artifact_sha256", "not-a-digest"),
])
def test_execution_pointer_is_typed_bounded_and_not_an_arbitrary_download_path(field, value) -> None:
    with pytest.raises(ValueError):
        authenticate_execution(FixtureAPI(execution_responses()), pointer={**pointer(), field: value},
                               authority=authority(), subject=subject(), now=NOW)


@pytest.mark.parametrize("field,value", [
    ("head_sha", "d" * 40), ("run_attempt", 3), ("conclusion", "failure"),
    ("run_started_at", "2026-10-01T00:00:00Z"),
    ("triggering_actor", {"id": 666, "login": "unregistered", "type": "User"}),
])
def test_origin_requires_exact_registered_executable_and_latest_successful_attempt(field, value) -> None:
    responses = execution_responses()
    path = REPRO_PREFIX + "/actions/runs/66"
    responses[path] = {**responses[path], field: value}
    with pytest.raises(ValueError):
        authenticate_execution(FixtureAPI(responses), pointer=pointer(), authority=authority(),
                               subject=subject(), now=NOW)


def test_malformed_execution_actor_type_is_a_contract_error() -> None:
    responses = execution_responses()
    path = REPRO_PREFIX + "/actions/runs/66"
    responses[path]["triggering_actor"]["type"] = ["User"]
    with pytest.raises(ValueError):
        authenticate_execution(FixtureAPI(responses), pointer=pointer(), authority=authority(),
                               subject=subject(), now=NOW)
