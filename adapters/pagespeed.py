"""PageSpeed Insights payload adapter.

This adapter parses saved PageSpeed/Lighthouse JSON. Live API fetching belongs
behind the same normalized result contract once credentials/quotas are provided.
"""

from __future__ import annotations

import json
from pathlib import Path

from adapters.base import AdapterResult


class PageSpeedPayloadAdapter:
    name = "pagespeed_payload"

    def fetch(self, path: str, **_: object) -> AdapterResult:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        lighthouse = data.get("lighthouseResult", {})
        categories = lighthouse.get("categories", {})
        audits = lighthouse.get("audits", {})
        metrics = {
            "performance_score": self._score(categories.get("performance", {}).get("score")),
            "accessibility_score": self._score(categories.get("accessibility", {}).get("score")),
            "seo_score": self._score(categories.get("seo", {}).get("score")),
            "lcp": audits.get("largest-contentful-paint", {}).get("displayValue"),
            "cls": audits.get("cumulative-layout-shift", {}).get("displayValue"),
            "inp": audits.get("experimental-interaction-to-next-paint", {}).get("displayValue")
            or audits.get("interaction-to-next-paint", {}).get("displayValue"),
        }
        return AdapterResult(source=path, status="ok", data=metrics, warnings=[])

    @staticmethod
    def _score(value: float | int | None) -> int | None:
        if value is None:
            return None
        return round(float(value) * 100)

