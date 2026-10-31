"""Fetch immutable prepared bytes and verify actual GitHub attestation results."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TypedDict

from scripts import publication_policy as policy
from scripts.publication_artifacts import unpack_candidate, verify_attestation
from scripts.publication_provider import authenticate_ci, authenticate_preparation
from scripts.publication_subject import (
    JsonObject,
    integer_value,
    object_value,
    sha_value,
    string_value,
)
from scripts.publication_transport import GitHubCLI


class VerificationSource(TypedDict):
    repository: str
    workflow: str
    source_commit: str
    source_ref: str
    run_id: int
    run_attempt: int


@dataclass(frozen=True)
class CandidateBundle:
    subject: JsonObject
    files: dict[str, bytes]
    artifact_id: int
    archive_sha256: str

    @property
    def subject_sha256(self) -> str:
        return hashlib.sha256(self.files["publication-subject.json"]).hexdigest()


def archive_identity(api: GitHubCLI, repository: str, artifact_id: int) -> tuple[JsonObject, str]:
    integer_value(artifact_id, "artifact ID")
    record = object_value(api.json(f"/repos/{repository}/actions/artifacts/{artifact_id}"), "artifact")
    digest = string_value(record.get("digest"), "provider archive digest")
    if (not digest.startswith("sha256:") or record.get("id") != artifact_id
            or record.get("expired") is not False
            or integer_value(record.get("size_in_bytes"), "archive size") > policy.MAX_ARCHIVE_BYTES):
        raise ValueError("Provider artifact is expired, substituted or exceeds its size boundary")
    return record, sha_value(digest.removeprefix("sha256:"), 64, "archive digest")


def verify_bytes(
    api: GitHubCLI, data: bytes, *, name: str, repository: str, workflow: str,
    source_commit: str, source_ref: str, run_id: int, run_attempt: int,
    predicate_type: str = policy.PROVENANCE_PREDICATE,
) -> None:
    """Only successful real gh cryptographic verification may feed the shape verifier."""
    with TemporaryDirectory(prefix="wcseo-publication-attestation-") as temporary:
        path = Path(temporary) / name
        if path.parent != Path(temporary) or not data or len(data) > policy.MAX_MEMBER_BYTES:
            raise ValueError("Attestation subject is outside the flat bounded byte boundary")
        path.write_bytes(data)
        raw = api.command([
            "attestation", "verify", str(path), "--repo", repository,
            "--signer-workflow", repository + "/" + workflow,
            "--signer-digest", source_commit, "--source-digest", source_commit,
            "--source-ref", source_ref, "--deny-self-hosted-runners",
            "--predicate-type", predicate_type, "--format", "json",
        ])
        result: object = json.loads(raw)
        verify_attestation(result, name=name, digest=hashlib.sha256(data).hexdigest(),
                           repository=repository, workflow=workflow, source_commit=source_commit,
                           run_id=run_id, run_attempt=run_attempt, predicate_type=predicate_type)


def verify_candidate_bytes(api: GitHubCLI, bundle: CandidateBundle) -> None:
    subject = bundle.subject
    values: VerificationSource = {
        "repository": policy.REPOSITORY, "workflow": policy.PREPARATION_WORKFLOW,
        "source_commit": string_value(subject["candidate_commit"], "candidate"),
        "source_ref": "refs/heads/main",
        "run_id": integer_value(subject["prepare_run_id"], "preparation run"),
        "run_attempt": integer_value(subject["prepare_attempt"], "preparation attempt"),
    }
    for name, data in bundle.files.items():
        verify_bytes(api, data, name=name, **values)
    wheel = next(name for name in bundle.files if name.endswith(".whl"))
    verify_bytes(api, bundle.files[wheel], name=wheel, **values, predicate_type=policy.SBOM_PREDICATE)


def download_candidate(
    api: GitHubCLI, *, prepare_run_id: int, artifact_id: int, now: datetime,
) -> CandidateBundle:
    record, digest = archive_identity(api, policy.REPOSITORY, artifact_id)
    if object_value(record.get("workflow_run"), "artifact run").get("id") != prepare_run_id:
        raise ValueError("Selected preparation and immutable artifact do not match")
    archive = api.binary(f"/repos/{policy.REPOSITORY}/actions/artifacts/{artifact_id}/zip",
                         policy.MAX_ARCHIVE_BYTES)
    subject, files = unpack_candidate(archive, expected_archive_sha256=digest, now=now)
    if subject["prepare_run_id"] != prepare_run_id:
        raise ValueError("Prepared subject belongs to a different build run")
    authenticate_preparation(api, subject, artifact_id=artifact_id, archive_sha256=digest, now=now)
    authenticate_ci(api, subject, now=now)
    bundle = CandidateBundle(subject, files, artifact_id, digest)
    verify_candidate_bytes(api, bundle)
    return bundle
