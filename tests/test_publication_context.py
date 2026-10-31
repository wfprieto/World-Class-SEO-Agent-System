"""Current GitHub execution, not a dispatch field, controls publication privileges."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import publication_policy as policy
from scripts.publication_context import workflow_context
from tests.test_publication_git import _evidence_repository


class ContextAPI:
    def __init__(self, commit: str) -> None:
        self.main = commit
        repository = {"id": policy.REPOSITORY_ID, "full_name": policy.REPOSITORY,
                      "owner": {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN}}
        self.run = {
            "id": 12, "run_attempt": 1, "head_sha": commit, "head_branch": "main",
            "event": "workflow_dispatch", "path": policy.PUBLICATION_WORKFLOW,
            "repository": repository, "head_repository": repository,
            "actor": {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN, "type": "User"},
            "triggering_actor": {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN, "type": "User"},
            "status": "in_progress", "conclusion": None,
        }
        self.jobs = [{"id": 91, "name": "publish", "run_id": 12, "head_sha": commit,
                      "status": "in_progress", "conclusion": None}]

    def json(self, path: str) -> object:
        if path == f"/repos/{policy.REPOSITORY}/git/ref/heads/main":
            return {"object": {"sha": self.main}}
        if path == f"/repos/{policy.REPOSITORY}/actions/runs/12/attempts/1/jobs?per_page=100&page=1":
            return {"total_count": len(self.jobs), "jobs": self.jobs}
        assert path == f"/repos/{policy.REPOSITORY}/actions/runs/12"
        return self.run


def _context(monkeypatch: pytest.MonkeyPatch, commit: str) -> None:
    for name, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": policy.REPOSITORY,
        "GITHUB_REPOSITORY_ID": str(policy.REPOSITORY_ID), "GITHUB_SHA": commit,
        "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "12", "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_JOB": "publish",
    }.items():
        monkeypatch.setenv(name, value)


def test_actual_owner_context_binds_source_run_attempt_and_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, *_ = _evidence_repository(tmp_path)
    _context(monkeypatch, source)
    assert workflow_context(tmp_path, ContextAPI(source), policy.PUBLICATION_WORKFLOW,
                            "publish") == (source, 12, 1)


@pytest.mark.parametrize("change", ["rerun_actor", "actor", "event", "attempt", "workflow"])
def test_context_rejects_changed_provider_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    source, *_ = _evidence_repository(tmp_path)
    _context(monkeypatch, source)
    api = ContextAPI(source)
    field, value = {
        "rerun_actor": ("triggering_actor", {"id": 9, "login": "untrusted"}),
        "actor": ("actor", {"id": 9, "login": "untrusted"}),
        "event": ("event", "pull_request_target"), "attempt": ("run_attempt", 2),
        "workflow": ("path", ".github/workflows/untrusted.yml"),
    }[change]
    api.run[field] = value
    with pytest.raises(ValueError):
        workflow_context(tmp_path, api, policy.PUBLICATION_WORKFLOW, "publish")


def test_source_drift_after_dispatch_revokes_privileged_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, *_ = _evidence_repository(tmp_path)
    _context(monkeypatch, source)
    api = ContextAPI(source)
    api.main = "d" * 40
    with pytest.raises(ValueError):
        workflow_context(tmp_path, api, policy.PUBLICATION_WORKFLOW, "publish")


@pytest.mark.parametrize("change", ["completed", "cancelled", "queued", "missing_job",
                                   "duplicate_job", "finished_job", "wrong_run", "wrong_source"])
def test_only_actual_live_current_job_can_use_privileges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str,
) -> None:
    source, *_ = _evidence_repository(tmp_path)
    _context(monkeypatch, source)
    api = ContextAPI(source)
    if change in {"completed", "cancelled", "queued"}:
        api.run["status"] = "queued" if change == "queued" else "completed"
        api.run["conclusion"] = "cancelled" if change == "cancelled" else None
    elif change == "missing_job":
        api.jobs.clear()
    elif change == "duplicate_job":
        api.jobs.append({**api.jobs[0], "id": 92})
    else:
        key, value = {"finished_job": ("status", "completed"), "wrong_run": ("run_id", 99),
                      "wrong_source": ("head_sha", "e" * 40)}[change]
        api.jobs[0][key] = value
    with pytest.raises(ValueError):
        workflow_context(tmp_path, api, policy.PUBLICATION_WORKFLOW, "publish")
