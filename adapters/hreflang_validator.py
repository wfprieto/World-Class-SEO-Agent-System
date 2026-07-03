"""Hreflang validation adapter for exported alternate URL rows."""

from __future__ import annotations

import csv
from pathlib import Path

from adapters.base import AdapterResult


class HreflangValidatorAdapter:
    name = "hreflang_validator"

    def fetch(self, path: str, source_column: str = "source", target_column: str = "target", lang_column: str = "hreflang", **_: object) -> AdapterResult:
        rows = list(csv.DictReader(Path(path).open(newline="", encoding="utf-8-sig")))
        pairs = {(row.get(source_column, ""), row.get(target_column, "")) for row in rows}
        missing_return = []
        invalid_lang = []
        for row in rows:
            source = row.get(source_column, "")
            target = row.get(target_column, "")
            lang = row.get(lang_column, "")
            if target and source and (target, source) not in pairs and target != source:
                missing_return.append({"source": source, "target": target, "hreflang": lang})
            if lang and lang != "x-default" and len(lang.split("-")[0]) != 2:
                invalid_lang.append({"source": source, "target": target, "hreflang": lang})
        warnings = []
        if missing_return:
            warnings.append(f"{len(missing_return)} hreflang rows lack return links.")
        if invalid_lang:
            warnings.append(f"{len(invalid_lang)} hreflang rows have suspicious language codes.")
        return AdapterResult(source=path, status="ok" if not warnings else "needs-review", data={"row_count": len(rows), "missing_return": missing_return, "invalid_lang": invalid_lang}, warnings=warnings)
