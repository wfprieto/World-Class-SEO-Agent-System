"""Google Business Profile/local listing export adapter."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


class GBPLocalAdapter:
    name = "gbp_local"

    def fetch(self, path: str, **_: object) -> AdapterResult:
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        warnings = []
        missing_nap = []
        duplicate_names = {}
        for row in rows:
            name = row.get("name", "")
            duplicate_names[name] = duplicate_names.get(name, 0) + 1
            if not row.get("name") or not row.get("address") or not row.get("phone"):
                missing_nap.append(row)
        duplicates = [name for name, count in duplicate_names.items() if name and count > 1]
        if missing_nap:
            warnings.append(f"{len(missing_nap)} listings are missing NAP fields.")
        if duplicates:
            warnings.append(f"{len(duplicates)} duplicate listing names found.")
        return AdapterResult(source=path, status="ok" if not warnings else "needs-review", data={"listing_count": len(rows), "missing_nap_count": len(missing_nap), "duplicate_names": duplicates}, warnings=warnings)
