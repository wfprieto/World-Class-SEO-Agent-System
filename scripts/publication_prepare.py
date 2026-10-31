"""Unprivileged single build and a separate byte-only internal attestation handoff."""

from __future__ import annotations

import hashlib
import sys
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts import publication_policy as policy
from scripts.publication_artifacts import unpack_candidate
from scripts.publication_bundle import archive_identity
from scripts.publication_context import workflow_context
from scripts.publication_freshness import collect_time_proof
from scripts.publication_git import git
from scripts.publication_provider import authenticate_artifact, authenticate_ci, fresh_window
from scripts.publication_subject import (
    JsonObject,
    build_subject,
    instant,
    integer_value,
    object_value,
    payload_names,
    string_value,
)
from scripts.publication_transport import GitHubCLI, run_bounded


def output_directory(root: Path, output: Path) -> Path:
    selected = output.resolve()
    if selected.is_relative_to(root.resolve()) or (selected.exists() and any(selected.iterdir())):
        raise ValueError("Publication output requires an empty directory outside source")
    selected.mkdir(parents=True, exist_ok=True)
    return selected


def _command(root: Path, *arguments: str) -> None:
    run_bounded([sys.executable, "-B", *arguments], cwd=root, limit=policy.MAX_API_BYTES, timeout=300)


def prepare_candidate(root: Path, api: GitHubCLI, *, ci_run_id: int,
                      output: Path, now: datetime) -> JsonObject:
    commit, run_id, attempt = workflow_context(root, api, policy.PREPARATION_WORKFLOW, "build")
    tree = git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    version = string_value(tomllib.loads((root / "pyproject.toml").read_text())
                           ["project"]["version"], "version")
    ci = object_value(api.json(f"/repos/{policy.REPOSITORY}/actions/runs/{ci_run_id}"), "CI")
    ci_attempt = integer_value(ci.get("run_attempt"), "CI attempt")
    header: JsonObject = {"repository": policy.REPOSITORY, "repository_id": policy.REPOSITORY_ID,
                          "owner_id": policy.OWNER_ID, "candidate_commit": commit,
                          "candidate_tree": tree, "ci_run_id": ci_run_id, "ci_attempt": ci_attempt}
    authenticate_ci(api, header, now=now)
    directory = output_directory(root, output)
    _command(root, "scripts/validate_dependency_lock.py")
    _command(root, "scripts/validate_release_version.py")
    _command(root, "-m", "scripts.inventory_comparator")
    _command(root, "scripts/scan_secrets.py")
    _command(root, "-m", "build", "--no-isolation", "--outdir", str(directory))
    names = payload_names(version)
    wheel = next(name for name, role in names.items() if role == "wheel")
    _command(root, "scripts/verify_clean_wheel.py", str(directory / wheel))
    _command(root, "scripts/generate_sbom.py", "--out", str(directory / "sbom.cdx.json"))
    _command(root, "scripts/generate_release_manifest.py", "--sbom", str(directory / "sbom.cdx.json"),
             "--out", str(directory / "release-manifest.json"))
    _command(root, "scripts/validate_release_artifacts.py", "--manifest",
             str(directory / "release-manifest.json"), "--sbom", str(directory / "sbom.cdx.json"))
    payloads = {name: (directory / name).read_bytes() for name in names if name != "SHA256SUMS"}
    payloads["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(payloads.items())
    ).encode("ascii")
    (directory / "SHA256SUMS").write_bytes(payloads["SHA256SUMS"])
    subject = build_subject(commit=commit, tree=tree, version=version, ci_run_id=ci_run_id,
                            ci_attempt=ci_attempt, prepare_run_id=run_id, prepare_attempt=attempt,
                            prepared_at=now, payloads=payloads)
    (directory / "publication-subject.json").write_bytes(subject)
    if {path.name for path in directory.iterdir()} != {*names, "publication-subject.json"}:
        raise ValueError("Build output contains unexpected files")
    return {"state": "PREPARED_UNATTESTED", "candidate_commit": commit, "run_id": run_id,
            "run_attempt": attempt, "subject_sha256": hashlib.sha256(subject).hexdigest()}


