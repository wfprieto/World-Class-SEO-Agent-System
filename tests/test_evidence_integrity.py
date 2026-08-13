"""Adverse-state tests for the evidence store's pure integrity boundary."""

from __future__ import annotations

import json
from typing import cast

import pytest

from adapters.evidence_integrity import (
    SnapshotIntegrityFailure,
    canonical_json,
    decode_verified_row,
    record_digest,
    sha256_text,
)


def _row(**overrides: object) -> dict[str, object]:
    payload_json = '{"title":"A"}'
    scope_json = "{}"
    row: dict[str, object] = {
        "id": 7,
        "url": "https://example.com/",
        "metric_group": "page_state",
        "captured_at": 1.0,
        "payload_json": payload_json,
        "schema_version": "1",
        "source": None,
        "status": "ok",
        "run_id": None,
        "scope_json": scope_json,
        "payload_sha256": sha256_text(payload_json),
    }
    row["record_sha256"] = record_digest(
        url=str(row["url"]),
        metric_group=str(row["metric_group"]),
        captured_at=cast(float, row["captured_at"]),
        payload_json=payload_json,
        schema_version=str(row["schema_version"]),
        source=None,
        status=str(row["status"]),
        run_id=None,
        scope_json=scope_json,
    )
    row.update(overrides)
    return row


def test_decode_verified_row_preserves_the_persisted_snapshot_contract() -> None:
    decoded = decode_verified_row(_row())

    assert decoded == {
        "id": 7,
        "url": "https://example.com/",
        "metric_group": "page_state",
        "captured_at": 1.0,
        "payload": {"title": "A"},
        "schema_version": "1",
        "source": None,
        "status": "ok",
        "run_id": None,
        "scope": {},
        "payload_sha256": sha256_text('{"title":"A"}'),
        "record_sha256": _row()["record_sha256"],
    }


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"payload_json": '{"title":"forged"}'}, "payload hash verification"),
        ({"status": "forged"}, "record hash verification"),
        ({"payload_sha256": ""}, "payload hash verification"),
        ({"record_sha256": ""}, "record hash verification"),
        ({"payload_json": b"{}"}, "stored text contract"),
    ],
)
def test_decode_verified_row_rejects_tampering_and_invalid_storage_types(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(SnapshotIntegrityFailure, match=message):
        decode_verified_row(_row(**overrides))


def test_decode_verified_row_rejects_malformed_json_even_with_matching_digests() -> None:
    malformed = "{not-json"
    row = _row(payload_json=malformed, payload_sha256=sha256_text(malformed))
    row["record_sha256"] = record_digest(
        url=str(row["url"]),
        metric_group=str(row["metric_group"]),
        captured_at=cast(float, row["captured_at"]),
        payload_json=malformed,
        schema_version=str(row["schema_version"]),
        source=None,
        status=str(row["status"]),
        run_id=None,
        scope_json=str(row["scope_json"]),
    )

    with pytest.raises(SnapshotIntegrityFailure, match="malformed JSON"):
        decode_verified_row(row)


@pytest.mark.parametrize(("payload", "scope"), [([], {}), ({}, []), (None, {})])
def test_decode_verified_row_rejects_non_object_payload_or_scope(
    payload: object, scope: object
) -> None:
    payload_json = json.dumps(payload, separators=(",", ":"))
    scope_json = json.dumps(scope, separators=(",", ":"))
    row = _row(
        payload_json=payload_json,
        scope_json=scope_json,
        payload_sha256=sha256_text(payload_json),
    )
    row["record_sha256"] = record_digest(
        url=str(row["url"]),
        metric_group=str(row["metric_group"]),
        captured_at=cast(float, row["captured_at"]),
        payload_json=payload_json,
        schema_version=str(row["schema_version"]),
        source=None,
        status=str(row["status"]),
        run_id=None,
        scope_json=scope_json,
    )

    with pytest.raises(SnapshotIntegrityFailure, match="object contract"):
        decode_verified_row(row)


def test_canonical_json_is_deterministic_finite_and_size_bounded() -> None:
    assert canonical_json({"b": 2, "a": 1}, "payload", 100) == '{"a":1,"b":2}'
    with pytest.raises(ValueError, match="finite JSON-compatible"):
        canonical_json({"value": float("nan")}, "payload", 100)
    with pytest.raises(ValueError, match="exceeds 2 bytes"):
        canonical_json({"x": 1}, "payload", 2)
