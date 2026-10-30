"""XML sitemap validator adapter."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from io import StringIO
from pathlib import Path

from adapters.base import AdapterResult

# Sitemap protocol ceilings; reject excess rather than silently returning partial evidence.
MAX_SITEMAP_BYTES = 50 * 1024 * 1024
MAX_SITEMAP_LOCATIONS = 50_000


def _bounded_text(path: str, xml_text: str) -> str:
    if xml_text:
        if len(xml_text) > MAX_SITEMAP_BYTES or len(xml_text.encode("utf-8")) > MAX_SITEMAP_BYTES:
            raise ValueError("Sitemap byte limit exceeded.")
        return xml_text
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_SITEMAP_BYTES + 1)
    if len(raw) > MAX_SITEMAP_BYTES:
        raise ValueError("Sitemap byte limit exceeded.")
    return raw.decode("utf-8")


def _locations(text: str) -> tuple[int, list[str], list[str]]:
    counts: Counter[str] = Counter()
    sample: list[str] = []
    count = 0
    for _, element in ET.iterparse(StringIO(text), events=("end",)):
        if element.tag.endswith("loc"):
            count += 1
            if count > MAX_SITEMAP_LOCATIONS:
                raise ValueError("Sitemap location limit exceeded.")
            value = element.text or ""
            counts[value] += 1
            if len(sample) < 100:
                sample.append(value)
        element.clear()
    return count, sorted(value for value, occurrences in counts.items() if occurrences > 1), sample


class SitemapValidatorAdapter:
    name = "sitemap_validator"

    def fetch(self, path: str = "", xml_text: str = "", **_: object) -> AdapterResult:
        source = path or "xml_text"
        warnings: list[str] = []
        try:
            count, duplicates, sample = _locations(_bounded_text(path, xml_text))
        except (ET.ParseError, ValueError) as exc:
            return AdapterResult(source=source, status="invalid", data={"error": str(exc)}, warnings=["Invalid XML sitemap."])
        if not count:
            warnings.append("No <loc> URLs found.")
        if duplicates:
            warnings.append(f"{len(duplicates)} duplicate sitemap URLs found.")
        return AdapterResult(source=source, status="ok" if not warnings else "needs-review", data={"url_count": count, "duplicates": duplicates, "urls": sample}, warnings=warnings)
