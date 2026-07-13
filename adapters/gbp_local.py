"""Google Business Profile/local listing export adapter."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from adapters.base import AdapterResult


class GBPLocalAdapter:
    name = "gbp_local"

    def fetch(self, path: str, **_: object) -> AdapterResult:
        with Path(path).open(newline="", encoding="utf-8-sig") as handle:
            rows: list[dict[str, str | None]] = list(csv.DictReader(handle))
        warnings: list[str] = []
        missing_nap: list[dict[str, str | None]] = []
        duplicate_names: dict[str, int] = {}
        for row in rows:
            name = row.get("name") or ""
            duplicate_names[name] = duplicate_names.get(name, 0) + 1
            if not row.get("name") or not row.get("address") or not row.get("phone"):
                missing_nap.append(row)
        duplicates = [name for name, count in duplicate_names.items() if name and count > 1]
        if missing_nap:
            warnings.append(f"{len(missing_nap)} listings are missing NAP fields.")
        if duplicates:
            warnings.append(f"{len(duplicates)} duplicate listing names found.")
        data: dict[str, Any] = {
            "listing_count": len(rows),
            "missing_nap_count": len(missing_nap),
            "duplicate_names": duplicates,
        }
        return AdapterResult(
            source=path,
            status="ok" if not warnings else "needs-review",
            data=data,
            warnings=warnings,
        )
