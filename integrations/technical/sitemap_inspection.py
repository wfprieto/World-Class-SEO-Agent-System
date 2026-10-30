"""Bounded sitemap classification and truthful partial evidence."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any

from contracts.adapter import AdapterResult
from integrations.technical.parsing import local_name
from security.url_safety import (
    PublicURLClassificationBudget,
    URLClassificationLimit,
    validate_public_url,
)


def _classify_sitemap_locations(locations: list[str]) -> tuple[list[str], list[str], list[str]]:
    safe: list[str] = []
    unsafe: list[str] = []
    unclassified: list[str] = []
    classifier = PublicURLClassificationBudget()
    for location in locations:
        try:
            safe.append(classifier.validate(location))
        except URLClassificationLimit:
            unclassified.append(location)
        except ValueError:
            unsafe.append(location)
    return safe, unsafe, unclassified


def _sitemap_warnings(kind: str, duplicates: list[str], unsafe: list[str], truncated: bool,
                      unclassified: list[str], locations: list[str], status: int) -> list[str]:
    messages = [
        (kind not in {'urlset', 'sitemapindex'}, f"Unexpected sitemap root element: {kind or 'unknown'}."),
        (bool(duplicates), f'{len(duplicates)} duplicate sitemap location(s) found.'),
        (bool(unsafe), f'{len(unsafe)} invalid or non-public sitemap location(s) found.'),
        (truncated, 'Sitemap exceeds the 50,000-location analysis ceiling; remaining entries were not analyzed.'),
        (bool(unclassified), 'Sitemap DNS classification ceiling reached; unclassified locations are partial evidence. One in-flight OS DNS call cannot be cancelled.'),
        (not locations, 'No sitemap <loc> elements were found.'),
        (not 200 <= status < 300, f'Sitemap returned HTTP {status}.'),
    ]
    return [message for applies, message in messages if applies]


def inspect_sitemap(http: Any, url: str, *, source: str) -> AdapterResult:
    safe = validate_public_url(url)
    hop = http.get(safe)
    try:
        root = ET.fromstring(hop.body)
    except ET.ParseError as exc:
        return AdapterResult(
            source=source,
            status="invalid",
            data={
                "operation": "sitemap",
                "url": safe,
                "status_code": hop.status_code,
                "data_state": "INVALID_RESPONSE",
                "error": str(exc),
            },
            warnings=["Sitemap response is not valid XML."],
        )
    kind = local_name(root.tag)
    locations = [
        (element.text or "").strip()
        for element in root.iter()
        if local_name(element.tag) == "loc"
        and (element.text or "").strip()
    ]
    truncated = len(locations) > 50_000
    analyzed = locations[:50_000]
    counts = Counter(analyzed)
    duplicates = sorted(
        location for location, count in counts.items() if count > 1
    )
    safe_locations, unsafe_locations, unclassified_locations = _classify_sitemap_locations(analyzed)
    warnings = _sitemap_warnings(kind, duplicates, unsafe_locations, truncated,
                                 unclassified_locations, locations, hop.status_code)
    return AdapterResult(
        source=source,
        status="ok" if not warnings else "needs-review",
        data={
            "operation": "sitemap",
            "url": safe,
            "final_url": hop.final_url,
            "status_code": hop.status_code,
            "kind": kind,
            "url_count": len(locations),
            "analyzed_count": len(analyzed),
            "locations": safe_locations[:1000],
            "duplicates": duplicates,
            "unsafe_locations": unsafe_locations,
            "unclassified_locations": unclassified_locations[:1000],
            "unclassified_count": len(unclassified_locations),
            "truncated": truncated,
            "data_state": "PARTIAL" if unclassified_locations or truncated else ("AVAILABLE" if locations else "EMPTY"),
            "request_metadata": {"elapsed_ms": hop.elapsed_ms},
        },
        warnings=warnings,
    )
