"""Backlink CSV adapter."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


class BacklinkCSVAdapter:
    name = "backlink_csv"

    def fetch(self, path: str, domain_column: str = "referring_domain", anchor_column: str = "anchor", **_: object) -> AdapterResult:
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        domains = {row.get(domain_column, "") for row in rows if row.get(domain_column)}
        anchors: dict[str, int] = {}
        for row in rows:
            anchor = row.get(anchor_column, "") or "(empty)"
            anchors[anchor] = anchors.get(anchor, 0) + 1
        return AdapterResult(
            source=path,
            status="ok",
            data={"backlink_count": len(rows), "referring_domain_count": len(domains), "top_anchors": anchors},
            warnings=[],
        )

