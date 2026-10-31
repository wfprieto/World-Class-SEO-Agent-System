"""Bounded, detached publication subjects; hashes bind bytes, never authority.

The five payload records have exact role/name/bytes/sha256 keys. SHA256SUMS
contains four ``<sha256>  <basename>`` rows, excluding itself and the subject.
The prepared subject has no self hash, evidence commit, or provider artifact ID.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from scripts import publication_policy as policy
from scripts.publication_freshness import record_freshness

JsonObject = dict[str, object]


def object_value(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object with string keys")
    return dict(value)


def string_value(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{label} must be a nonempty trimmed string")
    return value


def integer_value(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _unambiguous(pairs: list[tuple[str, object]]) -> JsonObject:
    if len(dict(pairs)) != len(pairs):
        raise ValueError("duplicate JSON keys are forbidden")
    return dict(pairs)


def _nonfinite(value: str) -> object:
    raise ValueError(f"nonfinite JSON number is forbidden: {value}")


def json_object(raw: bytes, label: str) -> JsonObject:
    """Parse a bounded object without duplicate keys or nonfinite numbers."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= policy.MAX_RECORD_BYTES:
        raise ValueError(f"{label} exceeds the bounded JSON size")
    try:
        value: object = json.loads(raw, object_pairs_hook=_unambiguous, parse_constant=_nonfinite)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"{label} is invalid JSON") from exc
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("nonfinite JSON numbers are forbidden")
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return object_value(value, label)


def exact_keys(value: JsonObject, keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise ValueError(f"{label} must use the exact contract keys")


def sha_value(value: object, length: int, label: str) -> str:
    text = string_value(value, label)
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", text) is None:
        raise ValueError(f"{label} must be exact lowercase hexadecimal")
    return text


def instant(value: object, label: str) -> datetime:
    text = string_value(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be a UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must include UTC timezone")
    return parsed.astimezone(UTC)


def require_fresh(value: object, *, now: datetime, ttl: int, label: str) -> datetime:
    issued = instant(value, label)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("verification clock must be timezone-aware")
    if (issued - now).total_seconds() > policy.CLOCK_SKEW_SECONDS:
        raise ValueError(f"{label} is future-dated")
    if now >= issued + timedelta(seconds=ttl):
        raise ValueError(f"{label} has expired")
    record_freshness(issued, ttl=ttl, skew=policy.CLOCK_SKEW_SECONDS)
    return issued


def payload_names(version: str) -> dict[str, str]:
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) is None:
        raise ValueError("version must be digits.digits.digits")
    return {
        f"world_class_seo_agent_system-{version}-py3-none-any.whl": "wheel",
        f"world_class_seo_agent_system-{version}.tar.gz": "sdist",
        "sbom.cdx.json": "sbom", "release-manifest.json": "manifest",
        "SHA256SUMS": "checksums",
    }


def _subject_identity(subject: JsonObject) -> str:
    exact_keys(subject, {
        "schema_version", "repository", "repository_id", "owner_id", "candidate_commit",
        "candidate_tree", "version", "planned_tag", "ci_run_id", "ci_attempt",
        "prepare_run_id", "prepare_attempt", "prepared_at", "files",
    }, "publication subject")
    expected = {"schema_version": "1.0.0", "repository": policy.REPOSITORY,
                "repository_id": policy.REPOSITORY_ID, "owner_id": policy.OWNER_ID}
    if any(subject.get(key) != value for key, value in expected.items()):
        raise ValueError("publication subject repository identity or schema mismatch")
    for field in ("repository_id", "owner_id", "ci_run_id", "ci_attempt",
                  "prepare_run_id", "prepare_attempt"):
        integer_value(subject[field], field)
    for field in ("candidate_commit", "candidate_tree"):
        sha_value(subject[field], 40, field)
    version = string_value(subject["version"], "version")
    payload_names(version)
    if subject["planned_tag"] != "v" + version:
        raise ValueError("planned tag must match exact subject version")
    instant(subject["prepared_at"], "prepared_at")
    return version


def parse_subject(raw: bytes, *, now: datetime) -> JsonObject:
    subject = json_object(raw, "publication subject")
    subject_files(subject)
    require_fresh(subject["prepared_at"], now=now, ttl=policy.PREPARED_TTL_SECONDS,
                  label="prepared_at")
    return subject


def subject_files(subject: JsonObject) -> dict[str, JsonObject]:
    names = payload_names(_subject_identity(subject))
    rows = subject["files"]
    if not isinstance(rows, list) or len(rows) != 5:
        raise ValueError("publication subject requires exactly five payload files")
    files: dict[str, JsonObject] = {}
    total = 0
    for item in rows:
        row = object_value(item, "payload file")
        exact_keys(row, {"name", "role", "bytes", "sha256"}, "payload file")
        name = string_value(row["name"], "payload filename")
        if name not in names or name in files or row["role"] != names[name]:
            raise ValueError("unexpected, duplicate or misclassified payload file")
        size = integer_value(row["bytes"], "payload bytes")
        if size > policy.MAX_MEMBER_BYTES:
            raise ValueError("payload exceeds member byte cap")
        total += size
        sha_value(row["sha256"], 64, "payload sha256")
        files[name] = row
    if total > policy.MAX_EXPANDED_BYTES or set(files) != set(names):
        raise ValueError("publication payload set or expanded size is invalid")
    return files


def _payload_checksums(payloads: Mapping[str, bytes]) -> None:
    expected = {name: hashlib.sha256(data).hexdigest()
                for name, data in payloads.items() if name != "SHA256SUMS"}
    try:
        lines = payloads["SHA256SUMS"].decode("ascii").splitlines()
    except UnicodeError as exc:
        raise ValueError("SHA256SUMS must contain ASCII checksum rows") from exc
    actual: dict[str, str] = {}
    for line in lines:
        digest, separator, name = line.partition("  ")
        if not separator or name not in expected or name in actual:
            raise ValueError("SHA256SUMS contains missing, duplicate or unexpected files")
        actual[name] = digest
    if actual != expected:
        raise ValueError("SHA256SUMS must hash exactly the four other payload bytes")


def build_subject(
    *, commit: str, tree: str, version: str, ci_run_id: int, ci_attempt: int,
    prepare_run_id: int, prepare_attempt: int, prepared_at: datetime,
    payloads: Mapping[str, bytes],
) -> bytes:
    names = payload_names(version)
    if set(payloads) != set(names) or any(not isinstance(data, bytes) for data in payloads.values()):
        raise ValueError("prepared payloads must contain exactly the five approved byte files")
    _payload_checksums(payloads)
    subject: JsonObject = {
        "schema_version": "1.0.0", "repository": policy.REPOSITORY,
        "repository_id": policy.REPOSITORY_ID, "owner_id": policy.OWNER_ID,
        "candidate_commit": commit, "candidate_tree": tree, "version": version,
        "planned_tag": "v" + version, "ci_run_id": ci_run_id, "ci_attempt": ci_attempt,
        "prepare_run_id": prepare_run_id, "prepare_attempt": prepare_attempt,
        "prepared_at": prepared_at.isoformat(),
        "files": [{"name": name, "role": names[name], "bytes": len(data),
                   "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in sorted(payloads.items())],
    }
    raw = (json.dumps(subject, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    parse_subject(raw, now=prepared_at)
    return raw
