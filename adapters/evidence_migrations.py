"""Transactional, additive evidence schema migration and explicit digest repair."""
from __future__ import annotations

import hmac
import sqlite3
from collections.abc import Callable

from adapters.evidence_integrity import record_digest as _record_digest
from adapters.evidence_integrity import sha256_text as _sha256


def _add_columns(connection: sqlite3.Connection) -> None:
    connection.execute(
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
        for row in connection.execute("PRAGMA table_info(snapshots)")
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
            connection.execute(
                f"ALTER TABLE snapshots ADD COLUMN {name} {definition}"
            )


def _backfill_row(connection: sqlite3.Connection, row: sqlite3.Row,
                  canonicalizer: Callable[[str], str], integrity_error: type[RuntimeError]) -> None:
    payload_hash = row["payload_sha256"] or ""
    record_hash = row["record_sha256"] or ""
    if payload_hash and record_hash:
        return  # fully hashed: leave untouched, verify on read

    payload_digest = _sha256(row["payload_json"])
    if payload_hash and not hmac.compare_digest(payload_hash, payload_digest):
        raise integrity_error(
            f"snapshot {row['id']} failed payload hash verification during "
            "migration; refusing to repair it silently"
        )

    try:
        canonical_url = canonicalizer(row["url"])
    except ValueError as exc:
        raise integrity_error(
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
        raise integrity_error(
            f"snapshot {row['id']} failed record hash verification during "
            "migration; refusing to repair it silently"
        )

    connection.execute(
        """
        UPDATE snapshots
           SET url=?, payload_sha256=?, record_sha256=?
         WHERE id=?
        """,
        (canonical_url, payload_digest, record_digest, row["id"]),
    )


def _backfill_rows(connection: sqlite3.Connection, canonicalizer: Callable[[str], str],
                   integrity_error: type[RuntimeError]) -> None:
    legacy_rows = connection.execute(
        """
        SELECT id, url, metric_group, captured_at, payload_json,
               schema_version, source, status, run_id, scope_json,
               payload_sha256, record_sha256
          FROM snapshots
        """
    ).fetchall()
    for row in legacy_rows:
        _backfill_row(connection, row, canonicalizer, integrity_error)


def migrate_schema(connection: sqlite3.Connection, canonicalizer: Callable[[str], str],
                   integrity_error: type[RuntimeError], schema_version: int) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        _add_columns(connection)
        _backfill_rows(connection, canonicalizer, integrity_error)
        connection.execute("DROP INDEX IF EXISTS idx_url_group")
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_url_group
            ON snapshots(
                url, metric_group, schema_version, captured_at DESC, id DESC
            )
            """
        )
        connection.execute(f"PRAGMA user_version={schema_version}")
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def repair_digests(connection: sqlite3.Connection, canonicalizer: Callable[[str], str]) -> dict[str, int | str]:
    """Explicit caller-confirmed rewrite; never invoked by schema migration."""
    rows = connection.execute(
        """
        SELECT id, url, metric_group, captured_at, payload_json,
               schema_version, source, status, run_id, scope_json,
               payload_sha256, record_sha256
          FROM snapshots
        """
    ).fetchall()
    repaired = 0
    for row in rows:
        canonical_url = canonicalizer(row["url"])
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
            connection.execute(
                """
                UPDATE snapshots
                   SET url=?, payload_sha256=?, record_sha256=?
                 WHERE id=?
                """,
                (canonical_url, payload_digest, record_digest, row["id"]),
            )
            repaired += 1
    connection.commit()
    return {"status": "repaired", "repaired": repaired, "checked": len(rows)}
