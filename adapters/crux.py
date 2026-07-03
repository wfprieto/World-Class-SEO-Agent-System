"""CrUX payload adapter for field Core Web Vitals data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.base import AdapterResult


class CrUXPayloadAdapter:
    name = "crux_payload"

    def fetch(self, path: str = "", payload: dict[str, Any] | None = None, **_: object) -> AdapterResult:
        data = payload or json.loads(Path(path).read_text(encoding="utf-8"))
        record = data.get("record", data)
        metrics = record.get("metrics", {})
        normalized = {
            "lcp": self._metric(metrics, "largest_contentful_paint"),
            "inp": self._metric(metrics, "interaction_to_next_paint"),
            "cls": self._metric(metrics, "cumulative_layout_shift"),
        }
        warnings = [name.upper() + " missing." for name, value in normalized.items() if value is None]
        return AdapterResult(source=path or "crux_payload", status="ok" if not warnings else "needs-review", data=normalized, warnings=warnings)

    @staticmethod
    def _metric(metrics: dict[str, Any], name: str) -> Any:
        metric = metrics.get(name)
        if not metric:
            return None
        return metric.get("percentiles", {}).get("p75") or metric.get("histogram")
