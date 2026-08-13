"""Redirect chain export adapter."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


def _hops(row: dict[str, str], column: str) -> int:
    try:
        return int(row.get(column, "0"))
    except ValueError:
        return 0


def _is_skipped(row: dict[str, str]) -> bool:
    return str(row.get("skipped", "")).lower() == "true" or row.get("status") == "skipped"


class RedirectChainAdapter:
    name = "redirect_chain"

    def fetch(
        self,
        path: str,
        source_column: str = "source",
        target_column: str = "target",
        hops_column: str = "hops",
        **_: object,
    ) -> AdapterResult:
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        chains = [row for row in rows if _hops(row, hops_column) > 1]
        loops = [row for row in rows if row.get(source_column) == row.get(target_column)]
        skipped = [row for row in rows if _is_skipped(row)]
        blocked = [row for row in rows if row.get("status") == "robots_blocked"]
        warnings = []
        if chains:
            warnings.append(f"{len(chains)} redirect chains found.")
        if loops:
            warnings.append(f"{len(loops)} redirect loops found.")
        if skipped:
            warnings.append(f"{len(skipped)} redirect rows skipped.")
        if blocked:
            warnings.append(f"{len(blocked)} redirect rows blocked by robots policy.")
        return AdapterResult(
            source=path,
            status="ok" if not warnings else "needs-review",
            data={
                "row_count": len(rows),
                "chain_count": len(chains),
                "loop_count": len(loops),
                "skipped_count": len(skipped),
                "blocked_count": len(blocked),
            },
            warnings=warnings,
        )
