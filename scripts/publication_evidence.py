"""Strict detached evidence semantics, deliberately not an authority verifier.

Root separately authenticates all three execution artifacts and decision records.
Live records bind scope, actual normalized observations and redacted provider/app
logs. Independent reproduction binds provider-derived numeric context, the exact
prepared wheel, installed environment and seven actual documented command results.
Capability closures reference those checked observations; community closure adds
real external event identities/counts. Only release-distribution remains pending
in immutable E: the authenticated final consumer derives that closure from actual
tag/assets/attestations outside E, so final=True does not mutate/reapprove E.

All data refs are content-addressed JSON records. Exact raw record shapes are
enforced in publication_evidence_records and publication_benchmark and illustrated
by test_publication_evidence.evidence_package (synthetic test-only data).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from scripts import publication_policy as policy
from scripts.publication_benchmark import benchmark_metrics
from scripts.publication_evidence_records import (
    BOUND,
    EvidenceRecords,
    bound_record,
    live_observations,
    nonnegative,
    object_list,
    observed_time,
    reproduction,
    string_list,
)
from scripts.publication_prerequisites import closure_prerequisites, prerequisites
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    integer_value,
    json_object,
    object_value,
    parse_subject,
    sha_value,
    string_value,
)

ROOT = Path(__file__).resolve().parents[1]


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _reachable(value: object, reader: EvidenceRecords) -> set[str]:
    paths: set[str] = set()
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, dict):
            record = object_value(item, "seal record")
            if set(record) == {"path", "sha256"}:
                path = reader.reference_path(record)
                if path not in paths:
                    paths.add(path)
                    pending.append(reader.values[path])
            else:
                pending.extend(record.values())
    return paths


def _gate_capabilities(value: object, reader: EvidenceRecords, gate: str) -> list[JsonObject]:
    selected: list[JsonObject] = []
    for row in object_list(value, "seal capability closures"):
        if row.get("id") == "release-distribution":
            continue
        gates: set[str] = set()
        for reference in object_list(row.get("evidence_refs"), "sealed capability refs"):
            record = reader.read(reference, kind="capability_closure", keys=BOUND | {
                "id", "status", "execution_gate", "observed_at", "observations"})
            gates.add(string_value(record["execution_gate"], "capability execution gate"))
        if len(gates) != 1 or not gates.issubset(policy.EXECUTION_GATES):
            raise ValueError("capability evidence does not have one canonical execution gate")
        if gate in gates:
            selected.append(row)
    return sorted(selected, key=lambda row: string_value(row.get("id"), "capability ID"))


def execution_seal(
    evidence: JsonObject, records: Mapping[str, bytes], *, gate: str,
    execution_context: JsonObject,
) -> JsonObject:
    """Compute a complete result binding, never authority or a signing oracle.

    An enrolled producer must derive this from its own actual execution outputs,
    NEVER sign a caller-supplied digest. Root supplies actual authenticated numeric
    context and compares the entire producer result using strict canonical JSON.
    Semantic validation plus registered provenance/attestation remain mandatory.
    The inventory hashes exact raw bytes and includes all transitive capability
    proof branches; no pointer/archive/result self-hash is part of this graph.
    """
    sections = {"live_authorized_smokes": "live", "seven_archetype_benchmark": "benchmark",
                "external_reproduction": "external_reproduction"}
    if gate not in sections:
        raise ValueError("execution seal gate is not canonical")
    exact_keys(execution_context, {"repository_id", "owner_id", "actor_id", "run_id", "run_attempt"},
               "authenticated execution context")
    for field, number in execution_context.items():
        integer_value(number, field)
    pointers = _executions(evidence.get("executions"))
    if any(execution_context[key] != pointers[gate][key] for key in ("run_id", "run_attempt")):
        raise ValueError("authenticated execution context does not match its exact pointer")
    section = object_value(evidence.get(sections[gate]), "sealed evidence section")
    if gate == "external_reproduction" and _canonical(section.get("execution")) != _canonical(execution_context):
        raise ValueError("external execution identity was not derived from actual provider context")
    candidate = sha_value(evidence.get("candidate_commit"), 40, "sealed source")
    digest = sha_value(evidence.get("prepared_subject_sha256"), 64, "sealed subject")
    reader = EvidenceRecords(records)
    capabilities = _gate_capabilities(evidence.get("capabilities"), reader, gate)
    body: JsonObject = {"section": section, "capabilities": capabilities}
    paths = _reachable(body, reader)
    body["records"] = [{"path": path, "sha256": hashlib.sha256(records[path]).hexdigest(),
                        "bytes": len(records[path])} for path in sorted(paths)]
    return {"schema_version": "1.0.0", "gate": gate, "candidate_commit": candidate,
            "prepared_subject_sha256": digest, "execution_context": execution_context,
            "evidence_sha256": hashlib.sha256(_canonical(body)).hexdigest()}


def _source_policy() -> tuple[dict[str, JsonObject], dict[str, JsonObject], set[str]]:
    ledger = json_object((ROOT / "evaluation/comparative/capability-parity.json").read_bytes(),
                         "capability policy")
    rows = {str(row["id"]): row for row in object_list(ledger["capabilities"], "source capabilities")
            if row["status"] == "GAP_OPEN"}
    if len(rows) != 10 or "release-distribution" not in rows:
        raise ValueError("publication requires the reviewed ten-capability closure contract")
    contract = json_object((ROOT / "governance/capability-certification.json").read_bytes(),
                           "live certification profiles")
    profiles: dict[str, JsonObject] = {}
    for profile in object_list(contract["profiles"], "live profiles"):
        for capability in string_list(profile["capabilities"], "profile capabilities", nonempty=True):
            if capability in profiles:
                raise ValueError("live capability has multiple source profiles")
            profiles[capability] = profile
    statuses = set(string_list(ledger["allowed_statuses"], "capability statuses", nonempty=True))
    return rows, profiles, statuses - {"GAP_OPEN", "REJECTED_WITH_EVIDENCE"}


def _executions(value: object) -> dict[str, JsonObject]:
    data = object_value(value, "execution pointers")
    exact_keys(data, set(policy.EXECUTION_GATES), "execution pointers")
    executions: dict[str, JsonObject] = {}
    for gate, value in data.items():
        pointer = object_value(value, "execution pointer")
        exact_keys(pointer, {"authority_index", "run_id", "run_attempt", "artifact_id",
                            "artifact_sha256", "member_name", "member_sha256"}, "execution pointer")
        nonnegative(pointer["authority_index"], "authority index")
        for field in ("run_id", "run_attempt", "artifact_id"):
            integer_value(pointer[field], field)
        for field in ("artifact_sha256", "member_sha256"):
            sha_value(pointer[field], 64, field)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\.json",
                        string_value(pointer["member_name"], "result member")) is None:
            raise ValueError("execution result member must be a bounded flat JSON filename")
        executions[gate] = pointer
    return executions


def _community(
    reference: object, reader: EvidenceRecords, subject: JsonObject, digest: str,
    execution_id: str, now: datetime,
) -> None:
    record = bound_record(reference, reader, kind="community_observation", keys={"execution_id",
        "observed_at", "metric", "value", "events"},
        candidate=str(subject["candidate_commit"]), digest=digest)
    if record["execution_id"] != execution_id:
        raise ValueError("community observation does not belong to independent execution")
    observed_time(record["observed_at"], subject, now)
    string_value(record["metric"], "community metric")
    events = object_list(record["events"], "external community events")
    if integer_value(record["value"], "community count") != len(events):
        raise ValueError("community metric does not reconcile to actual event identities")
    seen: set[tuple[int, int, str]] = set()
    for event in events:
        exact_keys(event, {"repository_id", "actor_id", "event_id", "event_type", "url_sha256"},
                   "community event")
        repository = integer_value(event["repository_id"], "community repository")
        actor = integer_value(event["actor_id"], "community actor")
        identity = integer_value(event["event_id"], "community event ID")
        kind = string_value(event["event_type"], "community event type")
        if repository != policy.REPOSITORY_ID or actor in {policy.OWNER_ID, 41898282}:
            raise ValueError("community event is not external use of the primary repository")
        if kind not in {"issue", "discussion", "install", "reproduction"} or (repository, identity, kind) in seen:
            raise ValueError("duplicate or unsupported community event")
        sha_value(event["url_sha256"], 64, "community URL digest")
        seen.add((repository, identity, kind))


def _closure_chronology(
    record: JsonObject, paths: list[str], reader: EvidenceRecords, subject: JsonObject, now: datetime,
) -> None:
    closed = observed_time(record["observed_at"], subject, now)
    for path in paths:
        observation = reader.values[path]
        field = "executed_at" if observation["kind"] in {"reproduction_command", "capability_prerequisite"} else "observed_at"
        if closed < observed_time(observation[field], subject, now):
            raise ValueError("capability closure precedes its actual referenced observations")


def _closure_observations(
    identity: str, record: JsonObject, reader: EvidenceRecords, expected: JsonObject,
    live: dict[str, set[str]], command_paths: set[str], context: str,
    profiles: dict[str, JsonObject], subject: JsonObject, digest: str, now: datetime,
) -> None:
    references = object_list(record["observations"], "capability observations")
    paths = [reader.reference_path(ref) for ref in references]
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate capability observation references")
    if expected["gap_disposition"] == "EXTERNAL_EVIDENCE_REQUIRED":
        if record["execution_gate"] != "live_authorized_smokes" or not set(paths).issubset(live):
            raise ValueError("capability closure is not backed by validated live observation records")
        required = set(string_list(expected.get("required_command_ids"), "required commands"))
        covered = set().union(*(live[path] for path in paths))
        if not required or not required.issubset(covered):
            raise ValueError("live closure omits required actual command/prerequisite observations")
        closure_prerequisites(identity, paths, reader, subject, now)
    elif identity == "documentation-install-success":
        if record["execution_gate"] != "external_reproduction" or set(paths) != command_paths:
            raise ValueError("documentation closure requires the complete independent command results")
    elif identity == "community-infrastructure":
        if record["execution_gate"] != "external_reproduction":
            raise ValueError("community closure requires independent external execution")
        for reference in references:
            _community(reference, reader, subject, digest, context, now)
    else:
        raise ValueError("capability has no reviewed publication evidence contract")
    _closure_chronology(record, paths, reader, subject, now)


def _capabilities(
    value: object, reader: EvidenceRecords, source: dict[str, JsonObject], statuses: set[str],
    live: dict[str, set[str]], command_paths: set[str], context: str,
    profiles: dict[str, JsonObject], subject: JsonObject, digest: str, now: datetime,
) -> None:
    seen: set[str] = set()
    for row in object_list(value, "capability closures"):
        exact_keys(row, {"id", "status", "evidence_refs"}, "capability closure")
        identity = string_value(row["id"], "capability ID")
        if identity not in source or identity in seen:
            raise ValueError("duplicate or unknown capability closure")
        seen.add(identity)
        if identity == "release-distribution":
            if row["status"] != "GAP_OPEN" or row["evidence_refs"] != []:
                raise ValueError("immutable E must leave distribution for authenticated completion")
            continue
        if string_value(row["status"], "capability status") not in statuses:
            raise ValueError("only distribution may remain open before publication")
        paths: set[str] = set()
        for reference in object_list(row["evidence_refs"], "capability evidence refs"):
            path = string_value(reference.get("path"), "closure record path")
            if path in paths:
                raise ValueError("duplicate capability evidence reference")
            paths.add(path)
            record = bound_record(reference, reader, kind="capability_closure", keys={"id", "status",
                "execution_gate", "observed_at", "observations"},
                candidate=str(subject["candidate_commit"]), digest=digest)
            if record["id"] != identity or record["status"] != row["status"]:
                raise ValueError("capability closure record does not match the declared disposition")
            observed_time(record["observed_at"], subject, now)
            _closure_observations(identity, record, reader, source[identity], live, command_paths,
                                  context, profiles, subject, digest, now)
    if seen != set(source):
        raise ValueError("evidence must account for all ten canonical open capabilities")


def checked_evidence(
    raw: bytes, records: Mapping[str, bytes], subject: JsonObject, *,
    subject_sha256: str, now: datetime, final: bool = False,
) -> tuple[JsonObject, EvidenceRecords]:
    """Return semantically checked data and consumed refs, never issuer authority."""
    if not isinstance(final, bool):
        raise ValueError("final selector must be a boolean, never authority data")
    parse_subject(json.dumps(subject, allow_nan=False).encode(), now=now)
    sha_value(subject_sha256, 64, "authenticated subject digest")
    data = json_object(raw, "publication evidence")
    exact_keys(data, {"schema_version", *BOUND, "comparator_commit", "executions", "benchmark",
                      "live", "external_reproduction", "capabilities"}, "publication evidence")
    if (data["schema_version"] != "1.0.0" or data["candidate_commit"] != subject["candidate_commit"]
            or data["prepared_subject_sha256"] != subject_sha256
            or data["comparator_commit"] != policy.COMPARATOR_COMMIT):
        raise ValueError("publication evidence source, subject, comparator or schema mismatch")
    executions = _executions(data["executions"])
    reader = EvidenceRecords(records)
    source, profiles, statuses = _source_policy()
    benchmark_metrics(data["benchmark"], reader, candidate_commit=str(subject["candidate_commit"]), now=now)
    live = live_observations(data["live"], reader, subject, subject_sha256, profiles, now)
    live.update(prerequisites(object_value(data["live"], "live evidence")["prerequisites"],
                              reader, subject, subject_sha256, now))
    commands, context = reproduction(data["external_reproduction"], reader, subject, subject_sha256,
                                     executions["external_reproduction"], now)
    _capabilities(data["capabilities"], reader, source, statuses, live, commands, context,
                  profiles, subject, subject_sha256, now)
    reader.finish()
    return data, reader


def parse_evidence(
    raw: bytes, records: Mapping[str, bytes], subject: JsonObject, *,
    subject_sha256: str, now: datetime, final: bool = False,
) -> JsonObject:
    return checked_evidence(raw, records, subject, subject_sha256=subject_sha256,
                             now=now, final=final)[0]
