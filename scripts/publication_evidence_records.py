"""Bounded content-addressed evidence records, not execution authentication.

Every reference has exactly path/sha256. Paths are flat JSON records under
publication-evidence/records, named by the SHA256 of the exact supplied bytes.
Consumers enforce each record kind's exact schema and finish rejects unused data.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from datetime import datetime

from scripts import publication_policy as policy
from scripts.publication_subject import (
    JsonObject,
    exact_keys,
    instant,
    integer_value,
    json_object,
    object_value,
    require_fresh,
    sha_value,
    string_value,
    subject_files,
)

BOUND = {"candidate_commit", "prepared_subject_sha256"}


def string_list(
    value: object, label: str, *, nonempty: bool = False, unique: bool = True,
) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{label} must be a list")
    values = [string_value(item, label) for item in value]
    if unique and len(values) != len(set(values)):
        raise ValueError(f"{label} must not contain duplicates")
    return values


def object_list(value: object, label: str, *, nonempty: bool = True) -> list[JsonObject]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{label} must contain object records")
    return [object_value(item, label) for item in value]


class EvidenceRecords:
    """Integrity-checked bounded records. This class grants no issuer authority."""

    def __init__(self, records: Mapping[str, bytes]) -> None:
        if len(records) > policy.MAX_RECORDS:
            raise ValueError("evidence record count exceeds the cap")
        self.values: dict[str, JsonObject] = {}
        self.used: set[str] = set()
        total = 0
        for path, raw in records.items():
            if not isinstance(path, str) or re.fullmatch(
                r"publication-evidence/records/[0-9a-f]{64}\.json", path
            ) is None:
                raise ValueError("record path must be a normalized content-addressed JSON path")
            if not isinstance(raw, bytes) or not 0 < len(raw) <= policy.MAX_RECORD_BYTES:
                raise ValueError("evidence record exceeds the byte cap")
            total += len(raw)
            if total > policy.MAX_EVIDENCE_BYTES:
                raise ValueError("evidence exceeds the total byte cap")
            digest = path.rsplit("/", 1)[-1][:-5]
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("record content does not match its path digest")
            self.values[path] = json_object(raw, "evidence record")

    def reference_path(self, value: object) -> str:
        """Validate the complete reference, including paths already seen elsewhere."""
        reference = object_value(value, "evidence reference")
        exact_keys(reference, {"path", "sha256"}, "evidence reference")
        path = string_value(reference["path"], "evidence path")
        if path not in self.values or reference["sha256"] != path.rsplit("/", 1)[-1][:-5]:
            raise ValueError("evidence reference is missing or has the wrong digest")
        return path

    def read(self, value: object, *, kind: str, keys: set[str]) -> JsonObject:
        path = self.reference_path(value)
        record = self.values[path]
        exact_keys(record, keys | {"kind"}, kind)
        if record["kind"] != kind:
            raise ValueError("evidence reference has the wrong record kind")
        self.used.add(path)
        return record

    def finish(self) -> None:
        if self.used != set(self.values):
            raise ValueError("unused or unreferenced evidence records are forbidden")


def nonnegative(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a nonnegative integer")
    return value


def bound_record(
    reference: object, reader: EvidenceRecords, *, kind: str, keys: set[str],
    candidate: str, digest: str,
) -> JsonObject:
    record = reader.read(reference, kind=kind, keys=keys | BOUND)
    if record["candidate_commit"] != candidate or record["prepared_subject_sha256"] != digest:
        raise ValueError("evidence record is bound to another source or prepared subject")
    return record


def observed_time(value: object, subject: JsonObject, now: datetime) -> datetime:
    observed = require_fresh(value, now=now, ttl=policy.EVIDENCE_TTL_SECONDS, label="observed_at")
    if observed < instant(subject["prepared_at"], "prepared_at"):
        raise ValueError("evidence observation predates its prepared subject")
    return observed


def _live_log(
    reference: object, reader: EvidenceRecords, observation: JsonObject, subject: JsonObject,
    role: str, now: datetime, normalized: JsonObject,
) -> None:
    record = bound_record(reference, reader, kind="live_log", keys={"role", "request_id",
        "observed_at", "source_sha256", "redacted", "events", "request_ids"},
        candidate=str(subject["candidate_commit"]), digest=str(observation["prepared_subject_sha256"]))
    if (record["role"] != role or record["request_id"] != observation["request_id"]
            or record["redacted"] is not True):
        raise ValueError("live log identity or redaction mismatch")
    sha_value(record["source_sha256"], 64, "log source digest")
    string_list(record["events"], "redacted live events", nonempty=True)
    actual = set(string_list(record["request_ids"], "logged actual request IDs", nonempty=True))
    expected = {string_value(row["request_id"], "actual request ID") for row in
                object_list(normalized["requests"], "actual requests")}
    if actual != expected:
        raise ValueError("Provider/application log does not reconcile to actual request identities")
    observed_time(record["observed_at"], subject, now)


def _profile_consent(authorization: JsonObject, normalized: JsonObject, profile: JsonObject) -> None:
    consent = object_value(profile["live_authorization"], "profile live authorization")
    if consent["cost_approval_required"] and authorization["cost_approved"] is not True:
        raise ValueError("profile requires explicit cost approval")
    if consent["write_approval_required"] and authorization["write_approved"] is not True:
        raise ValueError("profile requires explicit write approval")
    if profile["side_effect"] == "write" and normalized["write_performed"] is not True:
        raise ValueError("write profile requires an actual write observation")
    if profile["side_effect"] == "read_only" and (
        authorization["write_approved"] is not False or normalized["write_performed"] is not False
    ):
        raise ValueError("read-only profile cannot grant or perform writes")


def _live_consent(authorization: JsonObject, normalized: JsonObject, profiles: list[JsonObject]) -> None:
    for field in ("cost_approved", "write_approved"):
        if not isinstance(authorization[field], bool):
            raise ValueError("live consent must be explicit boolean values")
    if not isinstance(normalized["write_performed"], bool):
        raise ValueError("actual write state must be a boolean")
    if nonnegative(normalized["cost_micros"], "actual cost") and authorization["cost_approved"] is not True:
        raise ValueError("actual paid calls require explicit cost approval")
    for profile in profiles:
        _profile_consent(authorization, normalized, profile)


def _live_budget(
    reference: object, authorization: JsonObject, normalized: JsonObject,
    usage: dict[str, tuple[int, int]],
) -> None:
    path = string_value(object_value(reference, "live scope reference")["path"], "scope path")
    requests, cost = usage.get(path, (0, 0))
    requests += integer_value(normalized["requests_made"], "actual requests")
    cost += nonnegative(normalized["cost_micros"], "actual cost")
    if requests > integer_value(authorization["max_requests"], "request budget") or cost > nonnegative(
        authorization["max_cost_micros"], "cost budget"
    ):
        raise ValueError("live observations exceed their cumulative authorized request or cost budget")
    usage[path] = requests, cost


def _live_scope(
    observation: JsonObject, reader: EvidenceRecords, profiles: list[JsonObject],
    subject: JsonObject, now: datetime, usage: dict[str, tuple[int, int]],
) -> JsonObject:
    from scripts.publication_capability_checks import validate_observation

    candidate, digest = str(subject["candidate_commit"]), str(observation["prepared_subject_sha256"])
    authorization = bound_record(observation["authorization"], reader, kind="live_authorization",
        keys={"target_sha256", "scope_sha256", "owner_actor_id", "starts_at", "expires_at",
              "max_requests", "max_cost_micros", "cost_approved", "write_approved", "target", "scope"},
        candidate=candidate, digest=digest)
    normalized = bound_record(observation["normalized"], reader, kind="normalized_observation",
        keys={"capabilities", "provider_id", "request_id", "target_sha256", "observed_at",
              "requests_made", "cost_micros", "write_performed", "data", "target", "requests"},
        candidate=candidate, digest=digest)
    for field in ("capabilities", "provider_id", "request_id", "observed_at"):
        if normalized[field] != observation[field]:
            raise ValueError("normalized provider result does not match its observation")
    for field in ("target_sha256", "scope_sha256"):
        sha_value(authorization[field], 64, field)
    integer_value(authorization["owner_actor_id"], "scope owner")
    observed = observed_time(observation["observed_at"], subject, now)
    start, end = instant(authorization["starts_at"], "scope start"), instant(authorization["expires_at"], "scope end")
    if not start <= observed < end or (end - start).total_seconds() > policy.EVIDENCE_TTL_SECONDS:
        raise ValueError("live observation is outside its bounded authorization window")
    if normalized["target_sha256"] != authorization["target_sha256"]:
        raise ValueError("live target is outside its authorized scope")
    if not object_value(normalized["data"], "normalized provider data"):
        raise ValueError("live success requires normalized provider observations")
    _live_consent(authorization, normalized, profiles)
    validate_observation(observation, normalized, authorization, reader, subject, now)
    _live_budget(observation["authorization"], authorization, normalized, usage)
    return normalized


def _unique_actual_requests(normalized: JsonObject, seen: set[str]) -> None:
    for row in object_list(normalized["requests"], "actual requests"):
        identity = string_value(row["request_id"], "actual request ID")
        if identity in seen:
            raise ValueError("Duplicate actual request identity across the execution run")
        seen.add(identity)


def live_observations(
    value: object, reader: EvidenceRecords, subject: JsonObject, digest: str,
    profiles: dict[str, JsonObject], now: datetime,
) -> dict[str, set[str]]:
    data = object_value(value, "live evidence")
    exact_keys(data, BOUND | {"mode", "observations", "prerequisites"}, "live evidence")
    if (data["candidate_commit"] != subject["candidate_commit"]
            or data["prepared_subject_sha256"] != digest or data["mode"] != "AUTHORIZED_LIVE"):
        raise ValueError("live evidence is not bound authorized observation mode")
    observed: dict[str, set[str]] = {}
    request_ids: set[tuple[str, str]] = set()
    actual_ids: set[str] = set()
    usage: dict[str, tuple[int, int]] = {}
    for reference in object_list(data["observations"], "live observations"):
        raw = reader.values[reader.reference_path(reference)]
        commands = set(string_list(raw.get("capabilities"), "live capability IDs", nonempty=True))
        record = bound_record(reference, reader, kind="live_observation", keys={"mode",
            "capabilities", "provider_id", "request_id", "observed_at", "authorization",
            "normalized", "provider_log", "application_log", "platform", "job_id", "argv", "exit_codes"}
            | ({"input_file"} if "indexnow.submit" in commands else set()),
            candidate=str(subject["candidate_commit"]), digest=digest)
        if record["mode"] != "AUTHORIZED_LIVE" or not commands.issubset(profiles):
            raise ValueError("live observation mode or capability is not canonical")
        provider = string_value(record["provider_id"], "provider ID")
        request = string_value(record["request_id"], "request ID")
        if (provider, request) in request_ids or any(profiles[key]["provider_id"] != provider for key in commands):
            raise ValueError("duplicate live request or misbound provider")
        request_ids.add((provider, request))
        normalized = _live_scope(record, reader, [profiles[key] for key in commands], subject, now, usage)
        _unique_actual_requests(normalized, actual_ids)
        for role in ("provider", "application"):
            _live_log(record[f"{role}_log"], reader, record, subject, role, now, normalized)
        path = string_value(reference["path"], "observation path")
        if path in observed:
            raise ValueError("duplicate live observation reference")
        observed[path] = commands
    return observed


COMMAND_ARGUMENTS = {
    "cli_help": ["--help"], "registry": ["--registry-check"],
    "integrations": ["integrations", "list"], "knowledge": ["knowledge", "validate"],
    "doctor": ["system", "doctor"], "humanize": ["content", "humanize"],
    "technical_fixture": ["audit", "technical"],
}


def _command_arguments(value: object, command_id: str) -> None:
    argv = string_list(value, "command argv", nonempty=True, unique=False)
    executable = argv[0].replace("\\", "/").rsplit("/", 1)[-1]
    if re.fullmatch(r"python(?:3(?:\.[0-9]+)?)?(?:\.exe)?", executable) is None:
        raise ValueError("external reproduction must execute Python directly")
    prefix = ["-m", "seoctl", *COMMAND_ARGUMENTS[command_id]]
    if argv[1:1 + len(prefix)] != prefix:
        raise ValueError("reproduction command identity does not match its actual argv")
    remaining = argv[1 + len(prefix):]
    if command_id in {"humanize", "technical_fixture"}:
        required = {"--input", "--output"} if command_id == "humanize" else {
            "--url", "--fixture", "--output", "--max-urls"}
        if len(remaining) != len(required) * 2 or set(remaining[::2]) != required:
            raise ValueError("reproduction command options are incomplete or unexpected")
        if command_id == "technical_fixture":
            options = dict(zip(remaining[::2], remaining[1::2], strict=True))
            if options["--url"] != "https://example.com/" or options["--max-urls"] != "20":
                raise ValueError("documented technical fixture bounds changed")
    elif remaining:
        raise ValueError("reproduction command may not override documented behavior or dates")


def _reproduction_context(value: object, pointer: JsonObject) -> JsonObject:
    context = object_value(value, "reproducer execution")
    exact_keys(context, {"repository_id", "owner_id", "actor_id", "run_id", "run_attempt"},
               "reproducer execution")
    for field in context:
        integer_value(context[field], field)
    if (context["repository_id"] == policy.REPOSITORY_ID or context["owner_id"] == policy.OWNER_ID
            or context["actor_id"] in {policy.OWNER_ID, 41898282}
            or context["run_id"] != pointer["run_id"] or context["run_attempt"] != pointer["run_attempt"]):
        raise ValueError("reproduction requires a distinct provider execution context")
    return context


def _reproduction_environment(
    data: JsonObject, reader: EvidenceRecords, subject: JsonObject, digest: str,
    pointer: JsonObject, now: datetime,
) -> tuple[str, str, datetime]:
    context = _reproduction_context(data["execution"], pointer)
    execution_id = f"github:{context['repository_id']}:run:{context['run_id']}:attempt:{context['run_attempt']}"
    wheel = next(row for row in subject_files(subject).values() if row["role"] == "wheel")
    if data["wheel_sha256"] != wheel["sha256"]:
        raise ValueError("external reproduction used another wheel")
    environment = bound_record(data["environment"], reader, kind="reproduction_environment", keys={
        *context, "execution_id", "outside_source", "python_version", "os", "created_at",
        "installed_wheel_sha256"}, candidate=str(subject["candidate_commit"]), digest=digest)
    for field in context:
        integer_value(environment[field], f"environment {field}")
    if any(environment[key] != number for key, number in context.items()) or (
        environment["execution_id"] != execution_id or environment["outside_source"] is not True
        or environment["installed_wheel_sha256"] != wheel["sha256"]
    ):
        raise ValueError("external installed environment identity mismatch")
    if re.fullmatch(r"3\.(?:11|12|13)\.[0-9]+", string_value(environment["python_version"], "Python")) is None:
        raise ValueError("external reproduction interpreter is not supported")
    string_value(environment["os"], "external operating system")
    created = observed_time(environment["created_at"], subject, now)
    return execution_id, str(wheel["sha256"]), created


def reproduction(
    value: object, reader: EvidenceRecords, subject: JsonObject, digest: str,
    pointer: JsonObject, now: datetime,
) -> tuple[set[str], str]:
    data = object_value(value, "external reproduction")
    exact_keys(data, BOUND | {"mode", "wheel_sha256", "execution", "environment", "commands"},
               "external reproduction")
    if (data["candidate_commit"] != subject["candidate_commit"]
            or data["prepared_subject_sha256"] != digest or data["mode"] != "INDEPENDENT_EXTERNAL"):
        raise ValueError("external reproduction is not bound independent mode")
    execution_id, wheel, created = _reproduction_environment(data, reader, subject, digest, pointer, now)
    paths: set[str] = set()
    commands: set[str] = set()
    for reference in object_list(data["commands"], "reproduction commands"):
        row = bound_record(reference, reader, kind="reproduction_command", keys={"execution_id",
            "wheel_sha256", "command_id", "argv", "exit_code", "executed_at", "stdout_sha256",
            "stderr_sha256", "output_bytes"}, candidate=str(subject["candidate_commit"]), digest=digest)
        command = string_value(row["command_id"], "command ID")
        if command not in COMMAND_ARGUMENTS or command in commands or row["execution_id"] != execution_id:
            raise ValueError("duplicate, missing or foreign reproduction command")
        if row["wheel_sha256"] != wheel or type(row["exit_code"]) is not int or row["exit_code"] != 0:
            raise ValueError("reproduction command failed or used a different artifact")
        if observed_time(row["executed_at"], subject, now) < created:
            raise ValueError("reproduction command predates its environment")
        _command_arguments(row["argv"], command)
        for field in ("stdout_sha256", "stderr_sha256"):
            sha_value(row[field], 64, field)
        integer_value(row["output_bytes"], "command output bytes")
        commands.add(command)
        paths.add(string_value(reference["path"], "command path"))
    if commands != set(COMMAND_ARGUMENTS):
        raise ValueError("external reproduction omits documented command checks")
    return paths, execution_id
