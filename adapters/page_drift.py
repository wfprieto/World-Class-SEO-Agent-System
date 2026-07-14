"""Page-state drift detection over the canonical EvidenceStore.

Replaces the proposed standalone drift database. The kit already has exactly one
persistent evidence store (`adapters/evidence_store.py`, `.seo-cache/evidence.db`)
with SHA-256 record digests, canonical URLs, and drift comparison. Adding a second
SQLite database would create a competing source of truth, so this module is a thin
layer instead:

- fingerprint()  SHA-256 of page content and structured data
- capture()      records a page-state snapshot via EvidenceStore (metric_group "page_state")
- compare()      classifies EvidenceStore drift into critical / warning / info

Severity policy:
  critical  status_code moves into 4xx/5xx; canonical changes; robots gains noindex;
            title disappears
  warning   title/h1 change; schema_hash change (structured-data drift)
  info      html_hash change with no field-level change

Missing history is reported as `insufficient_history`, never as "no drift".
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

from adapters.evidence_store import (
    DEFAULT_DB,
    EvidenceIntegrityError,
    EvidenceStore,
    _sha256 as _payload_sha256,
)

METRIC_GROUP = "page_state"
_TRACKED = ("title", "canonical", "robots", "h1", "status_code", "html_hash", "schema_hash")


def _hash_optional(text: str | None) -> str | None:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None


def fingerprint(fields: dict[str, Any]) -> dict[str, Any]:
    """Normalized, hashed page state. Deterministic for identical input."""
    return {
        "title": fields.get("title"),
        "canonical": fields.get("canonical"),
        "robots": fields.get("robots"),
        "h1": fields.get("h1"),
        "status_code": fields.get("status_code"),
        "html_hash": _hash_optional(fields.get("html") if isinstance(fields.get("html"), str) else None),
        "schema_hash": _hash_optional(fields.get("schema_json") if isinstance(fields.get("schema_json"), str) else None),
    }


def _severity(field: str, before: Any, after: Any) -> str:
    if field == "status_code":
        return "critical" if str(after).startswith(("4", "5")) else "warning"
    if field == "canonical":
        return "critical"
    if field == "robots":
        return "critical" if "noindex" in str(after or "").lower() else "warning"
    if field == "title":
        return "critical" if not after else "warning"
    if field in ("h1", "schema_hash"):
        return "warning"
    return "info"



def verify_untampered(db_path: str | Path) -> dict[str, Any]:
    """Verify stored payload digests on a raw connection, before any migration runs.

    Opening `EvidenceStore` triggers `_migrate_schema()`, which recomputes and rewrites the
    payload and record digests for every row. That means an externally tampered payload is
    silently re-blessed on the next open and can no longer be detected by `integrity_check()`.

    This check reads the database directly (no EvidenceStore, therefore no migration) and
    fails closed on any payload whose stored digest does not match its content. A drift
    verdict must never be produced from evidence that cannot be trusted.

    Returns a summary when the store is absent (nothing to verify) or intact.
    """
    path = Path(db_path)
    if not path.exists():
        return {"status": "absent", "checked": 0}

    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "snapshots" not in tables:
            return {"status": "absent", "checked": 0}
        rows = connection.execute(
            "SELECT id, payload_json, payload_sha256 FROM snapshots"
        ).fetchall()
    finally:
        connection.close()

    tampered = [
        row["id"]
        for row in rows
        if not row["payload_sha256"]
        or row["payload_sha256"] != _payload_sha256(row["payload_json"])
    ]
    if tampered:
        raise EvidenceIntegrityError(
            "evidence payload digest mismatch for snapshot id(s) "
            f"{tampered}; the store may have been tampered with or truncated"
        )
    return {"status": "ok", "checked": len(rows)}


class PageDrift:
    """Page-drift API backed by the canonical EvidenceStore."""

    def __init__(self, db_path: str | None = None, *, verify_integrity: bool = True) -> None:
        target = db_path or DEFAULT_DB
        if verify_integrity:
            verify_untampered(target)  # fail closed before migration can re-bless digests
        self._store = EvidenceStore(db_path) if db_path else EvidenceStore()
        try:
            self._store.integrity_check()
        except Exception:
            self._store.close()
            raise

    def capture(self, url: str, fields: dict[str, Any], **kwargs: Any) -> int:
        return self._store.record(url, METRIC_GROUP, fingerprint(fields), **kwargs)

    def compare(self, url: str) -> dict[str, Any]:
        result = self._store.compare(url, METRIC_GROUP)
        if result.get("status") != "ok":
            return result  # insufficient_history stays distinct from "no drift"

        drift = result.get("drift") or {}
        changes: list[dict[str, Any]] = []
        for pointer, delta in drift.items():
            field = str(pointer).lstrip("/").split("/")[0]
            if field not in _TRACKED:
                continue
            before, after = delta.get("before"), delta.get("after")
            changes.append(
                {
                    "field": field,
                    "severity": _severity(field, before, after),
                    "before": before,
                    "after": after,
                }
            )

        # An html-only change (no tracked field moved) is informational.
        counts = {
            level: sum(1 for c in changes if c["severity"] == level)
            for level in ("critical", "warning", "info")
        }
        return {
            "status": "ok",
            "url": result.get("url", url),
            "metric_group": METRIC_GROUP,
            "counts": counts,
            "changes": changes,
        }

    def history(self, url: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._store.latest(url, METRIC_GROUP, limit=limit)

    def close(self) -> None:
        self._store.close()

    def __enter__(self) -> "PageDrift":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
