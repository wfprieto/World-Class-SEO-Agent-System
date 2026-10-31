"""Public provider boundary tests; all responses are controlled offline fixtures."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from scripts import publication_policy as policy
from scripts.publication_provider import authenticate_ci, authenticate_preparation

NOW = datetime(2026, 10, 31, 3, tzinfo=UTC)
CANDIDATE = "a" * 40
TREE = "b" * 40
CI_ID = 44
PREFIX = f"/repos/{policy.REPOSITORY}"


class FixtureAPI:
    def __init__(self, responses: dict[str, object]):
        self.responses = responses
        self.calls: list[str] = []

    def json(self, path: str) -> object:
        self.calls.append(path)
        return deepcopy(self.responses[path])

    def binary(self, path: str, limit: int) -> bytes:
        raise AssertionError("Provider authentication must not fetch artifact bytes")

    def graphql(self, query: str, variables: dict[str, object]) -> object:
        self.calls.append("graphql")
        assert "mutation" not in query
        return deepcopy(self.responses["graphql"])


def repository() -> dict[str, object]:
    return {"id": policy.REPOSITORY_ID, "full_name": policy.REPOSITORY,
            "owner": {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN}}


def subject() -> dict[str, object]:
    return {"repository": policy.REPOSITORY, "repository_id": policy.REPOSITORY_ID,
            "owner_id": policy.OWNER_ID, "candidate_commit": CANDIDATE, "candidate_tree": TREE,
            "ci_run_id": CI_ID, "ci_attempt": 2, "prepare_run_id": 45,
            "prepare_attempt": 1}


def ci_responses() -> dict[str, object]:
    repo = repository()
    run = {"id": CI_ID, "repository": repo, "head_repository": repo,
           "workflow_id": policy.VALIDATION_WORKFLOW_ID,
           "path": policy.VALIDATION_WORKFLOW, "event": "push", "head_branch": "main",
           "head_sha": CANDIDATE, "status": "completed", "conclusion": "success",
           "run_attempt": 2, "created_at": "2026-10-31T02:00:00Z",
           "run_started_at": "2026-10-31T02:00:00Z", "updated_at": "2026-10-31T02:30:00Z"}
    jobs = [{"id": index + 1, "name": name, "status": "completed", "conclusion": "success"}
            for index, name in enumerate(sorted(policy.EXPECTED_CI_JOBS))]
    return {PREFIX: repo, PREFIX + "/branches/main": {"protected": True, "commit": {"sha": CANDIDATE}},
            PREFIX + "/git/commits/" + CANDIDATE: {"sha": CANDIDATE, "tree": {"sha": TREE}},
            PREFIX + f"/actions/workflows/{policy.VALIDATION_WORKFLOW_ID}":
                {"id": policy.VALIDATION_WORKFLOW_ID, "path": policy.VALIDATION_WORKFLOW,
                 "state": "active"},
            PREFIX + f"/actions/runs/{CI_ID}": run,
            PREFIX + f"/actions/runs/{CI_ID}/attempts/2": run,
            PREFIX + f"/actions/runs/{CI_ID}/attempts/2/jobs?per_page=100&page=1":
                {"total_count": len(jobs), "jobs": jobs}}


def test_authenticates_real_exact_ci_metadata_not_local_cell_labels() -> None:
    api = FixtureAPI(ci_responses())
    receipt = authenticate_ci(api, subject(), now=NOW)
    assert receipt.get("run_id") == CI_ID, "Exact provider CI run was not authenticated"
    assert receipt.get("run_attempt") == 2
    assert receipt.get("candidate_commit") == CANDIDATE


@pytest.mark.parametrize("field,value", [
    ("head_sha", "c" * 40), ("head_branch", "other"), ("event", "pull_request"),
    ("workflow_id", 123), ("run_attempt", 3), ("status", "in_progress"),
    ("conclusion", "failure"), ("run_attempt", True),
    ("run_started_at", "2026-10-01T00:00:00Z"),
    ("updated_at", "2026-11-01T00:00:00Z"),
])
@pytest.mark.parametrize("suffix", ["", "/attempts/2"])
def test_ci_rejects_wrong_stale_failed_and_rerun_metadata(field, value, suffix) -> None:
    responses = ci_responses()
    record = dict(responses[PREFIX + f"/actions/runs/{CI_ID}" + suffix])
    record[field] = value
    responses[PREFIX + f"/actions/runs/{CI_ID}" + suffix] = record
    with pytest.raises(ValueError):
        authenticate_ci(FixtureAPI(responses), subject(), now=NOW)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "skipped", "wrong_name", "total"])
def test_ci_requires_complete_unique_successful_job_list(mutation) -> None:
    responses = ci_responses()
    path = PREFIX + f"/actions/runs/{CI_ID}/attempts/2/jobs?per_page=100&page=1"
    result = dict(responses[path])
    jobs = list(result["jobs"])
    if mutation == "missing":
        jobs.pop()
    elif mutation == "duplicate":
        jobs[-1] = jobs[0]
    elif mutation == "skipped":
        jobs[0] = {**jobs[0], "conclusion": "skipped"}
    elif mutation == "wrong_name":
        jobs[0] = {**jobs[0], "name": "not-a-certified-cell"}
    else:
        result["total_count"] = 999
    result["jobs"] = jobs
    responses[path] = result
    with pytest.raises(ValueError):
        authenticate_ci(FixtureAPI(responses), subject(), now=NOW)


def preparation_responses() -> dict[str, object]:
    responses = ci_responses()
    owner = {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN, "type": "User"}
    run = {**responses[PREFIX + f"/actions/runs/{CI_ID}"], "id": 45,
           "workflow_id": 55, "path": policy.PREPARATION_WORKFLOW,
           "event": "workflow_dispatch", "run_attempt": 1,
           "actor": owner, "triggering_actor": owner}
    responses.update({
        PREFIX + "/actions/workflows/prepare-publication.yml":
            {"id": 55, "path": policy.PREPARATION_WORKFLOW, "state": "active"},
        PREFIX + "/actions/runs/45": run,
        PREFIX + "/actions/runs/45/attempts/1": run,
        PREFIX + "/actions/runs/45/attempts/1/jobs?per_page=100&page=1":
            {"total_count": 2, "jobs": [
                {"id": 11, "name": "build", "status": "completed", "conclusion": "success"},
                {"id": 12, "name": "attest", "status": "completed", "conclusion": "success"}]},
        PREFIX + "/actions/artifacts/88":
            {"id": 88, "name": "publication-candidate", "size_in_bytes": 1000,
             "digest": "sha256:" + "d" * 64, "expired": False,
             "created_at": "2026-10-31T02:20:00Z", "updated_at": "2026-10-31T02:20:00Z",
             "expires_at": "2026-11-01T02:20:00Z", "workflow_run": {
                 "id": 45, "repository_id": policy.REPOSITORY_ID,
                 "head_repository_id": policy.REPOSITORY_ID, "head_sha": CANDIDATE}},
    })
    return responses


def test_preparation_requires_whole_build_and_attest_run_and_exact_final_artifact() -> None:
    result = authenticate_preparation(FixtureAPI(preparation_responses()), subject(),
                                      artifact_id=88, archive_sha256="d" * 64, now=NOW)
    assert result["run_id"] == 45
    assert result["artifact"]["id"] == 88


@pytest.mark.parametrize("field", ["actor", "triggering_actor"])
def test_nonowner_original_or_rerun_actor_cannot_authorize_preparation(field) -> None:
    responses = preparation_responses()
    run = {**responses[PREFIX + "/actions/runs/45"], field:
           {"id": 999, "login": "other", "type": "User"}}
    responses[PREFIX + "/actions/runs/45"] = run
    with pytest.raises(ValueError, match="owner"):
        authenticate_preparation(FixtureAPI(responses), subject(), artifact_id=88,
                                 archive_sha256="d" * 64, now=NOW)


@pytest.mark.parametrize("field,value", [
    ("name", "publication-build"), ("expired", True), ("size_in_bytes", True),
    ("size_in_bytes", policy.MAX_ARCHIVE_BYTES + 1), ("digest", "sha256:" + "e" * 64),
    ("expires_at", "2026-10-31T02:00:00Z"),
])
def test_preparation_rejects_intermediate_expired_wrong_or_oversized_artifact(field, value) -> None:
    responses = preparation_responses()
    responses[PREFIX + "/actions/artifacts/88"] = {
        **responses[PREFIX + "/actions/artifacts/88"], field: value}
    with pytest.raises(ValueError):
        authenticate_preparation(FixtureAPI(responses), subject(), artifact_id=88,
                                 archive_sha256="d" * 64, now=NOW)


def test_preparation_cannot_approve_a_still_running_parent() -> None:
    responses = preparation_responses()
    responses[PREFIX + "/actions/runs/45"] = {
        **responses[PREFIX + "/actions/runs/45"], "status": "in_progress", "conclusion": None}
    with pytest.raises(ValueError):
        authenticate_preparation(FixtureAPI(responses), subject(), artifact_id=88,
                                 archive_sha256="d" * 64, now=NOW)


def test_ci_expires_at_the_exact_lifetime_boundary() -> None:
    responses = ci_responses()
    for suffix in ("", "/attempts/2"):
        path = PREFIX + f"/actions/runs/{CI_ID}" + suffix
        responses[path] = {**responses[path], "run_started_at": "2026-10-24T03:00:00Z",
                           "updated_at": "2026-10-24T03:30:00Z"}
    with pytest.raises(ValueError, match="expired"):
        authenticate_ci(FixtureAPI(responses), subject(), now=NOW)


def test_preparation_rejects_an_artifact_created_before_the_latest_attempt() -> None:
    responses = preparation_responses()
    for suffix in ("", "/attempts/1"):
        path = PREFIX + "/actions/runs/45" + suffix
        responses[path] = {**responses[path], "run_started_at": "2026-10-31T02:25:00Z"}
    with pytest.raises(ValueError, match="attempt"):
        authenticate_preparation(FixtureAPI(responses), subject(), artifact_id=88,
                                 archive_sha256="d" * 64, now=NOW)


def test_provider_unavailability_is_a_sanitized_fail_closed_contract_error() -> None:
    class Unavailable(FixtureAPI):
        def json(self, path: str) -> object:
            raise OSError("untrusted provider details must not reach the error")

    with pytest.raises(ValueError, match="lookup unavailable"):
        authenticate_ci(Unavailable({}), subject(), now=NOW)
