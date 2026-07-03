"""Rank tracking CSV adapter."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


class RankTrackingCSVAdapter:
    name = "rank_tracking_csv"

    def fetch(self, path: str, keyword_column: str = "keyword", rank_column: str = "rank", **_: object) -> AdapterResult:
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        ranks = []
        for row in rows:
            try:
                ranks.append(int(row.get(rank_column, "0")))
            except ValueError:
                continue
        data = {
            "keyword_count": len(rows),
            "ranked_count": len(ranks),
            "average_rank": round(sum(ranks) / len(ranks), 2) if ranks else None,
            "top_10_count": len([rank for rank in ranks if rank <= 10]),
            "keywords": [row.get(keyword_column, "") for row in rows if row.get(keyword_column)],
        }
        return AdapterResult(source=path, status="ok", data=data, warnings=[])

