"""Durable SEO evidence snapshots; local digests detect corruption, not hostile writers."""

from __future__ import annotations

import math
import os
import sqlite3
import threading
import time
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, Final

from adapters.evidence_identity import _iter_drift as _iter_drift
from adapters.evidence_identity import canonicalize_url as canonicalize_url
from adapters.evidence_identity import compare_snapshots
from adapters.evidence_integrity import (
    SnapshotIntegrityFailure,
    decode_verified_row,
)
from adapters.evidence_integrity import (
    canonical_json as _canonical_json,
)
from adapters.evidence_integrity import (
    record_digest as _record_digest,
)
from adapters.evidence_integrity import (
    sha256_text as _sha256,
)
from adapters.evidence_migrations import migrate_schema
from adapters.evidence_migrations import repair_digests as repair_stored_digests
from sensitive_data import redact_evidence_fields

__all__ = [
    "DEFAULT_DB",
    "DB_SCHEMA_VERSION",
    "EvidenceIntegrityError",
    "EvidenceStore",
    "EvidenceStoreError",
    "canonicalize_url",
]

DEFAULT_DB: Final = ".seo-cache/evidence.db"
DB_SCHEMA_VERSION: Final = 3
DEFAULT_PAYLOAD_SCHEMA_VERSION: Final = "1"
MAX_TEXT_LENGTH: Final = 2_048
MAX_PAYLOAD_BYTES: Final = 2_000_000
_SCHEMA_INIT_LOCK = threading.Lock()

class EvidenceStoreError(RuntimeError):
    """Base class for evidence-store failures."""


class EvidenceIntegrityError(EvidenceStoreError):
    """Persisted evidence failed hash, JSON, or type validation."""


