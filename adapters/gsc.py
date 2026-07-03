"""Google Search Console adapter contract.

Live OAuth/API calls should implement this interface in production. The current
class intentionally supports saved exports so the repository remains runnable
without credentials.
"""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterNotConfigured, AdapterResult


class GSCExportAdapter:
    name = "gsc_export"

    def fetch(self, path: str = "", **_: object) -> AdapterResult:
        if not path:
            raise AdapterNotConfigured("Provide a GSC CSV export path or implement live OAuth fetching.")
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        clicks = sum(self._number(row.get("Clicks") or row.get("clicks")) for row in rows)
        impressions = sum(self._number(row.get("Impressions") or row.get("impressions")) for row in rows)
        return AdapterResult(
            source=path,
            status="ok",
            data={"row_count": len(rows), "clicks": clicks, "impressions": impressions},
            warnings=[],
        )

    @staticmethod
    def _number(value: str | None) -> int:
        try:
            return int(float(value or 0))
        except ValueError:
            return 0

