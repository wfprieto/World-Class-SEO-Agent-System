"""Durable normalized SEO evidence snapshots and compatible drift comparison.

Canonical target: ``adapters/evidence_store.py``. The store is consumed by
adapters and drift-monitoring workflows under the rules in
``docs/evidence-cache-contract.md``. It is intentionally dependency-free and
provides additive schema migration, deterministic JSON, provenance, integrity
verification, nested drift, retention, deletion, and safe lifecycle handling.

The database is append-oriented: repeated captures may be valid observations,
but callers must not present identical records as independent corroboration.
Local digests detect accidental corruption and unsophisticated tampering; they
are not encryption or a trust boundary against a writer that can recompute them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import sqlite3
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Final, Iterator, Mapping


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

SENSITIVE_QUERY_KEYS: Final = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "authorization",
        "code",
        "password",
        "passwd",
        "session",
        "sessionid",
        "token",
    }
)


class EvidenceStoreError(RuntimeError):
    """Base class for evidence-store failures."""


class EvidenceIntegrityError(EvidenceStoreError):
    """Persisted evidence failed hash, JSON, or type validation."""


def canonicalize_url(url: str) -> str:
    """Return a stable URL identity without fragments or embedded credentials."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url must be a non-empty string")

    parsed = urllib.parse.urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must use http or https and include a host")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")

    query_keys = {
        key.lower()
        for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    }
    sensitive = sorted(query_keys & SENSITIVE_QUERY_KEYS)
    if sensitive:
        raise ValueError(
            "URL query contains credential-like fields: " + ", ".join(sensitive)
        )

    try:
        host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        port = parsed.port
    except (UnicodeError, ValueError) as exc:
        raise ValueError("url contains an invalid host or port") from exc

    if port == (80 if scheme == "http" else 443):
        port = None
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port is None else f"{display_host}:{port}"
    path = parsed.path or "/"
    return urllib.parse.urlunsplit((scheme, netloc, path, parsed.query, ""))


