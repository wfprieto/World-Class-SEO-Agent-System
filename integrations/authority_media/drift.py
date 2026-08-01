"""Persistent page-drift operations backed by the canonical evidence store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.base import AdapterResult
from adapters.evidence_store import canonicalize_url
from adapters.page_drift import PageDrift

MAX_STATE_BYTES = 10_000_000


class DriftService:
    """Capture and compare bounded page-state snapshots in the evidence store."""

    ALLOWED_FIELDS = {"title", "canonical", "robots", "h1", "status_code", "html", "schema_json"}

    @classmethod
    def _state_file(cls, path: str) -> dict[str, Any]:
        target = Path(path)
        if target.stat().st_size > MAX_STATE_BYTES:
            raise ValueError(f"input exceeds {MAX_STATE_BYTES} bytes")
        payload = json.loads(target.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("state file must contain a JSON object")
        unknown = sorted(set(payload) - cls.ALLOWED_FIELDS)
        if unknown:
            raise ValueError("unsupported state fields: " + ", ".join(unknown))
        return payload

    def baseline(self, url: str, state_path: str, *, db_path: str | None = None) -> AdapterResult:
        fields = self._state_file(state_path)
        with PageDrift(db_path) as drift:
            snapshot_id = drift.capture(url, fields, source=state_path, status="ok")
        return AdapterResult(
            source=state_path,
            status="ok",
            data={
                "data_state": "AVAILABLE",
                "url": canonicalize_url(url),
                "snapshot_id": snapshot_id,
                "action": "baseline_recorded",
            },
            warnings=[],
        )

    def compare(self, url: str, *, db_path: str | None = None) -> AdapterResult:
        with PageDrift(db_path) as drift:
            result = drift.compare(url)
        status = "ok" if result.get("status") == "ok" else "partial"
        data_state = "AVAILABLE" if status == "ok" else "PARTIAL"
        return AdapterResult("evidence_store", status, {"data_state": data_state, **result}, [])

    def history(self, url: str, *, db_path: str | None = None, limit: int = 20) -> AdapterResult:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be from 1 to 1000")
        with PageDrift(db_path) as drift:
            rows = drift.history(url, limit=limit)
        status = "ok" if rows else "empty"
        data_state = "AVAILABLE" if status == "ok" else "EMPTY"
        return AdapterResult(
            "evidence_store",
            status,
            {
                "data_state": data_state,
                "url": canonicalize_url(url),
                "history": rows,
                "count": len(rows),
            },
            [],
        )

    def report(
        self,
        url: str,
        *,
        db_path: str | None = None,
        output_path: str | None = None,
    ) -> AdapterResult:
        result = self.compare(url, db_path=db_path)
        written = None
        if output_path:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result.data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            written = str(target)
        result.data["report_path"] = written
        result.warnings.append("The report reflects only stored snapshots and is not an ongoing monitor.")
        return result

    def watch(self, url: str, state_path: str, *, db_path: str | None = None) -> AdapterResult:
        fields = self._state_file(state_path)
        with PageDrift(db_path) as drift:
            snapshot_id = drift.capture(url, fields, source=state_path, status="ok")
            result = drift.compare(url)
        status = "ok" if result.get("status") == "ok" else "partial"
        data_state = "AVAILABLE" if status == "ok" else "PARTIAL"
        return AdapterResult(
            source=state_path,
            status=status,
            data={"data_state": data_state, "snapshot_id": snapshot_id, "one_shot": True, **result},
            warnings=[
                "drift watch performs one bounded capture-and-compare; it does not create a background schedule."
            ],
        )
