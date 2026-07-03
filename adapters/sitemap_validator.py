"""XML sitemap validator adapter."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from adapters.base import AdapterResult


class SitemapValidatorAdapter:
    name = "sitemap_validator"

    def fetch(self, path: str = "", xml_text: str = "", **_: object) -> AdapterResult:
        source = path or "xml_text"
        text = xml_text or Path(path).read_text(encoding="utf-8")
        warnings: list[str] = []
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            return AdapterResult(source=source, status="invalid", data={"error": str(exc)}, warnings=["Invalid XML sitemap."])
        urls = [element.text or "" for element in root.iter() if element.tag.endswith("loc")]
        duplicates = sorted({url for url in urls if urls.count(url) > 1})
        if not urls:
            warnings.append("No <loc> URLs found.")
        if duplicates:
            warnings.append(f"{len(duplicates)} duplicate sitemap URLs found.")
        return AdapterResult(source=source, status="ok" if not warnings else "needs-review", data={"url_count": len(urls), "duplicates": duplicates, "urls": urls[:100]}, warnings=warnings)