def _canonical_json(value: Any, field: str, max_bytes: int) -> str:
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


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_digest(
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
    return _sha256(
        json.dumps(envelope, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    )


def _json_pointer_escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _iter_drift(before: Any, after: Any, path: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield JSON-Pointer-style differences while preserving missing vs null."""
    if isinstance(before, dict) and isinstance(after, dict):
        before_keys = set(before)
        after_keys = set(after)
        for key in sorted(before_keys - after_keys):
            child = f"{path}/{_json_pointer_escape(str(key))}"
            yield child, {"change": "removed", "before": before[key]}
        for key in sorted(after_keys - before_keys):
            child = f"{path}/{_json_pointer_escape(str(key))}"
            yield child, {"change": "added", "after": after[key]}
        for key in sorted(before_keys & after_keys):
            child = f"{path}/{_json_pointer_escape(str(key))}"
            yield from _iter_drift(before[key], after[key], child)
        return

    # Treat arrays as ordered values. Reordering is material unless a metric
    # schema defines its own normalization before storage.
    if before != after:
        yield path or "/", {"change": "changed", "before": before, "after": after}


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
            try:
                self.db_path.parent.chmod(0o700)
            except OSError:
                pass

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
            try:
                self.db_path.chmod(0o600)
            except OSError:
                pass

    def _migrate_schema(self) -> None:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS snapshots (
                        id             INTEGER PRIMARY KEY AUTOINCREMENT,
                        url            TEXT NOT NULL,
                        metric_group   TEXT NOT NULL,
                        captured_at    REAL NOT NULL,
                        payload_json   TEXT NOT NULL,
                        schema_version TEXT NOT NULL DEFAULT '1',
                        source         TEXT,
                        status         TEXT NOT NULL DEFAULT 'ok',
                        run_id         TEXT,
                        scope_json     TEXT NOT NULL DEFAULT '{}',
                        payload_sha256 TEXT NOT NULL DEFAULT '',
                        record_sha256  TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                columns = {
                    row["name"]
                    for row in self._conn.execute("PRAGMA table_info(snapshots)")
                }
                additions = {
                    "schema_version": "TEXT NOT NULL DEFAULT '1'",
                    "source": "TEXT",
                    "status": "TEXT NOT NULL DEFAULT 'ok'",
                    "run_id": "TEXT",
                    "scope_json": "TEXT NOT NULL DEFAULT '{}'",
                    "payload_sha256": "TEXT NOT NULL DEFAULT ''",
                    "record_sha256": "TEXT NOT NULL DEFAULT ''",
                }
                for name, definition in additions.items():
                    if name not in columns:
                        self._conn.execute(
                            f"ALTER TABLE snapshots ADD COLUMN {name} {definition}"
                        )

                legacy_rows = self._conn.execute(
                    """
                    SELECT id, url, metric_group, captured_at, payload_json,
                           schema_version, source, status, run_id, scope_json,
                           payload_sha256, record_sha256
                      FROM snapshots
                    """
                ).fetchall()
                # Backfill digests ONLY for rows that genuinely lack them (pre-digest legacy
                # rows). A row that already carries both digests is never rewritten here:
                # recomputing it would silently re-bless external tampering and destroy
                # tamper-evidence. Verification of hashed rows happens on read
                # (`_decode_row`) and in `integrity_check()`. Deliberate rewriting is only
                # available through the explicit `repair_digests(confirm=True)` method.
                for row in legacy_rows:
                    payload_hash = row["payload_sha256"] or ""
                    record_hash = row["record_sha256"] or ""
                    if payload_hash and record_hash:
                        continue  # fully hashed: leave untouched, verify on read

                    payload_digest = _sha256(row["payload_json"])
                    if payload_hash and not hmac.compare_digest(payload_hash, payload_digest):
                        raise EvidenceIntegrityError(
                            f"snapshot {row['id']} failed payload hash verification during "
                            "migration; refusing to repair it silently"
                        )

                    try:
                        canonical_url = canonicalize_url(row["url"])
                    except ValueError as exc:
                        raise EvidenceIntegrityError(
                            f"legacy snapshot {row['id']} has an invalid URL"
                        ) from exc

                    record_digest = _record_digest(
                        url=canonical_url,
                        metric_group=row["metric_group"],
                        captured_at=row["captured_at"],
                        payload_json=row["payload_json"],
                        schema_version=row["schema_version"],
                        source=row["source"],
                        status=row["status"],
                        run_id=row["run_id"],
                        scope_json=row["scope_json"],
                    )
                    if record_hash and not hmac.compare_digest(record_hash, record_digest):
                        raise EvidenceIntegrityError(
                            f"snapshot {row['id']} failed record hash verification during "
                            "migration; refusing to repair it silently"
                        )

                    self._conn.execute(
                        """
                        UPDATE snapshots
                           SET url=?, payload_sha256=?, record_sha256=?
                         WHERE id=?
                        """,
                        (canonical_url, payload_digest, record_digest, row["id"]),
                    )

                self._conn.execute("DROP INDEX IF EXISTS idx_url_group")
                self._conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_url_group
                    ON snapshots(
                        url, metric_group, schema_version, captured_at DESC, id DESC
                    )
                    """
                )
                self._conn.execute(f"PRAGMA user_version={DB_SCHEMA_VERSION}")
            except Exception:
                self._conn.rollback()
                raise
            else:
                self._conn.commit()

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
        source = None if source is None else self._require_label(source, "source")
        run_id = None if run_id is None else self._require_label(run_id, "run_id")
        payload_json = _canonical_json(payload, "payload", self.max_payload_bytes)
        scope_json = _canonical_json(dict(scope or {}), "scope", self.max_payload_bytes)

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
            return int(cursor.lastrowid)

    def _decode_row(self, row: sqlite3.Row) -> dict[str, Any]:
        payload_json = row["payload_json"]
        expected_hash = row["payload_sha256"]
        actual_hash = _sha256(payload_json)
        if not expected_hash or not hmac.compare_digest(expected_hash, actual_hash):
            raise EvidenceIntegrityError(
                f"snapshot {row['id']} failed payload hash verification"
            )
        expected_record_hash = row["record_sha256"]
        actual_record_hash = _record_digest(
            url=row["url"],
            metric_group=row["metric_group"],
            captured_at=row["captured_at"],
            payload_json=payload_json,
            schema_version=row["schema_version"],
            source=row["source"],
            status=row["status"],
            run_id=row["run_id"],
            scope_json=row["scope_json"],
        )
        if not expected_record_hash or not hmac.compare_digest(
            expected_record_hash, actual_record_hash
        ):
            raise EvidenceIntegrityError(
                f"snapshot {row['id']} failed record hash verification"
            )
        try:
            payload = json.loads(payload_json)
            scope = json.loads(row["scope_json"])
        except json.JSONDecodeError as exc:
            raise EvidenceIntegrityError(
                f"snapshot {row['id']} contains malformed JSON"
            ) from exc
        if not isinstance(payload, dict) or not isinstance(scope, dict):
            raise EvidenceIntegrityError(
                f"snapshot {row['id']} violates the payload or scope object contract"
            )
        return {
            "id": row["id"],
            "url": row["url"],
            "metric_group": row["metric_group"],
            "captured_at": row["captured_at"],
            "payload": payload,
            "schema_version": row["schema_version"],
            "source": row["source"],
            "status": row["status"],
            "run_id": row["run_id"],
            "scope": scope,
            "payload_sha256": expected_hash,
            "record_sha256": expected_record_hash,
        }

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
        if len(recent) < 2:
            return {
                "status": "insufficient_history",
                "url": canonicalize_url(url),
                "metric_group": metric_group,
                "schema_version": schema_version,
                "have": len(recent),
            }

        current, previous = recent[0], recent[1]
        if current["schema_version"] != previous["schema_version"]:
            return {
                "status": "schema_mismatch",
                "url": current["url"],
                "metric_group": metric_group,
                "current_schema": current["schema_version"],
                "previous_schema": previous["schema_version"],
                "current_id": current["id"],
                "previous_id": previous["id"],
            }

        drift = dict(_iter_drift(previous["payload"], current["payload"]))
        return {
            "status": "ok",
            "url": current["url"],
            "metric_group": metric_group,
            "schema_version": current["schema_version"],
            "from": previous["captured_at"],
            "to": current["captured_at"],
            "previous_id": previous["id"],
            "current_id": current["id"],
            "drift": drift,
            "drift_count": len(drift),
        }

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
        """Recompute and overwrite integrity digests for every row.

        This is the only path that rewrites existing digests. It is deliberately NOT part
        of initialization, because rewriting a digest over tampered content destroys the
        tamper-evidence that `integrity_check()` and `_decode_row()` rely on.

        Use it only when you have established that a mismatch is caused by a legitimate
        migration and not by tampering. It requires `confirm=True`.
        """
        if not confirm:
            raise ValueError(
                "repair_digests() rewrites integrity digests and destroys tamper-evidence; "
                "call it with confirm=True only after establishing the cause of the mismatch"
            )
        with self._lock:
            self._ensure_open()
            rows = self._conn.execute(
                """
                SELECT id, url, metric_group, captured_at, payload_json,
                       schema_version, source, status, run_id, scope_json,
                       payload_sha256, record_sha256
                  FROM snapshots
                """
            ).fetchall()
            repaired = 0
            for row in rows:
                canonical_url = canonicalize_url(row["url"])
                payload_digest = _sha256(row["payload_json"])
                record_digest = _record_digest(
                    url=canonical_url,
                    metric_group=row["metric_group"],
                    captured_at=row["captured_at"],
                    payload_json=row["payload_json"],
                    schema_version=row["schema_version"],
                    source=row["source"],
                    status=row["status"],
                    run_id=row["run_id"],
                    scope_json=row["scope_json"],
                )
                if (
                    row["url"] != canonical_url
                    or (row["payload_sha256"] or "") != payload_digest
                    or (row["record_sha256"] or "") != record_digest
                ):
                    self._conn.execute(
                        """
                        UPDATE snapshots
                           SET url=?, payload_sha256=?, record_sha256=?
                         WHERE id=?
                        """,
                        (canonical_url, payload_digest, record_digest, row["id"]),
                    )
                    repaired += 1
            self._conn.commit()
        return {"status": "repaired", "repaired": repaired, "checked": len(rows)}

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def __enter__(self) -> "EvidenceStore":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
