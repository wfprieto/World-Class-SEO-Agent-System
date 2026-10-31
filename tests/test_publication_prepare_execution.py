"""Offline preparation controls: synthetic provider/build IO, real boundary validators.

Payloads are deliberately not installable distributions. These tests certify neither
hosted execution, installed-wheel behavior, cryptographic attestations nor publication.
"""

from __future__ import annotations

import hashlib
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from scripts import publication_context as context
from scripts import publication_policy as policy
from scripts import publication_prepare as prepare
from scripts import validate_release_version as versions
from scripts.publication_subject import build_subject, parse_subject, subject_files
from tests.test_publication_artifacts import payloads, zip_bytes
from tests.test_publication_provider import CANDIDATE, CI_ID, NOW, PREFIX, TREE, ci_responses

RUN_ID = 45
ARTIFACT_ID = 88
JOBS_PATH = PREFIX + "/actions/runs/45/attempts/1/jobs?per_page=100&page=1"
ARTIFACT_PATH = PREFIX + "/actions/artifacts/88"


class PreparationFixtureClock:
    """Explicit clock IO for this synthetic dated universe, never source policy."""

    @classmethod
    def now(cls, zone: object) -> datetime:
        assert zone is UTC
        return NOW


class PreparationAPI:
    """Only predetermined read responses; unexpected or mutating IO is an error."""

    def __init__(self, job: str) -> None:
        self.responses = ci_responses()
        owner = {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN, "type": "User"}
        run = {**self.responses[PREFIX + f"/actions/runs/{CI_ID}"], "id": RUN_ID,
               "path": policy.PREPARATION_WORKFLOW, "event": "workflow_dispatch",
               "run_attempt": 1, "status": "in_progress", "conclusion": None,
               "actor": owner, "triggering_actor": owner}
        build = {"id": 81, "name": "build", "run_id": RUN_ID, "run_attempt": 1,
                 "head_sha": CANDIDATE, "status": "in_progress", "conclusion": None,
                 "started_at": "2026-10-31T02:00:00Z", "completed_at": None}
        jobs = [build]
        if job == "attest":
            build.update(status="completed", conclusion="success",
                         completed_at="2026-10-31T02:30:00Z")
            jobs.append({**build, "id": 82, "name": "attest", "status": "in_progress",
                         "conclusion": None, "completed_at": None})
        self.responses.update({PREFIX + "/actions/runs/45": run,
                               PREFIX + "/git/ref/heads/main": {"object": {"sha": CANDIDATE}},
                               JOBS_PATH: {"total_count": len(jobs), "jobs": jobs}})
        self.calls: list[str] = []
        self.archive = b""

    def json(self, path: str) -> object:
        self.calls.append(path)
        return deepcopy(self.responses[path])

    def binary(self, path: str, limit: int) -> bytes:
        self.calls.append(path)
        assert path == ARTIFACT_PATH + "/zip"
        assert limit == policy.MAX_ARCHIVE_BYTES
        return self.archive

    def install_archive(self, **subject_changes: object) -> dict[str, bytes]:
        files = payloads()
        arguments = {"commit": CANDIDATE, "tree": TREE, "version": "1.7.1",
                     "ci_run_id": CI_ID, "ci_attempt": 2, "prepare_run_id": RUN_ID,
                     "prepare_attempt": 1, "prepared_at": NOW - timedelta(minutes=45), "payloads": files}
        files["publication-subject.json"] = build_subject(**(arguments | subject_changes))
        self.archive = zip_bytes(files)
        self.responses[ARTIFACT_PATH] = {
            "id": ARTIFACT_ID, "name": "publication-build", "size_in_bytes": len(self.archive),
            "digest": "sha256:" + hashlib.sha256(self.archive).hexdigest(), "expired": False,
            "created_at": "2026-10-31T02:20:00Z", "updated_at": "2026-10-31T02:20:00Z",
            "expires_at": "2026-11-01T02:20:00Z", "workflow_run": {
                "id": RUN_ID, "repository_id": policy.REPOSITORY_ID,
                "head_repository_id": policy.REPOSITORY_ID, "head_sha": CANDIDATE},
        }
        return files


