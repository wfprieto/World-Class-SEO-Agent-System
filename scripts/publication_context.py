"""Bind privileged operations to the actual owner-dispatched primary workflow."""

import os
from pathlib import Path
from typing import Protocol

from scripts import publication_policy as policy
from scripts.publication_git import git
from scripts.publication_provider import repository_identity
from scripts.publication_subject import integer_value, object_value, sha_value, string_value


class ContextAPI(Protocol):
    def json(self, path: str) -> object: ...


def _run_identity(run: dict[str, object], commit: str, run_id: int,
                  attempt: int, workflow: str) -> None:
    for field in ("repository", "head_repository"):
        repository_identity(run.get(field), policy.REPOSITORY, policy.REPOSITORY_ID, policy.OWNER_ID)
    expected = {"head_sha": commit, "head_branch": "main", "event": "workflow_dispatch",
                "path": workflow, "status": "in_progress", "conclusion": None}
    if (integer_value(run.get("id"), "run") != run_id
            or integer_value(run.get("run_attempt"), "attempt") != attempt
            or any(run.get(key) != value for key, value in expected.items())):
        raise ValueError("Provider run does not match the current primary workflow/source")
    for field in ("actor", "triggering_actor"):
        actor = object_value(run.get(field), field)
        if (integer_value(actor.get("id"), field) != policy.OWNER_ID
                or actor.get("login") != policy.OWNER_LOGIN or actor.get("type") != "User"):
            raise ValueError("Both original and rerun actors must be the actual owner")


def _active_job(current: dict[str, object], commit: str, run_id: int, attempt: int) -> None:
    expected = {"run_id": run_id, "head_sha": commit, "status": "in_progress", "conclusion": None}
    if (any(current.get(key) != value for key, value in expected.items())
            or ("run_attempt" in current
                and integer_value(current["run_attempt"], "job attempt") != attempt)):
        raise ValueError("Only the actual live current source/run/attempt/job can use privileges")


def _current_job(api: ContextAPI, commit: str, run_id: int, attempt: int,
                 workflow: str, job: str) -> None:
    allowed = {"build", "attest"} if workflow == policy.PREPARATION_WORKFLOW else {
        "authorize", "publish", "complete",
    }
    response = object_value(api.json(f"/repos/{policy.REPOSITORY}/actions/runs/{run_id}"
                                    f"/attempts/{attempt}/jobs?per_page=100&page=1"), "current jobs")
    count = integer_value(response.get("total_count"), "current job count")
    raw = response.get("jobs")
    if not isinstance(raw, list) or len(raw) != count or count > len(allowed):
        raise ValueError("Current-attempt job inventory is incomplete or unexpected")
    rows = [object_value(row, "current job") for row in raw]
    names = [string_value(row.get("name"), "job name") for row in rows]
    identities = [integer_value(row.get("id"), "job ID") for row in rows]
    if (len(set(names)) != len(names) or len(set(identities)) != len(identities)
            or not set(names).issubset(allowed) or job not in names):
        raise ValueError("Current job identity is missing, duplicated or unexpected")
    current = next(row for row in rows if row.get("name") == job)
    _active_job(current, commit, run_id, attempt)


def workflow_context(root: Path, api: ContextAPI, workflow: str, job: str) -> tuple[str, int, int]:
    expected = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": policy.REPOSITORY,
        "GITHUB_REPOSITORY_ID": str(policy.REPOSITORY_ID),
        "GITHUB_REF": "refs/heads/main", "GITHUB_JOB": job,
    }
    if workflow not in {policy.PREPARATION_WORKFLOW, policy.PUBLICATION_WORKFLOW}:
        raise ValueError("Workflow is not a publication authority")
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise ValueError("Publication requires its exact primary main workflow/job")
    commit = sha_value(os.environ.get("GITHUB_SHA"), 40, "current source")
    if git(root, "rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("Checked-out source does not match the current workflow commit")
    try:
        run_id = integer_value(int(os.environ.get("GITHUB_RUN_ID", "")), "current run")
        attempt = integer_value(int(os.environ.get("GITHUB_RUN_ATTEMPT", "")), "current attempt")
    except ValueError:
        raise ValueError("Current run/attempt must be positive integers") from None
    run = object_value(api.json(f"/repos/{policy.REPOSITORY}/actions/runs/{run_id}"), "current run")
    _run_identity(run, commit, run_id, attempt, workflow)
    _current_job(api, commit, run_id, attempt, workflow, job)
    main = object_value(api.json(f"/repos/{policy.REPOSITORY}/git/ref/heads/main"), "main")
    if object_value(main.get("object"), "main source").get("sha") != commit:
        raise ValueError("Protected main changed after dispatch")
    return commit, run_id, attempt
