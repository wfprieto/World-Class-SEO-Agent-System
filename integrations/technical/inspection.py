"""Technical SEO inspection operations built on bounded public evidence."""

from __future__ import annotations

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

from adapters.base import AdapterResult
from adapters.google_pagespeed_live import GooglePageSpeedLiveAdapter
from adapters.url_safety import validate_public_url
from integrations.technical.http import BoundedHttpClient, HttpHop
from integrations.technical.parsing import (
    SUPPORTED_SCHEMA,
    PageParser,
    cwv_metrics,
    decode_http_body,
    directive_tokens,
    header_value,
    is_missing,
    local_name,
    parse_jsonld_scripts,
    parse_robots,
    performance_score,
    schema_types,
    tokens,
    type_values,
)

_BCP47 = re.compile(
    r"^(?:[A-Za-z]{2,3}(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|\d{3}))?"
    r"(?:-[A-Za-z0-9]{5,8}|-\d[A-Za-z0-9]{3})*|x-default)$"
)
class TechnicalInspectionService:
    name = "technical_inspection"

    def __init__(
        self,
        *,
        http: Any | None = None,
        pagespeed: GooglePageSpeedLiveAdapter | None = None,
    ) -> None:
        self.http = http or BoundedHttpClient()
        self.pagespeed = pagespeed

    def robots(self, url: str, **_: Any) -> AdapterResult:
        safe = validate_public_url(url)
        parsed = urllib.parse.urlsplit(safe)
        robots_url = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, "/robots.txt", "", "")
        )
        hop = self.http.get(robots_url)
        text = decode_http_body(hop)
        groups, sitemaps, unknown = parse_robots(text)
        warnings: list[str] = []
        if hop.status_code == 404:
            warnings.append(
                "robots.txt was not found; this is not equivalent to a crawl block."
            )
        elif not 200 <= hop.status_code < 300:
            warnings.append(f"robots.txt returned HTTP {hop.status_code}.")
        if unknown:
            warnings.append(
                f"{len(unknown)} unrecognized robots.txt directive line(s) were preserved."
            )
        return AdapterResult(
            source=self.name,
            status="ok" if not warnings else "needs-review",
            data={
                "operation": "robots",
                "requested_url": robots_url,
                "final_url": hop.final_url,
                "status_code": hop.status_code,
                "groups": groups,
                "group_count": len(groups),
                "sitemaps": sitemaps,
                "unknown_directives": unknown,
                "data_state": "AVAILABLE" if text else "EMPTY",
                "request_metadata": {"elapsed_ms": hop.elapsed_ms},
                "limitations": [
                    "The parser reports directives and does not claim how every crawler implements them.",
                    "Robots rules govern crawling, not guaranteed removal from an index.",
                ],
            },
            warnings=warnings,
        )

    def sitemap(self, url: str, **_: Any) -> AdapterResult:
        safe = validate_public_url(url)
        hop = self.http.get(safe)
        try:
            root = ET.fromstring(hop.body)
        except ET.ParseError as exc:
            return AdapterResult(
                source=self.name,
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
        safe_locations: list[str] = []
        unsafe_locations: list[str] = []
        for location in analyzed:
            try:
                safe_locations.append(validate_public_url(location))
            except ValueError:
                unsafe_locations.append(location)
        warnings: list[str] = []
        if kind not in {"urlset", "sitemapindex"}:
            warnings.append(f"Unexpected sitemap root element: {kind or 'unknown'}.")
        if duplicates:
            warnings.append(
                f"{len(duplicates)} duplicate sitemap location(s) found."
            )
        if unsafe_locations:
            warnings.append(
                f"{len(unsafe_locations)} invalid or non-public sitemap location(s) found."
            )
        if truncated:
            warnings.append(
                "Sitemap exceeds the 50,000-location analysis ceiling; remaining entries were not analyzed."
            )
        if not locations:
            warnings.append("No sitemap <loc> elements were found.")
        if not 200 <= hop.status_code < 300:
            warnings.append(f"Sitemap returned HTTP {hop.status_code}.")
        return AdapterResult(
            source=self.name,
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
                "truncated": truncated,
                "data_state": "AVAILABLE" if locations else "EMPTY",
                "request_metadata": {"elapsed_ms": hop.elapsed_ms},
            },
            warnings=warnings,
        )

    def hreflang(self, url: str, **_: Any) -> AdapterResult:
        safe, hop, parser = self._page(url)
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
        duplicate_codes = sorted(
            code
            for code, count in Counter(
                item["hreflang"].lower() for item in alternates
            ).items()
            if count > 1
        )
        warnings: list[str] = []
        if invalid_codes:
            warnings.append(
                f"{len(invalid_codes)} hreflang value(s) failed the bounded BCP-47 format check."
            )
        if invalid_targets:
            warnings.append(
                f"{len(invalid_targets)} hreflang target(s) are invalid or non-public."
            )
        if duplicate_codes:
            warnings.append(
                "Duplicate hreflang codes found: " + ", ".join(duplicate_codes)
            )
        if not alternates:
            warnings.append("No HTML hreflang alternates were found.")
        return AdapterResult(
            source=self.name,
            status="ok" if not warnings else "needs-review",
            data={
                "operation": "hreflang",
                "url": safe,
                "final_url": hop.final_url,
                "status_code": hop.status_code,
                "alternates": alternates,
                "alternate_count": len(alternates),
                "has_x_default": any(
                    item["hreflang"].lower() == "x-default"
                    for item in alternates
                ),
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

    def preload(self, url: str, **_: Any) -> AdapterResult:
        safe, hop, parser = self._page(url)
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
                "fetchpriority": (
                    (link.get("fetchpriority") or "").lower() or None
                ),
            }
            preloads.append(item)
            if not href:
                warnings.append("A preload declaration is missing href.")
            if "preload" in rel and not item["as"]:
                warnings.append(
                    f"Preload {resolved or '[missing href]'} is missing an 'as' value."
                )
        high_priority_images = [
            item
            for item in preloads
            if item["as"] == "image" and item["fetchpriority"] == "high"
        ]
        return AdapterResult(
            source=self.name,
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

    def redirect_chain(
        self,
        url: str,
        max_redirects: int = 10,
        **_: Any,
    ) -> AdapterResult:
        chain = self.http.redirect_chain(url, max_redirects=max_redirects)
        warnings: list[str] = []
        if chain["loop_detected"]:
            warnings.append("Redirect loop detected.")
        if chain["limit_reached"]:
            warnings.append("Redirect chain reached the configured hop ceiling.")
        if chain["blocked_target"]:
            warnings.append(
                "Redirect target was blocked by canonical public-URL safety."
            )
        if chain["hop_count"] > 2:
            warnings.append(
                f"Redirect chain contains {chain['hop_count']} HTTP responses."
            )
        status = "ok" if not warnings else (
            "blocked" if chain["data_state"] == "BLOCKED" else "needs-review"
        )
        return AdapterResult(
            source=self.name,
            status=status,
            data={"operation": "redirect-chain", **chain},
            warnings=warnings,
        )

    def indexability(self, url: str, **_: Any) -> AdapterResult:
        safe, hop, parser = self._page(url)
        header_robots = header_value(hop.headers, "x-robots-tag") or ""
        meta_values = [
            meta.get("content", "")
            for meta in parser.metas
            if meta.get("name", "").lower()
            in {"robots", "googlebot", "googlebot-news"}
        ]
        header_directives = directive_tokens([header_robots])
        meta_directives = directive_tokens(meta_values)
        directives = header_directives | meta_directives
        canonicals = [
            urllib.parse.urljoin(hop.final_url, link["href"])
            for link in parser.links
            if "canonical" in tokens(link.get("rel"))
            and link.get("href")
        ]
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
            source=self.name,
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
            warnings=[
                f"Technical indexability blocker: {reason}." for reason in blocking
            ],
        )

    def cwv(
        self,
        *,
        url: str | None = None,
        fixture_path: str | Path | None = None,
        strategy: str = "mobile",
        **_: Any,
    ) -> AdapterResult:
        if bool(url) == bool(fixture_path):
            raise ValueError("provide exactly one of url or fixture_path")
        if strategy not in {"mobile", "desktop"}:
            raise ValueError("strategy must be mobile or desktop")
        if fixture_path:
            payload = json.loads(
                Path(fixture_path).read_text(encoding="utf-8-sig")
            )
            source = "fixture"
            live = False
            warnings: list[str] = []
        else:
            result = (self.pagespeed or GooglePageSpeedLiveAdapter()).fetch(
                url=str(url),
                strategy=strategy,
                include_crux=True,
            )
            payload = result.data
            source = "pagespeed_live"
            live = True
            warnings = list(result.warnings)
        metrics = cwv_metrics(payload)
        missing = [
            name for name, item in metrics.items() if item["value"] is None
        ]
        if missing:
            warnings.append(
                "Missing Core Web Vitals evidence for: " + ", ".join(missing)
            )
        return AdapterResult(
            source=self.name,
            status="ok" if not missing else "partial",
            data={
                "operation": "cwv",
                "source": source,
                "strategy": strategy,
                "performance_score": performance_score(payload),
                "metrics": metrics,
                "data_state": "AVAILABLE" if not missing else "PARTIAL",
                "live_measurement": live,
                "limitations": [
                    "Lighthouse values are lab diagnostics; CrUX values are eligible-user field aggregates.",
                    "A passing measurement does not prove a ranking effect or completed remediation.",
                ],
            },
            warnings=warnings,
        )

    def schema_detect(
        self,
        *,
        url: str | None = None,
        html: str | None = None,
        source: str | None = None,
        **_: Any,
    ) -> AdapterResult:
        if bool(url) == bool(html):
            raise ValueError("provide exactly one of url or html")
        if url:
            safe, hop, parser = self._page(url)
            source_value = hop.final_url
        else:
            safe = None
            parser = PageParser()
            parser.feed(str(html))
            source_value = source or "html"
        items, invalid = parse_jsonld_scripts(parser.jsonld_texts)
        warnings: list[str] = []
        if invalid:
            warnings.append(
                f"{len(invalid)} JSON-LD script(s) could not be parsed."
            )
        if not items:
            warnings.append("No parseable JSON-LD items were found.")
        return AdapterResult(
            source=self.name,
            status="ok" if not warnings else "needs-review",
            data={
                "operation": "schema-detect",
                "url": safe,
                "source": source_value,
                "items": items,
                "item_count": len(items),
                "types": sorted(schema_types(items)),
                "invalid_scripts": invalid,
                "data_state": "AVAILABLE" if items else "EMPTY",
                "limitations": [
                    "Detection and JSON parsing do not prove Google rich-result eligibility.",
                    "Feature-specific required properties require current official validation.",
                ],
            },
            warnings=warnings,
        )

    def schema_validate(
        self,
        *,
        jsonld: str | dict[str, Any] | list[Any],
        **_: Any,
    ) -> AdapterResult:
        if isinstance(jsonld, str):
            try:
                payload = json.loads(jsonld)
            except json.JSONDecodeError as exc:
                return AdapterResult(
                    source=self.name,
                    status="invalid",
                    data={
                        "operation": "schema-validate",
                        "data_state": "INVALID_RESPONSE",
                        "error": str(exc),
                    },
                    warnings=["JSON-LD is not valid JSON."],
                )
        else:
            payload = jsonld
        items = payload if isinstance(payload, list) else [payload]
        errors: list[dict[str, Any]] = []
        types: set[str] = set()
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(
                    {"item": index, "error": "item must be a JSON object"}
                )
                continue
            if "@context" not in item:
                errors.append({"item": index, "error": "missing @context"})
            if "@type" not in item:
                errors.append({"item": index, "error": "missing @type"})
            types.update(type_values(item.get("@type")))
        return AdapterResult(
            source=self.name,
            status="ok" if not errors else "needs-review",
            data={
                "operation": "schema-validate",
                "valid_json": True,
                "baseline_valid": not errors,
                "item_count": len(items),
                "types": sorted(types),
                "errors": errors,
                "data_state": "AVAILABLE",
                "validation_scope": "json_syntax_and_schema_org_baseline_only",
                "limitations": [
                    "This validator does not claim Google rich-result eligibility.",
                    "Feature-specific required and recommended properties require current official validation.",
                ],
            },
            warnings=[entry["error"] for entry in errors],
        )

    def schema_generate(
        self,
        *,
        schema_type: str,
        values: dict[str, Any],
        **_: Any,
    ) -> AdapterResult:
        if schema_type not in SUPPORTED_SCHEMA:
            raise ValueError(
                "schema_type must be one of the supported types: "
                + ", ".join(sorted(SUPPORTED_SCHEMA))
            )
        if not isinstance(values, dict):
            raise TypeError("values must be an object")
        contract = SUPPORTED_SCHEMA[schema_type]
        allowed = set(contract["required"]) | set(contract["optional"])
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(
                "unsupported fields for this bounded generator: "
                + ", ".join(unknown)
            )
        missing = [
            field
            for field in contract["required"]
            if is_missing(values.get(field))
        ]
        if missing:
            raise ValueError("missing required fields: " + ", ".join(missing))
        output: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": schema_type,
        }
        for field in (*contract["required"], *contract["optional"]):
            value = values.get(field)
            if not is_missing(value):
                output[field] = value
        omitted = [
            field for field in contract["optional"] if field not in output
        ]
        return AdapterResult(
            source=self.name,
            status="ok",
            data={
                "operation": "schema-generate",
                "jsonld": output,
                "schema_type": schema_type,
                "omitted_optional_fields": omitted,
                "data_state": "AVAILABLE",
                "provenance": "operator_supplied_values_only",
                "limitations": [
                    "The generator includes only operator-supplied facts and does not invent ratings, reviews, offers, identity, or eligibility claims.",
                    "Generated markup still requires page-level and feature-specific validation.",
                ],
            },
            warnings=[],
        )

    def _page(self, url: str) -> tuple[str, HttpHop, PageParser]:
        safe = validate_public_url(url)
        hop = self.http.get(safe)
        parser = PageParser()
        parser.feed(decode_http_body(hop))
        return safe, hop, parser