def _build_succeeded(api: GitHubCLI, run_id: int, attempt: int) -> JsonObject:
    result = object_value(api.json(f"/repos/{policy.REPOSITORY}/actions/runs/{run_id}"
                                  f"/attempts/{attempt}/jobs?per_page=100&page=1"), "internal jobs")
    jobs = result.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 2 or result.get("total_count") != 2:
        raise ValueError("Internal preparation requires exactly build and attest jobs")
    rows = [object_value(job, "internal job") for job in jobs]
    if {row.get("name") for row in rows} != {"build", "attest"}:
        raise ValueError("Unexpected internal preparation job identity")
    build = next(row for row in rows if row.get("name") == "build")
    if build.get("status") != "completed" or build.get("conclusion") != "success":
        raise ValueError("The actual current-attempt build has not succeeded")
    return build


def _build_interval(build: JsonObject, artifact: JsonObject, now: datetime) -> None:
    fresh_window({"run_started_at": build.get("started_at"), "updated_at": build.get("completed_at")},
                  now, policy.PREPARED_TTL_SECONDS)
    started = instant(build.get("started_at"), "actual build start")
    completed = instant(build.get("completed_at"), "actual build completion")
    created = instant(artifact.get("created_at"), "build artifact creation")
    updated = instant(artifact.get("updated_at"), "build artifact update")
    skew = timedelta(seconds=policy.CLOCK_SKEW_SECONDS)
    if not started - skew <= created <= updated <= completed + skew:
        raise ValueError("Intermediate artifact is outside its actual successful build interval")


def _verified_build_files(root: Path, api: GitHubCLI, *, artifact_id: int,
                          archive_sha256: str, now: datetime) -> tuple[str, dict[str, bytes]]:
    commit, run_id, attempt = workflow_context(root, api, policy.PREPARATION_WORKFLOW, "attest")
    build = _build_succeeded(api, run_id, attempt)
    _, digest = archive_identity(api, policy.REPOSITORY, artifact_id)
    if digest != archive_sha256:
        raise ValueError("Internal handoff digest differs from the actual build output")
    artifact = authenticate_artifact(api, repository=policy.REPOSITORY, repository_id=policy.REPOSITORY_ID,
                          run_id=run_id, artifact_id=artifact_id, archive_sha256=digest,
                          source_commit=commit, now=now, artifact_name="publication-build")
    _build_interval(build, artifact, now)
    archive = api.binary(f"/repos/{policy.REPOSITORY}/actions/artifacts/{artifact_id}/zip",
                         policy.MAX_ARCHIVE_BYTES)
    subject, files = unpack_candidate(archive, expected_archive_sha256=digest, now=now)
    if (subject["candidate_commit"] != commit or subject["prepare_run_id"] != run_id
            or subject["prepare_attempt"] != attempt):
        raise ValueError("Internal handoff belongs to another source/run/attempt")
    authenticate_ci(api, subject, now=now)
    return commit, files


def verify_build(root: Path, api: GitHubCLI, *, artifact_id: int, archive_sha256: str,
                 output: Path, now: datetime) -> JsonObject:
    entered = datetime.now(UTC)
    with collect_time_proof() as proof:
        commit, files = _verified_build_files(root, api, artifact_id=artifact_id,
                                              archive_sha256=archive_sha256, now=now)
        proof.assert_current(entered)
        directory = output_directory(root, output)
        proof.assert_current(datetime.now(UTC))
        for name, data in files.items():
            (directory / name).write_bytes(data)
        proof.assert_current(datetime.now(UTC))
        return {"state": "PREPARED_VERIFIED_INTERNAL", "candidate_commit": commit,
                "subject_sha256": hashlib.sha256(files["publication-subject.json"]).hexdigest()}
