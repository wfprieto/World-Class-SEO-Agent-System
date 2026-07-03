"""Lightweight accessibility export and HTML checker."""

from __future__ import annotations

import json
import re
from pathlib import Path

from adapters.base import AdapterResult


class AccessibilityCheckerAdapter:
    name = "accessibility_checker"

    def fetch(self, path: str = "", html: str = "", **_: object) -> AdapterResult:
        source = path or "html"
        text = html or Path(path).read_text(encoding="utf-8")
        if path.endswith(".json"):
            data = json.loads(text)
            violations = data.get("violations", [])
            warnings = [f"{len(violations)} accessibility violations found."] if violations else []
            return AdapterResult(source=source, status="ok" if not warnings else "needs-review", data={"violation_count": len(violations)}, warnings=warnings)
        img_count = len(re.findall(r"<img\b", text, re.IGNORECASE))
        missing_alt = len(re.findall(r"<img\b(?![^>]*\balt=)", text, re.IGNORECASE))
        h1_count = len(re.findall(r"<h1\b", text, re.IGNORECASE))
        warnings = []
        if missing_alt:
            warnings.append(f"{missing_alt} images are missing alt attributes.")
        if h1_count != 1:
            warnings.append(f"Expected 1 H1, found {h1_count}.")
        return AdapterResult(source=source, status="ok" if not warnings else "needs-review", data={"image_count": img_count, "missing_alt_count": missing_alt, "h1_count": h1_count}, warnings=warnings)
