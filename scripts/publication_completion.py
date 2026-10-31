"""Detached completion observation; only a consumer after producer success approves."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from scripts import publication_policy as policy
from scripts.publication_artifacts import inspect_result
from scripts.publication_authorize import authorize_candidate, canonical
from scripts.publication_bundle import archive_identity, verify_bytes
from scripts.publication_context import workflow_context
from scripts.publication_freshness import collect_time_proof
from scripts.publication_prepare import output_directory
from scripts.publication_provider import authenticate_workflow_artifact
from scripts.publication_remote import observed_release
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    integer_value,
    json_object,
    object_value,
    require_fresh,
    string_value,
)
from scripts.publication_transport import GitHubCLI

MEMBER = "publication-completion.json"
SELECTION_KEYS = ("prepare_run_id", "artifact_id", "evidence_pr", "owner_comment_id")
RECEIPT_KEYS = {"schema_version", "state", "repository", "repository_id", "binding",
                "publication_run_id", "publication_attempt", "observed_at", "publication",
                "gate_observations", "decisions_sha256"}


def _dependencies(api: GitHubCLI, commit: str, run_id: int, attempt: int) -> None:
    result = object_value(api.json(f"/repos/{policy.REPOSITORY}/actions/runs/{run_id}"
                                  f"/attempts/{attempt}/jobs?per_page=100&page=1"), "producer jobs")
    raw = result.get("jobs")
    if not isinstance(raw, list) or len(raw) != 3 or result.get("total_count") != 3:
        raise ValueError("Completion requires its exact three-job producer inventory")
    jobs = [object_value(row, "producer job") for row in raw]
    for name in ("authorize", "publish"):
        matching = [row for row in jobs if row.get("name") == name]
        if len(matching) != 1:
            raise ValueError("Completion dependency is missing or duplicated")
        expected = {"run_id": run_id, "head_sha": commit, "status": "completed", "conclusion": "success"}
        if any(matching[0].get(key) != value for key, value in expected.items()):
            raise ValueError("Actual current-attempt authorization/publication dependency did not succeed")


def _observe_completion(root: Path, api: GitHubCLI, *, selection: dict[str, int],
                        now: datetime) -> JsonObject:
    commit, run_id, attempt = workflow_context(root, api, policy.PUBLICATION_WORKFLOW, "complete")
    _dependencies(api, commit, run_id, attempt)
    candidate = authorize_candidate(root, api, **selection, now=now)
    publication = observed_release(api, candidate.bundle)
    fresh = authorize_candidate(root, api, **selection, now=datetime.now(UTC))
    if (canonical(fresh.binding()) != canonical(candidate.binding())
            or canonical(fresh.decisions) != canonical(candidate.decisions)):
        raise ValueError("Completion authorization changed during actual public-byte readback")
    workflow_context(root, api, policy.PUBLICATION_WORKFLOW, "complete")
    fresh.temporal_proof.assert_current(datetime.now(UTC))
    receipt: JsonObject = {
        "schema_version": "1.0.0", "state": "COMPLETION_OBSERVED", "repository": policy.REPOSITORY,
        "repository_id": policy.REPOSITORY_ID, "binding": candidate.binding(),
        "publication_run_id": run_id, "publication_attempt": attempt, "observed_at": datetime.now(UTC).isoformat(),
        "publication": publication, "gate_observations": policy.required_gate_values(),
        "decisions_sha256": hashlib.sha256(canonical(candidate.decisions)).hexdigest(),
    }
    return receipt


def observe_completion(root: Path, api: GitHubCLI, *, selection: dict[str, int],
                       output: Path, now: datetime) -> JsonObject:
    entered = datetime.now(UTC)
    with collect_time_proof() as proof:
        result = _observe_completion(root, api, selection=selection, now=now)
        raw = canonical(result) + b"\n"
        json_object(raw, "completion receipt")
        proof.assert_current(entered)
        directory = output_directory(root, output)
        proof.assert_current(datetime.now(UTC))
        (directory / MEMBER).write_bytes(raw)
        proof.assert_current(datetime.now(UTC))
        return result


def _receipt(raw: bytes, publication_run_id: int, now: datetime) -> JsonObject:
    receipt = json_object(raw, "completion receipt")
    exact_keys(receipt, RECEIPT_KEYS, "completion receipt")
    if (receipt["schema_version"] != "1.0.0" or receipt["state"] != "COMPLETION_OBSERVED"
            or receipt["repository"] != policy.REPOSITORY
            or integer_value(receipt["repository_id"], "receipt repository") != policy.REPOSITORY_ID
            or integer_value(receipt["publication_run_id"], "publication run") != publication_run_id):
        raise ValueError("Completion receipt identity/state mismatch")
    require_fresh(receipt["observed_at"], now=now, ttl=policy.PREPARED_TTL_SECONDS, label="completion time")
    gates = object_value(receipt["gate_observations"], "observed gates")
    if canonical(gates) != canonical(policy.required_gate_values()):
        raise ValueError("Completion must observe all twelve unchanged canonical gates")
    return receipt


def _verify_completion(root: Path, api: GitHubCLI, *, publication_run_id: int,
                      artifact_id: int, now: datetime) -> JsonObject:
    metadata, digest = archive_identity(api, policy.REPOSITORY, artifact_id)
    if object_value(metadata.get("workflow_run"), "completion artifact run").get("id") != publication_run_id:
        raise ValueError("Selected completion artifact belongs to another producer run")
    archive = api.binary(f"/repos/{policy.REPOSITORY}/actions/artifacts/{artifact_id}/zip",
                         policy.MAX_ARCHIVE_BYTES)
    raw = inspect_result(archive, expected_archive_sha256=digest, member_name=MEMBER)
    receipt = _receipt(raw, publication_run_id, now)
    binding = object_value(receipt["binding"], "completion binding")
    commit = string_value(binding.get("candidate_commit"), "completion candidate")
    attempt = integer_value(receipt["publication_attempt"], "publication attempt")
    authenticate_workflow_artifact(
        api, workflow=policy.PUBLICATION_WORKFLOW, run_id=publication_run_id, run_attempt=attempt,
        artifact_id=artifact_id, archive_sha256=digest, source_commit=commit, now=now,
        required_jobs=frozenset({"authorize", "publish", "complete"}), artifact_name="publication-completion")
    verify_bytes(api, raw, name=MEMBER, repository=policy.REPOSITORY, workflow=policy.PUBLICATION_WORKFLOW,
                 source_commit=commit, source_ref="refs/heads/main", run_id=publication_run_id, run_attempt=attempt)
    selection = {key: integer_value(binding.get(key), key) for key in SELECTION_KEYS}
    candidate = authorize_candidate(root, api, **selection, now=now)
    if (canonical(binding) != canonical(candidate.binding())
            or receipt["decisions_sha256"] != hashlib.sha256(canonical(candidate.decisions)).hexdigest()):
        raise ValueError("Completion authorization was changed or revoked after observation")
    publication = observed_release(api, candidate.bundle)
    if canonical(publication) != canonical(receipt["publication"]):
        raise ValueError("Actual published identities/bytes changed after completion observation")
    fresh = authorize_candidate(root, api, **selection, now=datetime.now(UTC))
    if (canonical(binding) != canonical(fresh.binding())
            or receipt["decisions_sha256"] != hashlib.sha256(canonical(fresh.decisions)).hexdigest()):
        raise ValueError("Completion authorization was revoked during actual public-byte readback")
    fresh.temporal_proof.assert_current(datetime.now(UTC))
    return {**receipt, "state": "APPROVED", "evidence_state": "Verified",
            "completion_artifact_id": artifact_id, "completion_archive_sha256": digest,
            "distribution_closure": "VERIFIED_PARITY", "publication_allowed": True}


def verify_completion(root: Path, api: GitHubCLI, *, publication_run_id: int,
                      artifact_id: int, now: datetime) -> JsonObject:
    entered = datetime.now(UTC)
    with collect_time_proof() as proof:
        result = _verify_completion(root, api, publication_run_id=publication_run_id,
                                    artifact_id=artifact_id, now=now)
        proof.assert_current(entered)
        proof.assert_current(datetime.now(UTC))
        return result
