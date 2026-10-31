"""Decode operator-supplied intelligence JSON, without live providers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))
