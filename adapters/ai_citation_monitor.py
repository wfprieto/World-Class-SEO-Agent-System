"""AI citation monitoring export adapter."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


class AICitationMonitorAdapter:
    name = "ai_citation_monitor"

    def fetch(self, path: str, brand_column: str = "brand", cited_column: str = "cited", **_: object) -> AdapterResult:
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        cited_rows = [row for row in rows if str(row.get(cited_column, "")).lower() in {"true", "1", "yes"}]
        brands = sorted({row.get(brand_column, "") for row in cited_rows if row.get(brand_column)})
        warnings = [] if cited_rows else ["No AI citations found in supplied sample."]
        return AdapterResult(source=path, status="ok" if cited_rows else "needs-review", data={"prompt_count": len(rows), "citation_count": len(cited_rows), "cited_brands": brands}, warnings=warnings)