class EvidenceStore:
    """SQLite-backed evidence store with additive migration and integrity checks."""

    def __init__(
        self,
        db_path: str | os.PathLike[str] = DEFAULT_DB,
        *,
        busy_timeout_ms: int = 5_000,
        max_payload_bytes: int = MAX_PAYLOAD_BYTES,
    ) -> None:
        if not isinstance(busy_timeout_ms, int) or busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be a non-negative integer")
        if not isinstance(max_payload_bytes, int) or max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be a positive integer")

        self.db_path = Path(db_path)
        self.max_payload_bytes = max_payload_bytes
        self._lock = threading.RLock()
        self._closed = False

        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with suppress(OSError):
                self.db_path.parent.chmod(0o700)

        self._conn = sqlite3.connect(
            str(self.db_path),
            timeout=busy_timeout_ms / 1_000,
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        # Serialize first-use configuration and migration inside this process.
        # SQLite's busy timeout remains the cross-process contention control.
        try:
            with _SCHEMA_INIT_LOCK:
                self._conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
                self._conn.execute("PRAGMA foreign_keys=ON")
                if str(self.db_path) != ":memory:":
                    self._conn.execute("PRAGMA journal_mode=WAL")
                self._conn.execute("PRAGMA synchronous=NORMAL")
                self._migrate_schema()
        except Exception:
            self._conn.close()
            self._closed = True
            raise

        if str(self.db_path) != ":memory:":
            with suppress(OSError):
                self.db_path.chmod(0o600)

    def _migrate_schema(self) -> None:
        with self._lock:
            migrate_schema(self._conn, canonicalize_url, EvidenceIntegrityError, DB_SCHEMA_VERSION)

    @staticmethod
    def _require_label(value: str, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        value = value.strip()
        if len(value) > MAX_TEXT_LENGTH:
            raise ValueError(f"{field} exceeds {MAX_TEXT_LENGTH} characters")
        return value

    def _ensure_open(self) -> None:
        if self._closed:
            raise EvidenceStoreError("EvidenceStore is closed")

    def record(
        self,
        url: str,
        metric_group: str,
        payload: dict[str, Any],
        *,
        schema_version: str = DEFAULT_PAYLOAD_SCHEMA_VERSION,
        source: str | None = None,
        status: str = "ok",
        run_id: str | None = None,
        scope: Mapping[str, Any] | None = None,
        captured_at: float | None = None,
    ) -> int:
        """Store one normalized snapshot and return its row ID."""
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        if scope is not None and not isinstance(scope, Mapping):
            raise TypeError("scope must be a mapping")

        canonical_url = canonicalize_url(url)
        metric_group = self._require_label(metric_group, "metric_group")
        schema_version = self._require_label(schema_version, "schema_version")
        status = self._require_label(status, "status")
        source, run_id, sanitized_payload, sanitized_scope = redact_evidence_fields(
            source, run_id, payload, dict(scope or {})
        )
        source = None if source is None else self._require_label(source, "source")
        run_id = None if run_id is None else self._require_label(run_id, "run_id")
        payload_json = _canonical_json(sanitized_payload, "payload", self.max_payload_bytes)
        scope_json = _canonical_json(sanitized_scope, "scope", self.max_payload_bytes)

        timestamp = time.time() if captured_at is None else float(captured_at)
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError("captured_at must be a finite non-negative timestamp")

        with self._lock, self._conn:
            self._ensure_open()
            cursor = self._conn.execute(
                """
                INSERT INTO snapshots(
                    url, metric_group, captured_at, payload_json,
                    schema_version, source, status, run_id,
                    scope_json, payload_sha256, record_sha256
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    canonical_url,
                    metric_group,
                    timestamp,
                    payload_json,
                    schema_version,
                    source,
                    status,
                    run_id,
                    scope_json,
                    _sha256(payload_json),
                    _record_digest(
                        url=canonical_url,
                        metric_group=metric_group,
                        captured_at=timestamp,
                        payload_json=payload_json,
                        schema_version=schema_version,
                        source=source,
                        status=status,
                        run_id=run_id,
                        scope_json=scope_json,
                    ),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("snapshot insert did not return a row id")
            return int(cursor.lastrowid)

    def _decode_row(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            return decode_verified_row(row)
        except SnapshotIntegrityFailure as exc:
            raise EvidenceIntegrityError(str(exc)) from exc

    def latest(
        self,
        url: str,
        metric_group: str,
        limit: int = 1,
        *,
        schema_version: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent verified snapshots, newest first."""
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 10_000:
            raise ValueError("limit must be an integer from 1 to 10000")
        canonical_url = canonicalize_url(url)
        metric_group = self._require_label(metric_group, "metric_group")
        parameters: list[Any] = [canonical_url, metric_group]
        schema_clause = ""
        if schema_version is not None:
            schema_clause = " AND schema_version=?"
            parameters.append(self._require_label(schema_version, "schema_version"))
        parameters.append(limit)

        with self._lock:
            self._ensure_open()
            rows = self._conn.execute(
                f"""
                SELECT id, url, metric_group, captured_at, payload_json,
                       schema_version, source, status, run_id, scope_json,
                       payload_sha256, record_sha256
                  FROM snapshots
                 WHERE url=? AND metric_group=?{schema_clause}
                 ORDER BY captured_at DESC, id DESC
                 LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [self._decode_row(row) for row in rows]

    def compare(
        self,
        url: str,
        metric_group: str,
        *,
        schema_version: str | None = None,
    ) -> dict[str, Any]:
        """Compare the two latest compatible verified snapshots."""
        recent = self.latest(
            url,
            metric_group,
            limit=2,
            schema_version=schema_version,
        )
        return compare_snapshots(recent, url, metric_group, schema_version)

    def purge(
        self,
        *,
        before: float,
        keep_latest: int = 1,
        url: str | None = None,
        metric_group: str | None = None,
        schema_version: str | None = None,
    ) -> int:
        """Delete old snapshots while retaining the newest N per compatible series."""
        cutoff = float(before)
        if not math.isfinite(cutoff) or cutoff < 0:
            raise ValueError("before must be a finite non-negative timestamp")
        if not isinstance(keep_latest, int) or isinstance(keep_latest, bool) or keep_latest < 0:
            raise ValueError("keep_latest must be a non-negative integer")

        filters: list[str] = []
        params: list[Any] = []
        if url is not None:
            filters.append("url=?")
            params.append(canonicalize_url(url))
        if metric_group is not None:
            filters.append("metric_group=?")
            params.append(self._require_label(metric_group, "metric_group"))
        if schema_version is not None:
            filters.append("schema_version=?")
            params.append(self._require_label(schema_version, "schema_version"))
        where = " WHERE " + " AND ".join(filters) if filters else ""

        with self._lock, self._conn:
            self._ensure_open()
            rows = self._conn.execute(
                f"""
                SELECT id, url, metric_group, schema_version, captured_at
                  FROM snapshots{where}
                 ORDER BY url, metric_group, schema_version, captured_at DESC, id DESC
                """,
                params,
            ).fetchall()
            seen: dict[tuple[str, str, str], int] = {}
            delete_ids: list[int] = []
            for row in rows:
                key = (row["url"], row["metric_group"], row["schema_version"])
                rank = seen.get(key, 0)
                seen[key] = rank + 1
                if row["captured_at"] < cutoff and rank >= keep_latest:
                    delete_ids.append(int(row["id"]))
            if delete_ids:
                self._conn.executemany(
                    "DELETE FROM snapshots WHERE id=?",
                    [(row_id,) for row_id in delete_ids],
                )
            return len(delete_ids)

    def delete(
        self,
        url: str,
        *,
        metric_group: str | None = None,
    ) -> int:
        """Delete all evidence for a URL, optionally limited to one metric group."""
        canonical_url = canonicalize_url(url)
        params: list[Any] = [canonical_url]
        clause = ""
        if metric_group is not None:
            clause = " AND metric_group=?"
            params.append(self._require_label(metric_group, "metric_group"))
        with self._lock, self._conn:
            self._ensure_open()
            cursor = self._conn.execute(
                f"DELETE FROM snapshots WHERE url=?{clause}", params
            )
            return int(cursor.rowcount)

    def integrity_check(self, *, verify_payloads: bool = True) -> dict[str, Any]:
        """Run SQLite quick-check and optionally verify every payload digest."""
        with self._lock:
            self._ensure_open()
            quick_rows = [row[0] for row in self._conn.execute("PRAGMA quick_check")]
            errors: list[str] = []
            checked = 0
            if verify_payloads:
                rows = self._conn.execute(
                    """
                    SELECT id, url, metric_group, captured_at, payload_json,
                           schema_version, source, status, run_id, scope_json,
                           payload_sha256, record_sha256
                      FROM snapshots
                    """
                ).fetchall()
                for row in rows:
                    checked += 1
                    try:
                        self._decode_row(row)
                    except EvidenceIntegrityError as exc:
                        errors.append(str(exc))
            sqlite_ok = quick_rows == ["ok"]
            return {
                "status": "ok" if sqlite_ok and not errors else "failed",
                "sqlite_quick_check": quick_rows,
                "payloads_checked": checked,
                "errors": errors,
            }

    def repair_digests(self, *, confirm: bool = False) -> dict[str, Any]:
        """Explicitly re-bless all rows only after investigating a digest mismatch."""
        if not confirm:
            raise ValueError(
                "repair_digests() rewrites integrity digests and destroys tamper-evidence; "
                "call it with confirm=True only after establishing the cause of the mismatch"
            )
        with self._lock:
            self._ensure_open()
            return repair_stored_digests(self._conn, canonicalize_url)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def __enter__(self) -> EvidenceStore:
        self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
