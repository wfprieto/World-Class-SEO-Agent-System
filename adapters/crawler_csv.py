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
        headers = list(rows[0].keys()) if rows else []
        resolved_url_column = self._resolve_column(headers, [url_column, "Address", "URL", "url", "page"])
        resolved_status_column = self._resolve_column(headers, [status_column, "Status Code", "status", "Status", "http_status"])
        if rows and not resolved_url_column:
            warnings.append(f"URL column '{url_column}' not found.")
        if rows and not resolved_status_column:
            warnings.append(f"Status column '{status_column}' not found.")
        summary = {
            "row_count": len(rows),
            "urls": [row.get(resolved_url_column, "") for row in rows if resolved_url_column and row.get(resolved_url_column)],
            "status_counts": self._status_counts(rows, resolved_status_column),
        }
        return AdapterResult(source=path, status="ok", data=summary, warnings=warnings)

    @staticmethod
    def _resolve_column(headers: list[str], candidates: list[str]) -> str:
        normalized = {header.lower().strip(): header for header in headers}
        for candidate in candidates:
            match = normalized.get(candidate.lower().strip())
            if match:
                return match
        return ""

    @staticmethod
    def _status_counts(rows: list[dict[str, str]], status_column: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            status = row.get(status_column, "unknown") if status_column else "unknown"
            status = status or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts
