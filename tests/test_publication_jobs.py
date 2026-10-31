"""Synthetic provider metadata controls; no real execution authority or network."""

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from scripts.publication_jobs import authenticate_jobs

NOW = datetime(2026, 10, 31, 4, 0, tzinfo=UTC)
SHA = "a" * 40


class API:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.rows = [{"id": 123, "run_id": 90, "run_attempt": 2, "head_sha": SHA,
                      "status": "completed", "conclusion": "success", "labels": ["ubuntu-latest"],
                      "started_at": "2026-10-31T03:00:00Z", "completed_at": "2026-10-31T03:30:00Z"}]
        self.total = 1

    def json(self, endpoint: str) -> object:
        self.calls.append(endpoint)
        return {"total_count": self.total, "jobs": self.rows}

    def binary(self, _endpoint: str, _limit: int) -> bytes:
        pytest.fail("Job verification must not download or execute bytes")

    def graphql(self, _query: str, _variables: dict[str, str]) -> object:
        pytest.fail("Job verification has no GraphQL operation")


def receipt() -> dict:
    return {"run": {"id": 90, "run_attempt": 2, "head_sha": SHA,
                    "repository": {"full_name": "independent/producer"}}}


def claims() -> list[dict]:
    return [{"job_id": 123, "platform": "ubuntu", "executed_at": "2026-10-31T03:15:00Z"}]


def test_valid_job_uses_exact_registered_attempt() -> None:
    api = API()
    authenticate_jobs(api, receipt=receipt(), claims=claims(), now=NOW)
    assert api.calls == ["/repos/independent/producer/actions/runs/90/attempts/2/jobs?per_page=100&page=1"]


def test_documented_per_attempt_job_without_redundant_attempt_echo_is_valid() -> None:
    api = API()
    del api.rows[0]["run_attempt"]
    authenticate_jobs(api, receipt=receipt(), claims=claims(), now=NOW)


@pytest.mark.parametrize("field,value", [("id", True), ("run_id", 91), ("run_attempt", 1),
    ("head_sha", "b" * 40), ("status", "in_progress"), ("conclusion", "failure"),
    ("labels", ["self-hosted", "ubuntu-latest"]), ("labels", ["windows-latest"]),
    ("completed_at", "2026-10-31T02:30:00Z"), ("started_at", "2026-10-31T03:25:00Z")])
def test_reject_wrong_job_identity_status_source_platform_or_time(field: str, value: object) -> None:
    api = API()
    api.rows[0][field] = value
    with pytest.raises(ValueError):
        authenticate_jobs(api, receipt=receipt(), claims=claims(), now=NOW)


@pytest.mark.parametrize("change", ["missing", "duplicate", "count", "bool_count", "cross_platform", "bool_claim"])
def test_reject_missing_duplicate_truncated_and_ambiguous_jobs(change: str) -> None:
    api, observed = API(), claims()
    if change == "missing":
        observed[0]["job_id"] = 999
    elif change == "duplicate":
        api.rows.append(deepcopy(api.rows[0]))
        api.total = 2
    elif change == "count":
        api.total = 2
    elif change == "bool_count":
        api.total = True
    elif change == "cross_platform":
        observed.append({**observed[0], "platform": "windows"})
    else:
        observed[0]["job_id"] = True
    with pytest.raises(ValueError):
        authenticate_jobs(api, receipt=receipt(), claims=observed, now=NOW)
