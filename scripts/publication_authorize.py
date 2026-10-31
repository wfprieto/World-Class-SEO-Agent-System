"""Authenticate prepared bytes, immutable data-only E and real execution/role decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts import publication_policy as policy
from scripts.publication_artifacts import unpack_result
from scripts.publication_bundle import CandidateBundle, download_candidate, verify_bytes
from scripts.publication_evidence import checked_evidence, execution_seal
from scripts.publication_freshness import TemporalProof, collect_time_proof
from scripts.publication_git import git, read_evidence
from scripts.publication_jobs import authenticate_jobs
from scripts.publication_prerequisites import job_claims
from scripts.publication_provider import authenticate_decisions, authenticate_execution
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    integer_value,
    json_object,
    object_value,
    sha_value,
    string_value,
)
from scripts.publication_transport import GitHubCLI


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def execution_authorities(root: Path) -> dict[str, list[JsonObject]]:
    registry = json_object((root / "governance/publication-execution-authorities.json").read_bytes(),
                           "execution authorities")
    exact_keys(registry, {"schema_version", "repository_id", "authorities"}, "execution registry")
    if (registry["schema_version"] != "1.0.0"
            or integer_value(registry["repository_id"], "registry repository") != policy.REPOSITORY_ID):
        raise ValueError("Execution authority registry identity mismatch")
    authorities = object_value(registry["authorities"], "execution authorities")
    exact_keys(authorities, set(policy.EXECUTION_GATES), "execution authorities")
    result: dict[str, list[JsonObject]] = {}
    for gate, entries in authorities.items():
        if not isinstance(entries, list) or len(entries) > policy.MAX_RECORDS:
            raise ValueError("Execution authorities must be bounded explicit allowlists")
        result[gate] = [object_value(entry, "execution authority") for entry in entries]
    return result


@dataclass(frozen=True)
class AuthorizedCandidate:
    bundle: CandidateBundle
    evidence_pr: int
    evidence_commit: str
    evidence_sha256: str
    owner_comment_id: int
    evidence: JsonObject
    decisions: JsonObject
    temporal_proof: TemporalProof

    def selection(self) -> dict[str, int]:
        return {"prepare_run_id": integer_value(self.bundle.subject["prepare_run_id"], "preparation"),
                "artifact_id": self.bundle.artifact_id, "evidence_pr": self.evidence_pr,
                "owner_comment_id": self.owner_comment_id}

    def binding(self) -> JsonObject:
        subject = self.bundle.subject
        return {**self.selection(), "candidate_commit": subject["candidate_commit"],
                "candidate_tree": subject["candidate_tree"], "planned_tag": subject["planned_tag"],
                "evidence_commit": self.evidence_commit, "evidence_sha256": self.evidence_sha256,
                "subject_sha256": self.bundle.subject_sha256,
                "archive_sha256": self.bundle.archive_sha256,
                "ci_run_id": subject["ci_run_id"], "ci_attempt": subject["ci_attempt"],
                "prepare_attempt": subject["prepare_attempt"]}


def _execution_context(receipt: JsonObject) -> JsonObject:
    run = object_value(receipt.get("run"), "execution run")
    repository = object_value(run.get("repository"), "execution repository")
    owner = object_value(repository.get("owner"), "execution owner")
    actor = object_value(run.get("actor"), "execution actor")
    return {"repository_id": integer_value(repository.get("id"), "execution repository"),
            "owner_id": integer_value(owner.get("id"), "execution owner"),
            "actor_id": integer_value(actor.get("id"), "execution actor"),
            "run_id": integer_value(run.get("id"), "execution run"),
            "run_attempt": integer_value(run.get("run_attempt"), "execution attempt")}


def _authenticate_executions(
    api: GitHubCLI, evidence: JsonObject, records: dict[str, bytes], bundle: CandidateBundle,
    authorities: dict[str, list[JsonObject]], now: datetime,
    *, live_claims: list[JsonObject],
) -> None:
    pointers = object_value(evidence["executions"], "execution pointers")
    for gate in sorted(policy.EXECUTION_GATES):
        pointer = object_value(pointers[gate], "execution pointer")
        index = pointer["authority_index"]
        if type(index) is not int or not 0 <= index < len(authorities[gate]):
            raise ValueError(f"No enrolled real execution authority for {gate}")
        authority = authorities[gate][index]
        repository = string_value(authority["repository"], "producer repository")
        producer = api.for_execution(gate, repository)
        receipt = authenticate_execution(producer, pointer=pointer, authority=authority,
                                         subject=bundle.subject, now=now)
        artifact_id = integer_value(pointer["artifact_id"], "execution artifact")
        archive = producer.binary(f"/repos/{repository}/actions/artifacts/{artifact_id}/zip",
                             policy.MAX_ARCHIVE_BYTES)
        member = string_value(pointer["member_name"], "execution result")
        raw = unpack_result(archive, expected_archive_sha256=str(pointer["artifact_sha256"]),
                            member_name=member, member_sha256=str(pointer["member_sha256"]))
        verify_bytes(producer, raw, name=member, repository=repository,
                     workflow=string_value(authority["workflow"], "producer workflow"),
                     source_commit=string_value(authority["source_commit"], "producer source"),
                     source_ref=string_value(authority["source_ref"], "producer ref"),
                     run_id=integer_value(pointer["run_id"], "producer run"),
                     run_attempt=integer_value(pointer["run_attempt"], "producer attempt"))
        expected = execution_seal(evidence, records, gate=gate,
                                  execution_context=_execution_context(receipt))
        if canonical(json_object(raw, "authenticated execution seal")) != canonical(expected):
            raise ValueError("Authenticated execution does not seal these exact evidence bytes/context")
        if gate == "live_authorized_smokes":
            authenticate_jobs(producer, receipt=receipt, claims=live_claims, now=now)


def _authorize_candidate(
    root: Path, api: GitHubCLI, *, prepare_run_id: int, artifact_id: int,
    evidence_pr: int, owner_comment_id: int, now: datetime, temporal_proof: TemporalProof,
) -> AuthorizedCandidate:
    for value in (prepare_run_id, artifact_id, evidence_pr, owner_comment_id):
        integer_value(value, "publication selection")
    authorities = execution_authorities(root)
    missing = sorted(gate for gate, entries in authorities.items() if not entries)
    if missing:
        raise ValueError("Missing enrolled real execution authorities: " + ", ".join(missing))
    bundle = download_candidate(api, prepare_run_id=prepare_run_id, artifact_id=artifact_id, now=now)
    commit = string_value(bundle.subject["candidate_commit"], "candidate")
    if git(root, "rev-parse", "HEAD").decode().strip() != commit:
        raise ValueError("Authorization source is not the exact prepared main commit")
    pr = object_value(api.json(f"/repos/{policy.REPOSITORY}/pulls/{evidence_pr}"), "evidence PR")
    evidence_commit = sha_value(object_value(pr.get("head"), "evidence head").get("sha"), 40, "E")
    git(root, "-c", "core.hooksPath=", "fetch", "--no-tags", "--no-write-fetch-head",
        f"https://github.com/{policy.REPOSITORY}.git", evidence_commit)
    raw, records, digest = read_evidence(root, commit, evidence_commit)
    evidence, reader = checked_evidence(raw, records, bundle.subject,
                                         subject_sha256=bundle.subject_sha256, now=now)
    claims = job_claims(evidence["live"], reader)
    _authenticate_executions(api, evidence, records, bundle, authorities, now, live_claims=claims)
    decisions = authenticate_decisions(api, bundle.subject, evidence_pr=evidence_pr,
                                       evidence_commit=evidence_commit, evidence_sha256=digest,
                                       artifact_id=artifact_id, archive_sha256=bundle.archive_sha256,
                                       subject_sha256=bundle.subject_sha256,
                                       owner_comment_id=owner_comment_id, now=now)
    return AuthorizedCandidate(bundle, evidence_pr, evidence_commit, digest, owner_comment_id,
                               evidence, decisions, temporal_proof)


def authorize_candidate(
    root: Path, api: GitHubCLI, *, prepare_run_id: int, artifact_id: int,
    evidence_pr: int, owner_comment_id: int, now: datetime,
) -> AuthorizedCandidate:
    entered = datetime.now(UTC)
    with collect_time_proof() as proof:
        result = _authorize_candidate(root, api, prepare_run_id=prepare_run_id, artifact_id=artifact_id,
                                       evidence_pr=evidence_pr, owner_comment_id=owner_comment_id,
                                       now=now, temporal_proof=proof)
        proof.assert_current(entered)
        proof.assert_current(datetime.now(UTC))
        return result
