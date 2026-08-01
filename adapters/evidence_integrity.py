"""Pure serialization and integrity primitives for the canonical evidence store.

This module owns no persistence, migration, repair, or public store API.
``adapters.evidence_store.EvidenceStore`` remains the sole authority for evidence
lifecycle decisions; these helpers isolate its deterministic data-integrity boundary.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Protocol


class SnapshotRow(Protocol):
    """Minimal keyed-row contract supported by sqlite rows and test mappings."""

    def __getitem__(self, key: str) -> Any: ...


class SnapshotIntegrityFailure(ValueError):
    """A persisted row failed pure digest, JSON, or object-contract validation."""


def canonical_json(value: Any, field: str, max_bytes: int) -> str:
    """Encode deterministic finite JSON within the caller's byte limit."""
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be finite JSON-compatible data") from exc
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return encoded


def sha256_text(text: str) -> str:
    """Return the lowercase SHA-256 hex digest of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_digest(
    *,
    url: str,
    metric_group: str,
    captured_at: float,
    payload_json: str,
    schema_version: str,
    source: str | None,
    status: str,
    run_id: str | None,
    scope_json: str,
) -> str:
    """Digest the exact, version-compatible persisted record envelope."""
    envelope = [
        url,
        metric_group,
        float(captured_at).hex(),
        payload_json,
        schema_version,
        source,
        status,
        run_id,
        scope_json,
    ]
    return sha256_text(
        json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    )


def decode_verified_row(row: SnapshotRow) -> dict[str, Any]:
    """Verify and decode one persisted row without performing I/O or repair."""
    row_id = row["id"]
    payload_json = row["payload_json"]
    scope_json = row["scope_json"]
    if not isinstance(payload_json, str) or not isinstance(scope_json, str):
        raise SnapshotIntegrityFailure(
            f"snapshot {row_id} violates the stored text contract"
        )

    expected_payload_hash = row["payload_sha256"]
    actual_payload_hash = sha256_text(payload_json)
    if (
        not isinstance(expected_payload_hash, str)
        or not expected_payload_hash
        or not hmac.compare_digest(expected_payload_hash, actual_payload_hash)
    ):
        raise SnapshotIntegrityFailure(
            f"snapshot {row_id} failed payload hash verification"
        )

    expected_record_hash = row["record_sha256"]
    actual_record_hash = record_digest(
        url=row["url"],
        metric_group=row["metric_group"],
        captured_at=row["captured_at"],
        payload_json=payload_json,
        schema_version=row["schema_version"],
        source=row["source"],
        status=row["status"],
        run_id=row["run_id"],
        scope_json=scope_json,
    )
    if (
        not isinstance(expected_record_hash, str)
        or not expected_record_hash
        or not hmac.compare_digest(expected_record_hash, actual_record_hash)
    ):
        raise SnapshotIntegrityFailure(
            f"snapshot {row_id} failed record hash verification"
        )

    try:
        payload = json.loads(payload_json)
        scope = json.loads(scope_json)
    except json.JSONDecodeError as exc:
        raise SnapshotIntegrityFailure(
            f"snapshot {row_id} contains malformed JSON"
        ) from exc
    if not isinstance(payload, dict) or not isinstance(scope, dict):
        raise SnapshotIntegrityFailure(
            f"snapshot {row_id} violates the payload or scope object contract"
        )

    return {
        "id": row_id,
        "url": row["url"],
        "metric_group": row["metric_group"],
        "captured_at": row["captured_at"],
        "payload": payload,
        "schema_version": row["schema_version"],
        "source": row["source"],
        "status": row["status"],
        "run_id": row["run_id"],
        "scope": scope,
        "payload_sha256": expected_payload_hash,
        "record_sha256": expected_record_hash,
    }
