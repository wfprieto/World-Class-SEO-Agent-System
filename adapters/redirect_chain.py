"""Redirect chain export adapter."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


class RedirectChainAdapter:
    name = "redirect_chain"

    def fetch(self, path: str, source_column: str = "source", target_column: str = "target", hops_column: str = "hops", **_: object) -> AdapterResult:
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        chains = []
        loops = []
        for row in rows:
            try:
                hops = int(row.get(hops_column, "0"))
            except ValueError:
                hops = 0
            if hops > 1:
                chains.append(row)
            if row.get(source_column) and row.get(source_column) == row.get(target_column):
                loops.append(row)
        warnings = []
        if chains:
            warnings.append(f"{len(chains)} redirect chains found.")
        if loops:
            warnings.append(f"{len(loops)} redirect loops found.")
        return AdapterResult(source=path, status="ok" if not warnings else "needs-review", data={"row_count": len(rows), "chain_count": len(chains), "loop_count": len(loops)}, warnings=warnings)
