"""Authenticated GitHub publication-provider boundaries."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Protocol

from scripts import publication_policy as policy
from scripts.publication_freshness import record_freshness, record_interval
from scripts.publication_subject import JsonObject, object_value


class PublicationAPI(Protocol):
    def json(self, path: str) -> object: ...

    def binary(self, path: str, limit: int) -> bytes: ...

    def graphql(self, query: str, variables: JsonObject) -> object: ...


def integer_value(value: object, label: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def text_value(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty string")
    return value


def timestamp(value: object, label: str) -> datetime:
    raw = text_value(value, label)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{label} must be a UTC timestamp") from None
    if parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be a UTC timestamp")
    return parsed.astimezone(UTC)


def fresh_window(record: JsonObject, now: datetime, ttl: int) -> None:
    if now.utcoffset() != timedelta(0):
        raise ValueError("verification clock must be UTC")
    start = timestamp(record.get("run_started_at", record.get("created_at")), "started")
    end = timestamp(record.get("updated_at", record.get("created_at")), "updated")
    if end < start or (end - now).total_seconds() > policy.CLOCK_SKEW_SECONDS:
        raise ValueError("provider timestamps are inconsistent or future-dated")
    if (start - now).total_seconds() > policy.CLOCK_SKEW_SECONDS:
        raise ValueError("provider execution is future-dated")
    if (now - start).total_seconds() >= ttl or (now - end).total_seconds() >= ttl:
        raise ValueError("provider evidence has expired")
    for issued in (start, end):
        record_freshness(issued, ttl=ttl, skew=policy.CLOCK_SKEW_SECONDS)


def read_object(api: PublicationAPI, path: str) -> JsonObject:
    try:
        return object_value(api.json(path), "provider response")
    except (OSError, RuntimeError):
        raise ValueError("publication provider lookup unavailable") from None


def repository_identity(value: object, repository: str, repository_id: int, owner_id: int) -> None:
    record = object_value(value, "repository")
    owner = object_value(record.get("owner"), "repository owner")
    if (record.get("full_name") != repository
            or integer_value(record.get("id"), "repository ID") != repository_id
            or integer_value(owner.get("id"), "owner ID") != owner_id
            or owner.get("login") != repository.split("/")[0]):
        raise ValueError("provider repository identity mismatch")


def _sha(value: object, label: str) -> str:
    result = text_value(value, label)
    if re.fullmatch(r"[0-9a-f]{40}", result) is None:
        raise ValueError(f"{label} must be an exact commit")
    return result


def _primary_source(api: PublicationAPI, commit: str, tree: str | None = None) -> str:
    _sha(commit, "candidate")
    prefix = f"/repos/{policy.REPOSITORY}"
    repository_identity(read_object(api, prefix), policy.REPOSITORY, policy.REPOSITORY_ID, policy.OWNER_ID)
    branch = read_object(api, prefix + "/branches/main")
    if branch.get("protected") is not True or object_value(branch.get("commit"), "main").get("sha") != commit:
        raise ValueError("candidate is not exact protected main")
    source = read_object(api, prefix + "/git/commits/" + commit)
    actual_tree = _sha(object_value(source.get("tree"), "source tree").get("sha"), "tree")
    if source.get("sha") != commit or (tree is not None and tree != actual_tree):
        raise ValueError("candidate source/tree mismatch")
    return actual_tree


def _owner_actor(record: JsonObject) -> None:
    for field in ("actor", "triggering_actor"):
        actor = object_value(record.get(field), field)
        if (integer_value(actor.get("id"), field) != policy.OWNER_ID
                or actor.get("login") != policy.OWNER_LOGIN or actor.get("type") != "User"):
            raise ValueError("publication trigger and rerun must belong to the owner")


def _execution_actor(record: JsonObject, actor_id: int) -> None:
    for field in ("actor", "triggering_actor"):
        actor = object_value(record.get(field), "registered execution actor")
        if (integer_value(actor.get("id"), "execution actor") != actor_id
                or not isinstance(actor.get("type"), str)
                or actor.get("type") not in {"User", "Bot"}
                or not text_value(actor.get("login"), "execution actor login")):
            raise ValueError("registered execution actor/rerun identity mismatch")


def authenticate_run(
    api: PublicationAPI, *, repository: str, repository_id: int, owner_id: int,
    workflow_id: int, workflow: str, run_id: int, attempt: int, commit: str,
    branch: str, event: str | None, now: datetime, ttl: int, owner_trigger: bool = False,
    actor_id: int | None = None,
) -> JsonObject:
    prefix = f"/repos/{repository}/actions/runs/{run_id}"
    latest = read_object(api, prefix)
    current = read_object(api, f"{prefix}/attempts/{attempt}")
    for record in (latest, current):
        repository_identity(record.get("repository"), repository, repository_id, owner_id)
        repository_identity(record.get("head_repository"), repository, repository_id, owner_id)
        if (integer_value(record.get("id"), "run") != run_id
                or integer_value(record.get("run_attempt"), "attempt") != attempt
                or integer_value(record.get("workflow_id"), "workflow") != workflow_id
                or record.get("path") != workflow or record.get("head_sha") != commit
                or record.get("head_branch") != branch or record.get("status") != "completed"
                or record.get("conclusion") != "success"
                or (event is not None and record.get("event") != event)):
            raise ValueError("provider run source/workflow/latest successful attempt mismatch")
        if owner_trigger:
            _owner_actor(record)
        if actor_id is not None:
            _execution_actor(record, actor_id)
        fresh_window(record, now, ttl)
    return current


def _certification_jobs(jobs: list[JsonObject], total: int | None,
                        expected: frozenset[str]) -> None:
    names = [text_value(job.get("name"), "job name") for job in jobs]
    ids = [integer_value(job.get("id"), "job ID") for job in jobs]
    if (len(jobs) != total or len(jobs) != len(expected) or set(names) != expected
            or len(set(names)) != len(names) or len(set(ids)) != len(ids)
            or any(job.get("status") != "completed" or job.get("conclusion") != "success" for job in jobs)):
        raise ValueError("provider requires every exact unique successful certification job")


def authenticate_jobs(
    api: PublicationAPI, *, repository: str, run_id: int, attempt: int,
    expected: frozenset[str],
) -> list[JsonObject]:
    jobs: list[JsonObject] = []
    total: int | None = None
    for page in range(1, policy.MAX_API_PAGES + 1):
        path = (f"/repos/{repository}/actions/runs/{run_id}/attempts/{attempt}/jobs"
                f"?per_page={policy.PAGE_SIZE}&page={page}")
        result = read_object(api, path)
        count = integer_value(result.get("total_count"), "job count")
        rows = result.get("jobs")
        if not isinstance(rows, list) or len(rows) > policy.PAGE_SIZE or (total is not None and total != count):
            raise ValueError("provider job pagination is inconsistent")
        total = count
        jobs.extend(object_value(row, "job") for row in rows)
        if len(rows) < policy.PAGE_SIZE:
            break
    else:
        raise ValueError("provider job pagination exceeded its bound")
    _certification_jobs(jobs, total, expected)
    return jobs


def authenticate_ci(
    api: PublicationAPI, subject: JsonObject, *, now: datetime
) -> JsonObject:
    """Authenticate the exact successful canonical validation attempt."""
    if (subject.get("repository") != policy.REPOSITORY
            or subject.get("repository_id") != policy.REPOSITORY_ID
            or subject.get("owner_id") != policy.OWNER_ID):
        raise ValueError("subject repository identity mismatch")
    commit = _sha(subject.get("candidate_commit"), "candidate")
    tree = _sha(subject.get("candidate_tree"), "tree")
    _primary_source(api, commit, tree)
    prefix = f"/repos/{policy.REPOSITORY}"
    workflow = read_object(api, prefix + f"/actions/workflows/{policy.VALIDATION_WORKFLOW_ID}")
    if (workflow.get("id") != policy.VALIDATION_WORKFLOW_ID
            or workflow.get("path") != policy.VALIDATION_WORKFLOW or workflow.get("state") != "active"):
        raise ValueError("canonical validation workflow identity mismatch")
    run_id = integer_value(subject.get("ci_run_id"), "CI run")
    attempt = integer_value(subject.get("ci_attempt"), "CI attempt")
    run = authenticate_run(api, repository=policy.REPOSITORY, repository_id=policy.REPOSITORY_ID,
                           owner_id=policy.OWNER_ID, workflow_id=policy.VALIDATION_WORKFLOW_ID,
                           workflow=policy.VALIDATION_WORKFLOW, run_id=run_id, attempt=attempt,
                           commit=commit, branch="main", event="push", now=now,
                           ttl=policy.EVIDENCE_TTL_SECONDS)
    jobs = authenticate_jobs(api, repository=policy.REPOSITORY, run_id=run_id,
                             attempt=attempt, expected=policy.EXPECTED_CI_JOBS)
    return {"run_id": run_id, "run_attempt": attempt, "candidate_commit": commit,
            "candidate_tree": tree, "run": run, "jobs": jobs}


def authenticate_artifact(
    api: PublicationAPI, *, repository: str, repository_id: int, run_id: int,
    artifact_id: int, archive_sha256: str, source_commit: str, now: datetime,
    artifact_name: str | None = None, ttl: int = policy.PREPARED_TTL_SECONDS,
) -> JsonObject:
    integer_value(artifact_id, "artifact ID")
    if re.fullmatch(r"[0-9a-f]{64}", archive_sha256) is None:
        raise ValueError("artifact digest must be exact SHA256")
    artifact = read_object(api, f"/repos/{repository}/actions/artifacts/{artifact_id}")
    source = object_value(artifact.get("workflow_run"), "artifact source")
    if (integer_value(artifact.get("id"), "artifact") != artifact_id
            or artifact.get("digest") != "sha256:" + archive_sha256 or artifact.get("expired") is not False
            or (artifact_name is not None and artifact.get("name") != artifact_name)
            or integer_value(source.get("id"), "artifact run") != run_id
            or integer_value(source.get("repository_id"), "artifact repository") != repository_id
            or integer_value(source.get("head_repository_id"), "artifact head repository") != repository_id
            or source.get("head_sha") != source_commit):
        raise ValueError("immutable provider artifact identity mismatch")
    if integer_value(artifact.get("size_in_bytes"), "archive size") > policy.MAX_ARCHIVE_BYTES:
        raise ValueError("provider archive exceeds the size limit")
    fresh_window(artifact, now, ttl)
    expiry = timestamp(artifact.get("expires_at"), "artifact expiry")
    if expiry <= now:
        raise ValueError("provider artifact has expired")
    record_interval(valid_after=datetime.min.replace(tzinfo=UTC), valid_before=expiry)
    return artifact


def artifact_attempt(artifact: JsonObject, run: JsonObject) -> None:
    created = timestamp(artifact.get("created_at"), "artifact created")
    updated = timestamp(artifact.get("updated_at"), "artifact updated")
    started = timestamp(run.get("run_started_at"), "attempt started")
    completed = timestamp(run.get("updated_at"), "attempt completed")
    if created < started or updated > completed or updated < created:
        raise ValueError("provider artifact does not belong to the exact latest attempt interval")


def authenticate_workflow_artifact(
    api: PublicationAPI, *, workflow: str, run_id: int, run_attempt: int,
    artifact_id: int, archive_sha256: str, source_commit: str, now: datetime,
    required_jobs: frozenset[str], artifact_name: str,
) -> JsonObject:
    allowed = {policy.PREPARATION_WORKFLOW: (frozenset({"build", "attest"}), "publication-candidate"),
               policy.PUBLICATION_WORKFLOW: (frozenset({"authorize", "publish", "complete"}),
                                             "publication-completion")}
    if allowed.get(workflow) != (required_jobs, artifact_name):
        raise ValueError("unexpected publication workflow/artifact contract")
    tree = _primary_source(api, source_commit)
    descriptor = read_object(api, f"/repos/{policy.REPOSITORY}/actions/workflows/{workflow.split('/')[-1]}")
    workflow_id = integer_value(descriptor.get("id"), "workflow")
    if descriptor.get("path") != workflow or descriptor.get("state") != "active":
        raise ValueError("publication workflow identity mismatch")
    run = authenticate_run(api, repository=policy.REPOSITORY, repository_id=policy.REPOSITORY_ID,
                           owner_id=policy.OWNER_ID, workflow_id=workflow_id, workflow=workflow,
                           run_id=integer_value(run_id, "run"), attempt=integer_value(run_attempt, "attempt"),
                           commit=source_commit, branch="main", event="workflow_dispatch", now=now,
                           ttl=policy.PREPARED_TTL_SECONDS, owner_trigger=True)
    jobs = authenticate_jobs(api, repository=policy.REPOSITORY, run_id=run_id,
                             attempt=run_attempt, expected=required_jobs)
    artifact = authenticate_artifact(api, repository=policy.REPOSITORY, repository_id=policy.REPOSITORY_ID,
                                     run_id=run_id, artifact_id=artifact_id, archive_sha256=archive_sha256,
                                     source_commit=source_commit, now=now, artifact_name=artifact_name)
    artifact_attempt(artifact, run)
    return {"run_id": run_id, "run_attempt": run_attempt, "candidate_commit": source_commit,
            "candidate_tree": tree, "run": run, "jobs": jobs, "artifact": artifact}


def authenticate_preparation(
    api: PublicationAPI, subject: JsonObject, *, artifact_id: int,
    archive_sha256: str, now: datetime,
) -> JsonObject:
    result = authenticate_workflow_artifact(
        api, workflow=policy.PREPARATION_WORKFLOW,
        run_id=integer_value(subject.get("prepare_run_id"), "preparation run"),
        run_attempt=integer_value(subject.get("prepare_attempt"), "preparation attempt"),
        artifact_id=artifact_id, archive_sha256=archive_sha256,
        source_commit=_sha(subject.get("candidate_commit"), "candidate"), now=now,
        required_jobs=frozenset({"build", "attest"}), artifact_name="publication-candidate")
    if result.get("candidate_tree") != subject.get("candidate_tree"):
        raise ValueError("preparation source tree mismatch")
    return result


def authenticate_decisions(
    api: PublicationAPI, subject: JsonObject, *, evidence_pr: int, evidence_commit: str,
    evidence_sha256: str, artifact_id: int, archive_sha256: str, subject_sha256: str,
    owner_comment_id: int, now: datetime,
) -> JsonObject:
    from scripts.publication_reviews import authenticate_decisions as decisions

    return decisions(api, subject, evidence_pr=evidence_pr, evidence_commit=evidence_commit,
                     evidence_sha256=evidence_sha256, artifact_id=artifact_id,
                     archive_sha256=archive_sha256, subject_sha256=subject_sha256,
                     owner_comment_id=owner_comment_id, now=now)


def authenticate_execution(
    api: PublicationAPI, *, pointer: JsonObject, authority: JsonObject,
    subject: JsonObject, now: datetime,
) -> JsonObject:
    from scripts.publication_execution import authenticate_execution as execution

    return execution(api, pointer=pointer, authority=authority, subject=subject, now=now)
