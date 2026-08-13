"""Extract normalized link evidence from parsed HTML."""
from __future__ import annotations

import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field

SKIPPED_LINK_RELS = {"stylesheet", "preload", "modulepreload", "icon"}


@dataclass
class LinkEvidence:
    internal: set[str] = field(default_factory=set)
    external: set[str] = field(default_factory=set)
    rel_next: set[str] = field(default_factory=set)
    rel_prev: set[str] = field(default_factory=set)
    canonical: str | None = None


def extract_link_evidence(
    links: list[dict[str, str]],
    base_url: str,
    root_host: str,
    normalize: Callable[[str], str],
) -> LinkEvidence:
    evidence = LinkEvidence()
    for link in links:
        href = link.get("href", "").strip()
        if not href:
            continue
        absolute = normalize(urllib.parse.urljoin(base_url, href))
        relation = {part.lower() for part in link.get("rel", "").split()}
        if "canonical" in relation and evidence.canonical is None:
            evidence.canonical = absolute
        if "next" in relation:
            evidence.rel_next.add(absolute)
        if "prev" in relation:
            evidence.rel_prev.add(absolute)
        if link.get("rel", "").lower() not in SKIPPED_LINK_RELS:
            _add_navigation_link(evidence, absolute, root_host)
    return evidence


def _add_navigation_link(evidence: LinkEvidence, absolute: str, root_host: str) -> None:
    parsed = urllib.parse.urlsplit(absolute)
    if parsed.hostname == root_host:
        evidence.internal.add(absolute)
    elif parsed.scheme in {"http", "https"}:
        evidence.external.add(absolute)
