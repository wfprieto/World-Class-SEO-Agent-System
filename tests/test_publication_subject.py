"""Exact-byte publication subject regression tests; all payloads are synthetic."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from scripts import publication_policy as policy
from scripts.publication_subject import (
    build_subject,
    json_object,
    object_value,
    parse_subject,
    subject_files,
)

NOW = datetime(2026, 10, 31, 2, 0, tzinfo=UTC)


def payloads() -> dict[str, bytes]:
    result = {
        "world_class_seo_agent_system-1.7.1-py3-none-any.whl": b"synthetic-wheel",
        "world_class_seo_agent_system-1.7.1.tar.gz": b"synthetic-sdist",
        "sbom.cdx.json": b'{"bomFormat":"CycloneDX"}\n',
        "release-manifest.json": b'{"schema_version":"1.0.0"}\n',
    }
    result["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in sorted(result.items())
    ).encode()
    return result


def subject() -> dict[str, object]:
    roles = {".whl": "wheel", ".gz": "sdist"}
    return {
        "schema_version": "1.0.0", "repository": policy.REPOSITORY,
        "repository_id": policy.REPOSITORY_ID, "owner_id": policy.OWNER_ID,
        "candidate_commit": "a" * 40, "candidate_tree": "b" * 40,
        "version": "1.7.1", "planned_tag": "v1.7.1", "ci_run_id": 1,
        "ci_attempt": 1, "prepare_run_id": 2, "prepare_attempt": 1,
        "prepared_at": NOW.isoformat(),
        "files": [
            {"name": name, "role": next(
                (role for suffix, role in roles.items() if name.endswith(suffix)),
                {"sbom.cdx.json": "sbom", "release-manifest.json": "manifest",
                 "SHA256SUMS": "checksums"}.get(name, "")),
             "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(payloads().items())
        ],
    }


def test_valid_subject_retains_exact_frozen_identity_and_files():
    value = subject()
    assert parse_subject(json.dumps(value).encode(), now=NOW) == value
    assert set(subject_files(value)) == set(payloads())


@pytest.mark.parametrize("field,value", [
    ("repository", "attacker/repository"), ("repository_id", True),
    ("owner_id", 1), ("candidate_commit", "A" * 40),
    ("candidate_tree", "c" * 39), ("version", "1.7.1rc1"),
    ("planned_tag", "v2.0.0"), ("ci_run_id", False),
    ("ci_attempt", 0), ("prepare_attempt", -1), ("unknown", "extra"),
])
def test_rejects_misbound_or_unknown_subject_fields(field, value):
    data = {**subject(), field: value}
    with pytest.raises(ValueError):
        parse_subject(json.dumps(data).encode(), now=NOW)


@pytest.mark.parametrize("delta", [timedelta(days=-2), timedelta(minutes=6)])
def test_preparation_must_be_current_and_not_future_dated(delta):
    data = {**subject(), "prepared_at": (NOW + delta).isoformat()}
    with pytest.raises(ValueError):
        parse_subject(json.dumps(data).encode(), now=NOW)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'[]'])
def test_rejects_ambiguous_or_nonfinite_json(raw):
    with pytest.raises(ValueError):
        parse_subject(raw, now=NOW)


def test_builder_pins_actual_payload_bytes_and_canonicalizes_json():
    raw = build_subject(
        commit="a" * 40, tree="b" * 40, version="1.7.1", ci_run_id=1,
        ci_attempt=1, prepare_run_id=2, prepare_attempt=1, prepared_at=NOW,
        payloads=payloads(),
    )
    assert raw.endswith(b"\n")
    assert json.loads(raw) == subject()


def test_builder_rejects_checksum_file_that_does_not_cover_actual_four_payloads():
    data = {**payloads(), "SHA256SUMS": b"invented verification\n"}
    with pytest.raises(ValueError):
        build_subject(
            commit="a" * 40, tree="b" * 40, version="1.7.1", ci_run_id=1,
            ci_attempt=1, prepare_run_id=2, prepare_attempt=1, prepared_at=NOW,
            payloads=data,
        )


def test_object_boundary_rejects_non_string_keys():
    with pytest.raises(ValueError):
        object_value({1: "not-json"}, "subject")


def test_json_boundary_rejects_overflowed_nested_floats_not_only_nan_literals():
    with pytest.raises(ValueError):
        json_object(b'{"nested":[{"value":1e999}]}', "record")
