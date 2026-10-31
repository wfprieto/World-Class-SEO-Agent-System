"""Inert prerequisite and joint closure evidence, never execution authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from scripts import publication_policy as policy
from scripts.publication_arguments import command_options
from scripts.publication_capability_results import validate_result
from scripts.publication_evidence_records import (
    BOUND,
    EvidenceRecords,
    bound_record,
    object_list,
    observed_time,
    string_list,
)
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    instant,
    integer_value,
    object_value,
    sha_value,
    string_value,
)

_LOCAL = {"browser.install": "render-installable", "render.health": "render-installable",
          "bing.preflight": "bing-indexnow", "indexnow.validate": "bing-indexnow"}
_LOCAL_KEYS = {"capability_id", "command_id", "platform", "job_id", "executed_at", "argv", "exit_code", "result"}
_INSTALL_KEYS = {"installed", "binary_sha256", "browser_version", "output_bytes", "stdout_sha256", "stderr_sha256"}
_REMOTE = {"render-installable": {"render.page", "render.screenshot"}, "bing-indexnow": {"indexnow.submit"}}


@dataclass(frozen=True)
class _Execution:
    command: str
    platform: str
    job: int
    time: datetime
    target: JsonObject | None = None


def _require(condition: bool, message: str = "Prerequisite or joint capability proof is inconsistent") -> None:
    if not condition:
        raise ValueError(message)


def _metadata(row: JsonObject) -> tuple[str, int]:
    platform = string_value(row.get("platform"), "actual platform")
    _require(platform in {"ubuntu", "windows"})
    return platform, integer_value(row.get("job_id"), "actual producer job")


def _install(value: object) -> JsonObject:
    data = object_value(value, "actual browser install result")
    exact_keys(data, _INSTALL_KEYS, "actual browser installation")
    _require(data["installed"] is True)
    for name in ("binary_sha256", "stdout_sha256", "stderr_sha256"):
        sha_value(data[name], 64, name)
    string_value(data["browser_version"], "installed browser version")
    integer_value(data["output_bytes"], "actual installation output bytes")
    return data


def _local_result(row: JsonObject, command: str) -> JsonObject:
    command_options(command, row["argv"])
    _require(type(row["exit_code"]) is int and row["exit_code"] == 0, "Actual prerequisite process did not exit0")
    return _install(row["result"]) if command == "browser.install" else validate_result(command, row["result"])


def _target(command: str, row: JsonObject, data: JsonObject, reader: EvidenceRecords,
            subject: JsonObject) -> JsonObject:
    # Root integrates this module; defer its helper import to avoid an import cycle.
    from scripts.publication_capability_checks import command_target

    return command_target(command, row["argv"], data, row, reader, subject)


def _local(reference: object, reader: EvidenceRecords, subject: JsonObject,
           digest: str, now: datetime) -> _Execution:
    raw = reader.values[reader.reference_path(reference)]
    command = string_value(raw.get("command_id"), "local prerequisite command")
    _require(command in _LOCAL, "Command is not a reviewed local prerequisite")
    extra = {"input_file"} if command == "indexnow.validate" else set()
    row = bound_record(reference, reader, kind="capability_prerequisite", keys=_LOCAL_KEYS | extra,
                       candidate=str(subject["candidate_commit"]), digest=digest)
    _require(row["capability_id"] == _LOCAL[command])
    platform, job = _metadata(row)
    executed = observed_time(row["executed_at"], subject, now)
    data = _local_result(row, command)
    target = _target(command, row, data, reader, subject) if command == "indexnow.validate" else None
    return _Execution(command, platform, job, executed, target)


def prerequisites(value: object, reader: EvidenceRecords, subject: JsonObject,
                  digest: str, now: datetime) -> dict[str, set[str]]:
    references = object_list(value, "local prerequisite references", nonempty=False)
    _require(len(references) <= policy.MAX_RECORDS)
    sha_value(digest, 64, "authenticated prepared subject digest")
    covered: dict[str, set[str]] = {}
    for reference in references:
        path = reader.reference_path(reference)
        _require(path not in covered, "Duplicate prerequisite reference")
        entry = _local(reference, reader, subject, digest, now)
        covered[path] = {entry.command}
    return covered


def _path_reference(path: str) -> JsonObject:
    return {"path": path, "sha256": path.rsplit("/", 1)[-1][:-5]}


def _consumed(reference: object, reader: EvidenceRecords, kind: str | None = None) -> JsonObject:
    path = reader.reference_path(reference)
    row = reader.values[path]
    _require(path in reader.used, "Row was not consumed by the actual evidence validation")
    _require(kind is None or row.get("kind") == kind, "Evidence has the wrong record kind")
    return row


def _outcomes(row: JsonObject, reader: EvidenceRecords) -> tuple[JsonObject, JsonObject]:
    _require(row.get("mode") == "AUTHORIZED_LIVE")
    normalized = _consumed(row.get("normalized"), reader, "normalized_observation")
    for field in (*BOUND, "capabilities", "observed_at"):
        _require(normalized.get(field) == row.get(field), "Normalized result belongs to another observation")
    commands = set(string_list(row.get("capabilities"), "actual observed commands", nonempty=True))
    argv = object_value(row.get("argv"), "actual command argv")
    exits = object_value(row.get("exit_codes"), "actual command exits")
    envelopes = object_value(normalized.get("data"), "actual command envelopes")
    for mapping in (argv, exits, envelopes):
        exact_keys(mapping, commands, "actual command mapping")
    data: JsonObject = {}
    for command in sorted(commands):
        command_options(command, argv[command])
        _require(type(exits[command]) is int and exits[command] == 0)
        data[command] = validate_result(command, envelopes[command])
    return normalized, data


def _request_start(normalized: JsonObject, command: str, subject: JsonObject,
                    now: datetime, completed: datetime) -> datetime:
    times = [observed_time(request.get("occurred_at"), subject, now)
             for request in object_list(normalized.get("requests"), "actual command requests")
             if string_value(request.get("command_id"), "actual request command") == command]
    _require(bool(times), "Actual command has no matching request start")
    _require(max(times) <= completed, "Actual request follows its reported observation completion")
    return min(times)


def _live(row: JsonObject, reader: EvidenceRecords, subject: JsonObject,
          now: datetime, identity: str) -> list[_Execution]:
    normalized, data = _outcomes(row, reader)
    _require(set(data).issubset(_REMOTE[identity]), "Closure references unrelated remote commands")
    platform, job = _metadata(row)
    observed = observed_time(row["observed_at"], subject, now)
    argv = object_value(row["argv"], "actual argv")
    entries = []
    for command, result in data.items():
        concrete = {**row, "argv": argv[command]}
        target = _target(command, concrete, object_value(result, "actual result data"), reader, subject)
        started = _request_start(normalized, command, subject, now, observed)
        entries.append(_Execution(command, platform, job, started, target))
    return entries


def _closure_rows(identity: str, paths: list[str], reader: EvidenceRecords,
                  subject: JsonObject, now: datetime) -> list[_Execution]:
    entries: list[_Execution] = []
    digests: set[str] = set()
    for path in string_list(paths, "joint closure paths", nonempty=True):
        reference = _path_reference(path)
        row = _consumed(reference, reader)
        _require(row.get("candidate_commit") == subject["candidate_commit"])
        digest = sha_value(row.get("prepared_subject_sha256"), 64, "previously validated subject digest")
        digests.add(digest)
        if row.get("kind") == "capability_prerequisite":
            _require(row.get("capability_id") == identity)
            entries.append(_local(reference, reader, subject, digest, now))
        else:
            _require(row.get("kind") == "live_observation")
            entries.extend(_live(row, reader, subject, now, identity))
    _require(len(digests) == 1, "Closure joins observations of different prepared subjects")
    return entries


def _local_uniqueness(entries: list[_Execution]) -> None:
    keys = [(row.command, row.platform) for row in entries if row.command in _LOCAL]
    _require(len(keys) == len(set(keys)), "Ambiguous duplicate local prerequisites")


def _render(entries: list[_Execution]) -> None:
    jobs = set()
    for platform in ("ubuntu", "windows"):
        rows = [row for row in entries if row.platform == platform]
        _require({row.command for row in rows} == {"browser.install", "render.health", "render.page", "render.screenshot"})
        group_jobs = {row.job for row in rows}
        _require(len(group_jobs) == 1, "Render install, health and smokes must share one actual platform job")
        jobs.update(group_jobs)
        install = next(row.time for row in rows if row.command == "browser.install")
        health = next(row.time for row in rows if row.command == "render.health")
        _require(install <= health and all(health <= row.time for row in rows if row.command.startswith("render.")))
    _require(len(jobs) == 2, "Windows and Ubuntu cannot reuse one actual job ID")


def _bing(entries: list[_Execution]) -> None:
    _require({row.command for row in entries} == {"bing.preflight", "indexnow.validate", "indexnow.submit"})
    submitted = [row for row in entries if row.command == "indexnow.submit"]
    checks = [row for row in entries if row.command != "indexnow.submit"]
    _require(max(row.time for row in checks) <= min(row.time for row in submitted), "Bing setup follows an actual submission")
    targets = [row.target for row in entries if row.command.startswith("indexnow.")]
    _require(bool(targets) and all(target is not None and target == targets[0] for target in targets),
             "IndexNow validation and actual submissions used different captured URL sets")


def closure_prerequisites(identity: str, paths: list[str], reader: EvidenceRecords,
                          subject: JsonObject, now: datetime) -> None:
    if identity not in _REMOTE:
        return
    entries = _closure_rows(identity, paths, reader, subject, now)
    _local_uniqueness(entries)
    (_render if identity == "render-installable" else _bing)(entries)


def _claim(row: JsonObject, value: object) -> JsonObject:
    platform, job = _metadata(row)
    instant(value, "actual job-bound event time")
    return {"job_id": job, "platform": platform, "executed_at": value}


def _claim_context(row: JsonObject, section: JsonObject) -> None:
    _require(all(row.get(field) == section[field] for field in BOUND),
             "Claimed event is bound to another live source or prepared subject")


def _observation_claims(row: JsonObject, reader: EvidenceRecords) -> list[JsonObject]:
    normalized, _data = _outcomes(row, reader)
    claims = [_claim(row, row.get("observed_at"))]
    for request in object_list(normalized.get("requests"), "actual job requests"):
        claims.append(_claim(row, request.get("occurred_at")))
    return claims


def _prerequisite_claim(row: JsonObject) -> JsonObject:
    command = string_value(row.get("command_id"), "actual prerequisite command")
    _require(command in _LOCAL)
    keys = _LOCAL_KEYS | BOUND | {"kind"}
    exact_keys(row, keys | ({"input_file"} if command == "indexnow.validate" else set()), "local prerequisite")
    _require(row["capability_id"] == _LOCAL[command])
    _local_result(row, command)
    return _claim(row, row.get("executed_at"))


def job_claims(live: object, reader: EvidenceRecords) -> list[JsonObject]:
    section = object_value(live, "already validated live evidence")
    sha_value(section.get("candidate_commit"), 40, "validated candidate")
    sha_value(section.get("prepared_subject_sha256"), 64, "validated prepared subject")
    _require(section.get("mode") == "AUTHORIZED_LIVE")
    claims: list[JsonObject] = []
    seen: set[str] = set()
    for reference in object_list(section.get("observations"), "validated observations", nonempty=False):
        path = reader.reference_path(reference)
        _require(path not in seen, "Duplicate observed job reference")
        seen.add(path)
        row = _consumed(reference, reader, "live_observation")
        _claim_context(row, section)
        claims.extend(_observation_claims(row, reader))
    for reference in object_list(section.get("prerequisites"), "validated prerequisites", nonempty=False):
        path = reader.reference_path(reference)
        _require(path not in seen, "Duplicate prerequisite job reference")
        seen.add(path)
        row = _consumed(reference, reader, "capability_prerequisite")
        _claim_context(row, section)
        claims.append(_prerequisite_claim(row))
    platforms: dict[int, str] = {}
    for claim in claims:
        job = integer_value(claim["job_id"], "actual job")
        _require(job not in platforms or platforms[job] == claim["platform"], "One job ID cannot claim both platforms")
        platforms[job] = str(claim["platform"])
    return claims
