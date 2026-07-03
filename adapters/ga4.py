"""GA4 adapter contract and CSV export parser."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterNotConfigured, AdapterResult


class GA4ExportAdapter:
    name = "ga4_export"

    def fetch(self, path: str = "", **_: object) -> AdapterResult:
        if not path:
            raise AdapterNotConfigured("Provide a GA4 CSV export path or implement live GA4 API fetching.")
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        sessions = sum(self._number(row.get("Sessions") or row.get("sessions")) for row in rows)
        conversions = sum(self._number(row.get("Conversions") or row.get("conversions")) for row in rows)
        return AdapterResult(
            source=path,
            status="ok",
            data={"row_count": len(rows), "sessions": sessions, "conversions": conversions},
            warnings=[],
        )

    @staticmethod
    def _number(value: str | None) -> int:
        try:
            return int(float(value or 0))
        except ValueError:
            return 0

