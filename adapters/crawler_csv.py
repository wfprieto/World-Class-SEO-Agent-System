"""Crawler CSV parser for Screaming Frog, Sitebulb, Lumar, or custom crawls."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


class CrawlerCSVAdapter:
    name = "crawler_csv"

    def fetch(self, path: str, url_column: str = "Address", status_column: str = "Status Code", **_: object) -> AdapterResult:
        rows: list[dict[str, str]] = []
        warnings: list[str] = []
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append(row)
        if rows and url_column not in rows[0]:
            warnings.append(f"URL column '{url_column}' not found.")
        if rows and status_column not in rows[0]:
            warnings.append(f"Status column '{status_column}' not found.")
        summary = {
            "row_count": len(rows),
            "urls": [row.get(url_column, "") for row in rows if row.get(url_column)],
            "status_counts": self._status_counts(rows, status_column),
        }
        return AdapterResult(source=path, status="ok", data=summary, warnings=warnings)

    @staticmethod
    def _status_counts(rows: list[dict[str, str]], status_column: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            status = row.get(status_column, "unknown") or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts

