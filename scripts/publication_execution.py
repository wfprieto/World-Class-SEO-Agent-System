"""Authenticate execution origins selected from the protected source registry."""

from __future__ import annotations

import re
from datetime import datetime

from scripts import publication_policy as policy
from scripts.publication_provider import (
    JsonObject,
    PublicationAPI,
    artifact_attempt,
    authenticate_artifact,
    authenticate_run,
    integer_value,
    read_object,
    repository_identity,
    text_value,
)

AUTHORITY_KEYS = {"repository", "repository_id", "owner_id", "actor_id", "workflow",
                  "source_commit", "source_ref", "independent"}
POINTER_KEYS = {"authority_index", "run_id", "run_attempt", "artifact_id",
                "artifact_sha256", "member_name", "member_sha256"}


def _registered_repository(value: object) -> str:
    repository = text_value(value, "registered repository")
    parts = repository.split("/")
    if (len(parts) != 2 or any(part in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
                              for part in parts)):
        raise ValueError("registered repository path is unsafe")
    return repository


def _registry_entry(authority: JsonObject) -> tuple[str, str, str]:
    if set(authority) != AUTHORITY_KEYS or type(authority.get("independent")) is not bool:
        raise ValueError("registered execution authority contract mismatch")
    repository = _registered_repository(authority.get("repository"))
    workflow = text_value(authority.get("workflow"), "registered workflow")
    if re.fullmatch(r"\.github/workflows/[A-Za-z0-9_-]+\.ya?ml", workflow) is None:
        raise ValueError("registered executable workflow path is unsafe")
    source = text_value(authority.get("source_commit"), "registered source")
    source_ref = text_value(authority.get("source_ref"), "registered source ref")
    if (re.fullmatch(r"[0-9a-f]{40}", source) is None
            or re.fullmatch(r"refs/(heads|tags)/[A-Za-z0-9_./-]+", source_ref) is None
            or any(part in {".", "..", ""} for part in source_ref.split("/"))):
        raise ValueError("registered executable commit/ref is invalid")
    for key in ("repository_id", "owner_id", "actor_id"):
        integer_value(authority.get(key), key)
    if authority["independent"] and (authority["repository_id"] == policy.REPOSITORY_ID
                                     or authority["owner_id"] == policy.OWNER_ID
                                     or authority["actor_id"] == policy.OWNER_ID):
        raise ValueError("independent reproduction cannot use primary builder identities")
    return repository, workflow, source_ref.split("/", 2)[2]


def _pointer(pointer: JsonObject) -> None:
    index = pointer.get("authority_index")
    if (set(pointer) != POINTER_KEYS or not isinstance(index, int)
            or isinstance(index, bool) or index < 0):
        raise ValueError("execution pointer contract mismatch")
    for key in ("run_id", "run_attempt", "artifact_id"):
        integer_value(pointer.get(key), key)
    for key in ("artifact_sha256", "member_sha256"):
        if re.fullmatch(r"[0-9a-f]{64}", text_value(pointer.get(key), key)) is None:
            raise ValueError("execution pointer requires exact SHA256")
    name = text_value(pointer.get("member_name"), "execution result member")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.json", name) is None:
        raise ValueError("execution result member must be a safe flat JSON filename")


def authenticate_execution(
    api: PublicationAPI, *, pointer: JsonObject, authority: JsonObject,
    subject: JsonObject, now: datetime,
) -> JsonObject:
    _pointer(pointer)
    repository, workflow, branch = _registry_entry(authority)
    repository_id = integer_value(authority.get("repository_id"), "registered repository")
    owner_id = integer_value(authority.get("owner_id"), "registered owner")
    actor_id = integer_value(authority.get("actor_id"), "registered actor")
    source = text_value(authority.get("source_commit"), "registered source")
    prefix = f"/repos/{repository}"
    repository_identity(read_object(api, prefix), repository, repository_id, owner_id)
    descriptor = read_object(api, prefix + f"/actions/workflows/{workflow.split('/')[-1]}")
    if descriptor.get("path") != workflow or descriptor.get("state") != "active":
        raise ValueError("registered producer workflow identity mismatch")
    run_id = integer_value(pointer.get("run_id"), "execution run")
    attempt = integer_value(pointer.get("run_attempt"), "execution attempt")
    run = authenticate_run(api, repository=repository, repository_id=repository_id,
                           owner_id=owner_id, workflow_id=integer_value(descriptor.get("id"), "workflow"),
                           workflow=workflow, run_id=run_id, attempt=attempt, commit=source,
                           branch=branch, event=None, now=now, ttl=policy.EVIDENCE_TTL_SECONDS,
                           actor_id=actor_id)
    artifact = authenticate_artifact(
        api, repository=repository, repository_id=repository_id, run_id=run_id,
        artifact_id=integer_value(pointer.get("artifact_id"), "execution artifact"),
        archive_sha256=text_value(pointer.get("artifact_sha256"), "archive digest"),
        source_commit=source, now=now, ttl=policy.EVIDENCE_TTL_SECONDS)
    artifact_attempt(artifact, run)
    return {"candidate_commit": subject.get("candidate_commit"), "producer_commit": source,
            "execution_context": f"github:{repository_id}:run:{run_id}:attempt:{attempt}",
            "independent": authority["independent"], "run": run, "artifact": artifact,
            "member_name": pointer["member_name"], "member_sha256": pointer["member_sha256"]}
