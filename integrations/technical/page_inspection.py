"""Pure HTML-page inspection after the canonical bounded fetch."""

from __future__ import annotations

import re
import urllib.parse
from collections import Counter
from typing import Any

from contracts.adapter import AdapterResult
from integrations.technical.http import HttpHop
from integrations.technical.parsing import PageParser, directive_tokens, header_value, tokens
from security.url_safety import validate_public_url

_BCP47 = re.compile(
    r"^(?:[A-Za-z]{2,3}(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|\d{3}))?"
    r"(?:-[A-Za-z0-9]{5,8}|-\d[A-Za-z0-9]{3})*|x-default)$"
)


def inspect_hreflang(name: str, safe: str, hop: HttpHop, parser: PageParser) -> AdapterResult:
    alternates, invalid_codes, invalid_targets = _alternates(hop, parser)
    duplicate_codes = sorted(
        code
        for code, count in Counter(item["hreflang"].lower() for item in alternates).items()
        if count > 1
    )
    warnings: list[str] = []
    if invalid_codes:
        warnings.append(
            f"{len(invalid_codes)} hreflang value(s) failed the bounded BCP-47 format check."
        )
    if invalid_targets:
        warnings.append(f"{len(invalid_targets)} hreflang target(s) are invalid or non-public.")
    if duplicate_codes:
        warnings.append("Duplicate hreflang codes found: " + ", ".join(duplicate_codes))
    if not alternates:
        warnings.append("No HTML hreflang alternates were found.")
    return AdapterResult(
        source=name,
        status="ok" if not warnings else "needs-review",
        data={
            "operation": "hreflang",
            "url": safe,
            "final_url": hop.final_url,
            "status_code": hop.status_code,
            "alternates": alternates,
            "alternate_count": len(alternates),
            "has_x_default": any(item["hreflang"].lower() == "x-default" for item in alternates),
            "invalid_language_codes": invalid_codes,
            "invalid_targets": invalid_targets,
            "duplicate_language_codes": duplicate_codes,
            "data_state": "AVAILABLE" if alternates else "EMPTY",
            "limitations": [
                "A single-page inspection cannot prove reciprocal return links across alternate pages.",
                "HTTP-header and XML-sitemap hreflang annotations are outside this HTML result.",
            ],
        },
        warnings=warnings,
    )


def inspect_preload(name: str, safe: str, hop: HttpHop, parser: PageParser) -> AdapterResult:
    preloads, warnings = _preloads(hop, parser)
    high_priority_images = [
        item for item in preloads if item["as"] == "image" and item["fetchpriority"] == "high"
    ]
    return AdapterResult(
        source=name,
        status="ok" if not warnings else "needs-review",
        data={
            "operation": "preload",
            "url": safe,
            "final_url": hop.final_url,
            "status_code": hop.status_code,
            "preloads": preloads,
            "preload_count": len(preloads),
            "high_priority_image_count": len(high_priority_images),
            "data_state": "AVAILABLE" if preloads else "EMPTY",
            "limitations": [
                "Markup presence does not prove that a preload was useful or timely.",
                "Performance impact requires browser or field evidence.",
            ],
        },
        warnings=warnings,
    )


def inspect_indexability(name: str, safe: str, hop: HttpHop, parser: PageParser) -> AdapterResult:
    header_robots, meta_values, header_directives, meta_directives, canonicals = _indexability_tags(
        hop, parser
    )
    directives = header_directives | meta_directives
    blocking: list[str] = []
    if not 200 <= hop.status_code < 300:
        blocking.append(f"http_status_{hop.status_code}")
    if {"noindex", "none"} & meta_directives:
        blocking.append("meta_robots_noindex")
    if {"noindex", "none"} & header_directives:
        blocking.append("x_robots_tag_noindex")
    if len(canonicals) > 1:
        blocking.append("multiple_html_canonicals")
    canonical = canonicals[0] if len(canonicals) == 1 else None
    canonical_public: bool | None = None
    if canonical:
        try:
            canonical = validate_public_url(canonical)
            canonical_public = True
        except ValueError:
            canonical_public = False
            blocking.append("invalid_or_non_public_canonical")
    indexable = not blocking
    return AdapterResult(
        source=name,
        status="ok" if indexable else "needs-review",
        data={
            "operation": "indexability",
            "url": safe,
            "final_url": hop.final_url,
            "status_code": hop.status_code,
            "x_robots_tag": header_robots or None,
            "meta_robots": meta_values,
            "directives": sorted(directives),
            "canonical": canonical,
            "canonical_public": canonical_public,
            "canonical_count": len(canonicals),
            "indexable": indexable,
            "blocking_reasons": blocking,
            "data_state": "AVAILABLE",
            "limitations": [
                "This is a technical eligibility assessment, not proof that Google indexed or will index the URL.",
                "Robots.txt crawl rules and Google index state require separate evidence.",
            ],
        },
        warnings=[f"Technical indexability blocker: {reason}." for reason in blocking],
    )


def _alternates(
    hop: HttpHop, parser: PageParser
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    alternates: list[dict[str, Any]] = []
    invalid_codes: list[str] = []
    invalid_targets: list[str] = []
    for link in parser.links:
        rel = tokens(link.get("rel"))
        language = link.get("hreflang", "").strip()
        href = link.get("href", "").strip()
        if "alternate" not in rel or not language:
            continue
        resolved = urllib.parse.urljoin(hop.final_url, href) if href else ""
        valid_code = bool(_BCP47.fullmatch(language))
        if not valid_code:
            invalid_codes.append(language)
        try:
            target = validate_public_url(resolved)
            target_public = True
        except ValueError:
            target = resolved
            target_public = False
            invalid_targets.append(resolved)
        alternates.append(
            {
                "hreflang": language,
                "href": target,
                "language_code_valid": valid_code,
                "target_public": target_public,
            }
        )

    return alternates, invalid_codes, invalid_targets


def _preloads(hop: HttpHop, parser: PageParser) -> tuple[list[dict[str, Any]], list[str]]:
    preloads: list[dict[str, Any]] = []
    warnings: list[str] = []
    for link in parser.links:
        rel = tokens(link.get("rel"))
        if not ({"preload", "modulepreload"} & rel):
            continue
        href = link.get("href", "").strip()
        resolved = urllib.parse.urljoin(hop.final_url, href) if href else ""
        item = {
            "rel": sorted(rel),
            "href": resolved,
            "as": link.get("as") or None,
            "type": link.get("type") or None,
            "media": link.get("media") or None,
            "crossorigin": link.get("crossorigin") or None,
            "fetchpriority": ((link.get("fetchpriority") or "").lower() or None),
        }
        preloads.append(item)
        if not href:
            warnings.append("A preload declaration is missing href.")
        if "preload" in rel and not item["as"]:
            warnings.append(f"Preload {resolved or '[missing href]'} is missing an 'as' value.")

    return preloads, warnings


def _indexability_tags(
    hop: HttpHop, parser: PageParser
) -> tuple[str, list[str], set[str], set[str], list[str]]:
    header_robots = header_value(hop.headers, "x-robots-tag") or ""
    meta_values = [
        meta.get("content", "")
        for meta in parser.metas
        if meta.get("name", "").lower() in {"robots", "googlebot", "googlebot-news"}
    ]
    header_directives = directive_tokens([header_robots])
    meta_directives = directive_tokens(meta_values)
    canonicals = [
        urllib.parse.urljoin(hop.final_url, link["href"])
        for link in parser.links
        if "canonical" in tokens(link.get("rel")) and link.get("href")
    ]

    return header_robots, meta_values, header_directives, meta_directives, canonicals
