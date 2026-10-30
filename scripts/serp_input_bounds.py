"""Bound imported SERP bytes and rows before pairwise clustering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_KEYWORDS = 1000
MAX_RESULTS_PER_KEYWORD = 100
MAX_VALUE_CHARACTERS = 4096
MAX_EDGES = 100_000


def check_edge_count(count: int) -> None:
    if count >= MAX_EDGES:
        raise ValueError("SERP edge count limit exceeded")


def load_json(path: str) -> Any:
    """Read JSON tolerating a UTF-8 BOM (common in Windows exports)."""
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("SERP input byte limit exceeded")
    return json.loads(raw.decode("utf-8-sig"))


def _value_size(value: str) -> int:
    if not isinstance(value, str):
        raise TypeError("SERP keywords and result URLs must be strings")
    if len(value) > MAX_VALUE_CHARACTERS:
        raise ValueError("SERP value length limit exceeded")
    return len(value.encode("utf-8"))


def bounded_result_sets(serps: dict[str, list[str]]) -> dict[str, set[str]]:
    if len(serps) > MAX_KEYWORDS:
        raise ValueError("SERP keyword count limit exceeded")
    sets: dict[str, set[str]] = {}
    size = 0
    for keyword, supplied in serps.items():
        size += _value_size(keyword)
        rows = supplied or []
        if not isinstance(rows, (list, tuple)):
            raise TypeError("SERP result rows must be lists of URLs")
        if len(rows) > MAX_RESULTS_PER_KEYWORD:
            raise ValueError("SERP results per keyword limit exceeded")
        size += sum(_value_size(value) for value in rows if value)
        if size > MAX_INPUT_BYTES:
            raise ValueError("SERP input byte limit exceeded")
        sets[keyword] = {value for value in rows if value}
    return sets