class BuildIO:
    """In-memory command observer and synthetic output writer, never a subprocess."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls: list[list[str]] = []
        self.output: Path | None = None

    def __call__(self, arguments: list[str], *, cwd: Path, limit: int, timeout: int) -> bytes:
        assert arguments[:2] == [sys.executable, "-B"]
        assert cwd == self.root and limit == policy.MAX_API_BYTES and timeout == 300
        command = arguments[2:]
        self.calls.append(command)
        if command == ["scripts/validate_release_version.py"]:
            failures = versions.validate(self.root)
            if failures:
                raise ValueError("; ".join(failures))
        elif command[:2] == ["-m", "build"]:
            self.output = Path(command[command.index("--outdir") + 1])
            for name, data in payloads().items():
                if name.endswith((".whl", ".tar.gz")):
                    (self.output / name).write_bytes(data)
        elif command[:1] == ["scripts/generate_sbom.py"]:
            Path(command[-1]).write_bytes(payloads()["sbom.cdx.json"])
        elif command[:1] == ["scripts/generate_release_manifest.py"]:
            Path(command[-1]).write_bytes(payloads()["release-manifest.json"])
        return b"synthetic subprocess seam; not real command output"


def source_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, job: str) -> Path:
    # Dedicated expiry/rollback tests can override this seam after setup.
    monkeypatch.setattr(prepare, "datetime", PreparationFixtureClock)
    root = tmp_path / "source"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "pyproject.toml").write_text('[project]\nversion = "1.7.1"\n', encoding="utf-8")
    (root / "CHANGELOG.md").write_text("## [1.7.1]\n", encoding="utf-8")
    (root / "docs" / "INTEGRATION-MANIFEST.md").write_text(
        "**Version:** `1.7.1`\n", encoding="utf-8")
    environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": policy.REPOSITORY,
                   "GITHUB_REPOSITORY_ID": str(policy.REPOSITORY_ID),
                   "GITHUB_REF": "refs/heads/main", "GITHUB_JOB": job,
                   "GITHUB_SHA": CANDIDATE, "GITHUB_RUN_ID": str(RUN_ID), "GITHUB_RUN_ATTEMPT": "1"}
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    def synthetic_git(directory: Path, *arguments: str) -> bytes:
        assert directory == root
        return {("rev-parse", "HEAD"): CANDIDATE.encode(),
                ("rev-parse", "HEAD^{tree}"): TREE.encode()}[arguments]

    monkeypatch.setattr(context, "git", synthetic_git)
    monkeypatch.setattr(prepare, "git", synthetic_git)
    return root


def verify(root: Path, api: PreparationAPI, output: Path, digest: str | None = None) -> dict[str, object]:
    return prepare.verify_build(root, api, artifact_id=ARTIFACT_ID,
                                archive_sha256=digest or hashlib.sha256(api.archive).hexdigest(),
                                output=output, now=NOW)


def test_preparation_constructs_exact_detached_subject_and_checksum_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = source_context(tmp_path, monkeypatch, "build")
    api, commands = PreparationAPI("build"), BuildIO(root)
    monkeypatch.setattr(prepare, "run_bounded", commands)
    output = tmp_path / "prepared"
    result = prepare.prepare_candidate(root, api, ci_run_id=CI_ID, output=output, now=NOW)
    files = {path.name: path.read_bytes() for path in output.iterdir()}
    raw = files.pop("publication-subject.json")
    subject = parse_subject(raw, now=NOW)
    assert files == payloads()
    assert subject["candidate_commit"] == CANDIDATE and subject["candidate_tree"] == TREE
    assert subject["prepared_at"] == NOW.isoformat()
    assert (subject["ci_run_id"], subject["ci_attempt"]) == (CI_ID, 2)
    assert (subject["prepare_run_id"], subject["prepare_attempt"]) == (RUN_ID, 1)
    assert (subject["version"], subject["planned_tag"]) == ("1.7.1", "v1.7.1")
    for name, record in subject_files(subject).items():
        assert (record["bytes"], record["sha256"]) == (len(files[name]), hashlib.sha256(files[name]).hexdigest())
    assert result == {"state": "PREPARED_UNATTESTED", "candidate_commit": CANDIDATE,
                      "run_id": RUN_ID, "run_attempt": 1, "subject_sha256": hashlib.sha256(raw).hexdigest()}


def test_preparation_invokes_module_safe_comparator_before_single_clean_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = source_context(tmp_path, monkeypatch, "build")
    commands = BuildIO(root)
    monkeypatch.setattr(prepare, "run_bounded", commands)
    output = tmp_path / "prepared"
    prepare.prepare_candidate(root, PreparationAPI("build"), ci_run_id=CI_ID, output=output, now=NOW)
    wheel = output / "world_class_seo_agent_system-1.7.1-py3-none-any.whl"
    assert commands.calls == [
        ["scripts/validate_dependency_lock.py"], ["scripts/validate_release_version.py"],
        ["-m", "scripts.inventory_comparator"], ["scripts/scan_secrets.py"],
        ["-m", "build", "--no-isolation", "--outdir", str(output)],
        ["scripts/verify_clean_wheel.py", str(wheel)],
        ["scripts/generate_sbom.py", "--out", str(output / "sbom.cdx.json")],
        ["scripts/generate_release_manifest.py", "--sbom", str(output / "sbom.cdx.json"),
         "--out", str(output / "release-manifest.json")],
        ["scripts/validate_release_artifacts.py", "--manifest", str(output / "release-manifest.json"),
         "--sbom", str(output / "sbom.cdx.json")],
    ]


@pytest.mark.parametrize("destination", ["source", "nested", "nonempty"])
def test_preparation_rejects_unsafe_output_before_any_build_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, destination: str,
) -> None:
    root = source_context(tmp_path, monkeypatch, "build")
    output = {"source": root, "nested": root / "dist", "nonempty": tmp_path / "occupied"}[destination]
    if destination == "nonempty":
        output.mkdir()
        (output / "preserve.txt").write_bytes(b"existing bytes")
    commands = BuildIO(root)
    monkeypatch.setattr(prepare, "run_bounded", commands)
    with pytest.raises(ValueError, match="empty directory outside source"):
        prepare.prepare_candidate(root, PreparationAPI("build"), ci_run_id=CI_ID, output=output, now=NOW)
    assert not commands.calls
    if destination == "nonempty":
        assert (output / "preserve.txt").read_bytes() == b"existing bytes"
    monkeypatch.setenv("GITHUB_JOB", "attest")
    api = PreparationAPI("attest")
    api.install_archive()
    with pytest.raises(ValueError, match="empty directory outside source"):
        verify(root, api, output)
    if destination == "nonempty":
        assert (output / "preserve.txt").read_bytes() == b"existing bytes"


def test_actual_version_disagreement_blocks_build_without_requiring_public_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = source_context(tmp_path, monkeypatch, "build")
    (root / "CHANGELOG.md").write_text("## [1.7.0]\n", encoding="utf-8")
    commands = BuildIO(root)
    monkeypatch.setattr(prepare, "run_bounded", commands)
    output = tmp_path / "prepared"
    with pytest.raises(ValueError, match="version sources disagree"):
        prepare.prepare_candidate(root, PreparationAPI("build"), ci_run_id=CI_ID, output=output, now=NOW)
    assert commands.calls == [["scripts/validate_dependency_lock.py"], ["scripts/validate_release_version.py"]]
    assert not list(output.iterdir())


@pytest.mark.parametrize("mutation", ["main", "checkout", "job_source", "ci_source", "ci_tree", "ci_cell"])
def test_preparation_source_main_job_and_ci_must_agree_before_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    root = source_context(tmp_path, monkeypatch, "build")
    api, commands = PreparationAPI("build"), BuildIO(root)
    monkeypatch.setattr(prepare, "run_bounded", commands)
    if mutation == "main":
        api.responses[PREFIX + "/git/ref/heads/main"] = {"object": {"sha": "c" * 40}}
    elif mutation == "checkout":
        monkeypatch.setenv("GITHUB_SHA", "c" * 40)
    elif mutation == "job_source":
        api.responses[JOBS_PATH]["jobs"][0]["head_sha"] = "c" * 40
    elif mutation == "ci_source":
        api.responses[PREFIX + f"/actions/runs/{CI_ID}"]["head_sha"] = "c" * 40
    elif mutation == "ci_tree":
        api.responses[PREFIX + "/git/commits/" + CANDIDATE]["tree"]["sha"] = "c" * 40
    else:
        api.responses[PREFIX + "/actions/runs/44/attempts/2/jobs?per_page=100&page=1"]["jobs"][0]["conclusion"] = "skipped"
    with pytest.raises(ValueError):
        prepare.prepare_candidate(root, api, ci_run_id=CI_ID, output=tmp_path / "prepared", now=NOW)
    assert not commands.calls
    assert not (tmp_path / "prepared").exists()


def test_attest_stage_reconstructs_only_exact_authenticated_intermediate_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = source_context(tmp_path, monkeypatch, "attest")
    api = PreparationAPI("attest")
    expected = api.install_archive()
    output = tmp_path / "verified"
    result = verify(root, api, output)
    assert {path.name: path.read_bytes() for path in output.iterdir()} == expected
    assert result == {"state": "PREPARED_VERIFIED_INTERNAL", "candidate_commit": CANDIDATE,
                      "subject_sha256": hashlib.sha256(expected["publication-subject.json"]).hexdigest()}
    assert ARTIFACT_PATH + "/zip" in api.calls
    assert PREFIX + "/actions/runs/44/attempts/2/jobs?per_page=100&page=1" in api.calls


@pytest.mark.parametrize("mutation", ["unfinished", "failed", "duplicate", "extra", "count"])
def test_attest_stage_requires_successful_exact_build_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    root = source_context(tmp_path, monkeypatch, "attest")
    api = PreparationAPI("attest")
    api.install_archive()
    jobs = api.responses[JOBS_PATH]
    if mutation in {"unfinished", "failed"}:
        jobs["jobs"][0].update(status="in_progress" if mutation == "unfinished" else "completed",
                               conclusion=None if mutation == "unfinished" else "failure")
    elif mutation == "duplicate":
        jobs["jobs"][0]["name"] = "attest"
    elif mutation == "extra":
        jobs["jobs"].append({**jobs["jobs"][0], "id": 90, "name": "untrusted"})
        jobs["total_count"] = 3
    else:
        jobs["total_count"] = 3
    with pytest.raises(ValueError):
        verify(root, api, tmp_path / "verified")
    assert ARTIFACT_PATH + "/zip" not in api.calls
    assert not (tmp_path / "verified").exists()


@pytest.mark.parametrize("mutation", ["run", "source", "repository", "name", "expired", "digest",
                                      "id", "expiry", "bool_size", "oversize"])
def test_attest_stage_rejects_substituted_or_expired_intermediate_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    root = source_context(tmp_path, monkeypatch, "attest")
    api = PreparationAPI("attest")
    api.install_archive()
    record = api.responses[ARTIFACT_PATH]
    if mutation in {"run", "source", "repository"}:
        key, value = {"run": ("id", 99), "source": ("head_sha", "c" * 40),
                      "repository": ("head_repository_id", 9)}[mutation]
        record["workflow_run"][key] = value
    else:
        key, value = {"name": ("name", "publication-candidate"), "expired": ("expired", True),
                      "digest": ("digest", "sha256:" + "e" * 64), "id": ("id", 99),
                      "expiry": ("expires_at", "2026-10-31T02:59:59Z"),
                      "bool_size": ("size_in_bytes", True),
                      "oversize": ("size_in_bytes", policy.MAX_ARCHIVE_BYTES + 1)}[mutation]
        record[key] = value
    with pytest.raises(ValueError):
        verify(root, api, tmp_path / "verified")
    assert ARTIFACT_PATH + "/zip" not in api.calls
    assert not (tmp_path / "verified").exists()


@pytest.mark.parametrize("failed_command", range(9))
def test_any_command_failure_prevents_subject_or_checksum_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_command: int,
) -> None:
    root = source_context(tmp_path, monkeypatch, "build")
    commands = BuildIO(root)

    def fail_at_boundary(arguments: list[str], **options: object) -> bytes:
        if len(commands.calls) == failed_command:
            raise RuntimeError("synthetic command failure")
        return commands(arguments, **options)

    monkeypatch.setattr(prepare, "run_bounded", fail_at_boundary)
    output = tmp_path / "prepared"
    with pytest.raises(RuntimeError, match="synthetic command failure"):
        prepare.prepare_candidate(root, PreparationAPI("build"), ci_run_id=CI_ID, output=output, now=NOW)
    assert len(commands.calls) == failed_command
    assert not (output / "publication-subject.json").exists()
    assert not (output / "SHA256SUMS").exists()


@pytest.mark.parametrize("changes", [{"commit": "c" * 40}, {"prepare_run_id": 99}, {"prepare_attempt": 2}])
def test_attest_stage_subject_must_belong_to_current_source_run_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, object],
) -> None:
    root = source_context(tmp_path, monkeypatch, "attest")
    api = PreparationAPI("attest")
    api.install_archive(**changes)
    with pytest.raises(ValueError, match="source/run/attempt"):
        verify(root, api, tmp_path / "verified")
    assert not (tmp_path / "verified").exists()


def test_attest_stage_rechecks_ci_and_archive_bytes_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = source_context(tmp_path, monkeypatch, "attest")
    api = PreparationAPI("attest")
    api.install_archive()
    api.responses[PREFIX + "/actions/runs/44/attempts/2"]["conclusion"] = "failure"
    with pytest.raises(ValueError):
        verify(root, api, tmp_path / "verified")
    api.responses = PreparationAPI("attest").responses
    api.install_archive()
    digest = hashlib.sha256(api.archive).hexdigest()
    api.archive += b"altered archive"
    with pytest.raises(ValueError, match="digest"):
        verify(root, api, tmp_path / "verified", digest=digest)
    assert not (tmp_path / "verified").exists()


@pytest.mark.parametrize("timestamp", ["2026-10-31T01:50:00Z", "2026-10-31T02:40:00Z"])
def test_intermediate_artifact_must_originate_within_actual_successful_build_interval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timestamp: str,
) -> None:
    root = source_context(tmp_path, monkeypatch, "attest")
    api = PreparationAPI("attest")
    api.install_archive()
    api.responses[ARTIFACT_PATH].update(created_at=timestamp, updated_at=timestamp)
    with pytest.raises(ValueError, match="build|attempt|interval"):
        verify(root, api, tmp_path / "verified")
    assert not (tmp_path / "verified").exists()
