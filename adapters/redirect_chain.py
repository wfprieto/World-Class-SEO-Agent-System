"""Redirect chain export adapter."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


class RedirectChainAdapter:
    name = "redirect_chain"

    def fetch(
        self,
        path: str,
        source_column: str = "source",
        target_column: str = "target",
        hops_column: str = "hops",
        status_column: str = "status",
        skipped_column: str = "skipped",
        **_: object,
    ) -> AdapterResult:
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        chains = []
        loops = []
        skipped = []
        blocked = []
        for row in rows:
            try:
                hops = int(row.get(hops_column, "0"))
            except ValueError:
                hops = 0
            if hops > 1:
                chains.append(row)
            if row.get(source_column) and row.get(source_column) == row.get(target_column):
                loops.append(row)
            status = (row.get(status_column) or "").strip().lower()
            skipped_state = (row.get(skipped_column) or "").strip().lower()
            if skipped_state in {"true", "1", "yes"} or status in {"skipped", "not_checked"}:
                skipped.append(row)
            if status in {"robots_blocked", "auth_required", "blocked"}:
                blocked.append(row)
        warnings = []
        if chains:
            warnings.append(f"{len(chains)} redirect chains found.")
        if loops:
            warnings.append(f"{len(loops)} redirect loops found.")
        if skipped:
            warnings.append(f"{len(skipped)} redirect rows were skipped or not checked.")
        if blocked:
            warnings.append(f"{len(blocked)} redirect rows were blocked by policy or access.")
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
