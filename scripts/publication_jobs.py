"""Actual hosted job binding for previously validated, producer-sealed observations."""

import re
from datetime import datetime, timedelta

from scripts import publication_policy as policy
from scripts.publication_provider import PublicationAPI
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    instant,
    integer_value,
    object_value,
    require_fresh,
    sha_value,
    string_value,
)


def _jobs(api: PublicationAPI, repository: str, run: int, attempt: int) -> dict[int, JsonObject]:
    found: dict[int, JsonObject] = {}
    total: int | None = None
    for page in range(1, policy.MAX_API_PAGES + 1):
        response = object_value(api.json(f"/repos/{repository}/actions/runs/{run}/attempts/{attempt}"
                                         f"/jobs?per_page={policy.PAGE_SIZE}&page={page}"), "producer jobs")
        count = integer_value(response.get("total_count"), "producer job count")
        if count > policy.MAX_API_PAGES * policy.PAGE_SIZE or (total is not None and count != total):
            raise ValueError("Producer job inventory is unbounded or changed during pagination")
        total = count
        rows = response.get("jobs")
        if not isinstance(rows, list) or not 0 < len(rows) <= policy.PAGE_SIZE:
            raise ValueError("Producer job inventory is missing or truncated")
        for value in rows:
            job = object_value(value, "producer job")
            identity = integer_value(job.get("id"), "producer job ID")
            if identity in found:
                raise ValueError("Duplicate producer job identity")
            found[identity] = job
        if len(found) == total:
            return found
        if len(found) > total or len(rows) != policy.PAGE_SIZE:
            raise ValueError("Producer job inventory does not reconcile to its complete count")
    raise ValueError("Producer job pagination exceeded its bound")


def _job_claim(job: JsonObject, claim: JsonObject, run: JsonObject, now: datetime) -> None:
    if integer_value(job.get("run_id"), "job run") != run["id"]:
        raise ValueError("Observation job belongs to a different run")
    if "run_attempt" in job and integer_value(job["run_attempt"], "job attempt") != run["run_attempt"]:
        raise ValueError("Observation job belongs to a different attempt")
    if (sha_value(job.get("head_sha"), 40, "job source") != run["head_sha"]
            or job.get("status") != "completed" or job.get("conclusion") != "success"):
        raise ValueError("Observation job source/execution is not a successful exact producer")
    labels = job.get("labels")
    if not isinstance(labels, list) or not all(isinstance(label, str) for label in labels):
        raise ValueError("Actual runner labels are missing")
    normalized = {str(label).lower() for label in labels}
    expected_label = {"ubuntu": "ubuntu-latest", "windows": "windows-latest"}[str(claim["platform"])]
    if "self-hosted" in normalized or expected_label not in normalized:
        raise ValueError("Observation platform does not match its actual hosted runner")
    start = instant(job.get("started_at"), "actual job start")
    end = require_fresh(job.get("completed_at"), now=now, ttl=policy.EVIDENCE_TTL_SECONDS,
                        label="actual job completion")
    observed = instant(claim["executed_at"], "actual observation time")
    skew = timedelta(seconds=policy.CLOCK_SKEW_SECONDS)
    if end < start or not start - skew <= observed <= end + skew:
        raise ValueError("Observation time is outside its actual successful job interval")


def authenticate_jobs(api: PublicationAPI, *, receipt: JsonObject,
                      claims: list[JsonObject], now: datetime) -> None:
    run = object_value(receipt.get("run"), "authenticated producer run")
    repository = string_value(object_value(run.get("repository"), "producer repository").get("full_name"),
                              "producer repository name")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None:
        raise ValueError("Producer repository name is invalid")
    identity = integer_value(run.get("id"), "producer run")
    attempt = integer_value(run.get("run_attempt"), "producer attempt")
    sha_value(run.get("head_sha"), 40, "producer source")
    if not claims:
        raise ValueError("Live execution has no actual job-bound observations")
    platforms: dict[int, str] = {}
    jobs = _jobs(api, repository, identity, attempt)
    for claim in claims:
        exact_keys(claim, {"job_id", "platform", "executed_at"}, "actual job claim")
        job_id = integer_value(claim.get("job_id"), "observation job")
        platform = string_value(claim.get("platform"), "observation platform")
        if platform not in {"ubuntu", "windows"} or platforms.get(job_id, platform) != platform:
            raise ValueError("Observation has an unknown or contradictory platform")
        platforms[job_id] = platform
        if job_id not in jobs:
            raise ValueError("Observation job is absent from the exact latest producer attempt")
        _job_claim(jobs[job_id], claim, run, now)
