"""Technical SEO inspection operations built on bounded public evidence."""

from __future__ import annotations

import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from adapters.base import AdapterResult
from adapters.google_pagespeed_live import GooglePageSpeedLiveAdapter
from adapters.url_safety import validate_public_url
from integrations.technical.http import BoundedHttpClient, HttpHop


_BCP47 = re.compile(
    r"^(?:[A-Za-z]{2,3}(?:-[A-Za-z]{4})?(?:-(?:[A-Za-z]{2}|\d{3}))?(?:-[A-Za-z0-9]{5,8}|-\d[A-Za-z0-9]{3})*|x-default)$"
)
_SUPPORTED_SCHEMA: dict[str, dict[str, tuple[str, ...]]] = {
    "Organization": {
        "required": ("name", "url"),
        "optional": ("logo", "sameAs", "description"),
    },
    "WebSite": {
        "required": ("name", "url"),
        "optional": ("alternateName", "description", "publisher"),
    },
    "Article": {
        "required": ("headline", "url"),
        "optional": ("datePublished", "dateModified", "author", "image", "publisher", "description"),
    },
    "Product": {
        "required": ("name", "url"),
        "optional": ("image", "description", "sku", "brand", "offers"),
    },
    "BreadcrumbList": {
        "required": ("itemListElement",),
        "optional": (),
    },
}


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self.metas: list[dict[str, str]] = []
        self.jsonld_texts: list[str] = []
        self._in_jsonld = False
        self._jsonld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        normalized = {str(key).lower(): str(value or "") for key, value in attrs}
        lower = tag.lower()
        if lower == "link":
            self.links.append(normalized)
        elif lower == "meta":
            self.metas.append(normalized)
        elif lower == "script" and normalized.get("type", "").lower().split(";", 1)[0].strip() == "application/ld+json":
            self._in_jsonld = True
            self._jsonld_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._jsonld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_jsonld:
            self.jsonld_texts.append("".join(self._jsonld_parts).strip())
            self._in_jsonld = False
            self._jsonld_parts = []


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
        robots_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
        hop = self.http.get(robots_url)
        text = self._decode(hop)
        groups, sitemaps, unknown = self._parse_robots(text)
        warnings: list[str] = []
        if hop.status_code == 404:
            warnings.append("robots.txt was not found; this is not equivalent to a crawl block.")
        elif not 200 <= hop.status_code < 300:
            warnings.append(f"robots.txt returned HTTP {hop.status_code}.")
        if unknown:
            warnings.append(f"{len(unknown)} unrecognized robots.txt directive line(s) were preserved.")
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
                    "This parser reports directives; it does not claim how every crawler implements them.",
                    "Robots rules control crawling, not guaranteed indexing removal.",
                ],
            },
            warnings=warnings,
        )

    def sitemap(self, url: str, **_: Any) -> AdapterResult:
        safe = validate_public_url(url)
        hop = self.http.get(safe)
        warnings: list[str] = []
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
        kind = self._local_name(root.tag)
        if kind not in {"urlset", "sitemapindex"}:
            warnings.append(f"Unexpected sitemap root element: {kind or 'unknown'}.")
        locations = [
            (element.text or "").strip()
            for element in root.iter()
            if self._local_name(element.tag) == "loc" and (element.text or "").strip()
        ]
        truncated = len(locations) > 50_000
        analyzed = locations[:50_000]
        counts = Counter(analyzed)
        duplicates = sorted(value for value, count in counts.items() if count > 1)
        unsafe_locations: list[str] = []
        safe_locations: list[str] = []
        for location in analyzed:
            try:
                safe_locations.append(validate_public_url(location))
            except ValueError:
                unsafe_locations.append(location)
        if duplicates:
            warnings.append(f"{len(duplicates)} duplicate sitemap location(s) found.")
        if unsafe_locations:
            warnings.append(f"{len(unsafe_locations)} non-public or invalid sitemap location(s) found.")
        if truncated:
            warnings.append("Sitemap exceeds the 50,000-location analysis ceiling; remaining entries were not analyzed.")
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
        safe, hop, html, parser = self._page(url)
        alternates: list[dict[str, Any]] = []
        invalid_codes: list[str] = []
        invalid_targets: list[str] = []
        for link in parser.links:
            rel = self._tokens(link.get("rel"))
            lang = link.get("hreflang", "").strip()
            href = link.get("href", "").strip()
            if "alternate" not in rel or not lang:
                continue
            resolved = urllib.parse.urljoin(hop.final_url, href) if href else ""
            valid_code = bool(_BCP47.fullmatch(lang))
            if not valid_code:
                invalid_codes.append(lang)
            try:
                target = validate_public_url(resolved)
                target_valid = True
            except ValueError:
                target = resolved
                target_valid = False
                invalid_targets.append(resolved)
            alternates.append(
                {
                    "hreflang": lang,
                    "href": target,
                    "language_code_valid": valid_code,
                    "target_public": target_valid,
                }
            )
        duplicate_codes = sorted(
            code for code, count in Counter(item["hreflang"].lower() for item in alternates).items() if count > 1
        )
        warnings: list[str] = []
        if invalid_codes:
            warnings.append(f"{len(invalid_codes)} hreflang value(s) do not match the bounded BCP-47 validator.")
        if invalid_targets:
            warnings.append(f"{len(invalid_targets)} hreflang target(s) are invalid or non-public.")
        if duplicate_codes:
            warnings.append(f"Duplicate hreflang codes found: {', '.join(duplicate_codes)}.")
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
                "has_x_default": any(item["hreflang"].lower() == "x-default" for item in alternates),
                "invalid_language_codes": invalid_codes,
                "invalid_targets": invalid_targets,
                "duplicate_language_codes": duplicate_codes,
                "data_state": "AVAILABLE" if alternates else "EMPTY",
                "limitations": [
                    "A single-page inspection cannot prove reciprocal return links across alternate pages.",
                    "HTTP headers and XML-sitemap hreflang annotations are outside this HTML-only result.",
                ],
            },
            warnings=warnings,
        )

    def preload(self, url: str, **_: Any) -> AdapterResult:
        safe, hop, html, parser = self._page(url)
        preloads: list[dict[str, Any]] = []
        warnings: list[str] = []
        for link in parser.links:
            rel = self._tokens(link.get("rel"))
            if not ({"preload", "modulepreload"} & rel):
                continue
            href = link.get("href", "").strip()
            resolved = urllib.parse.urljoin(hop.final_url, href) if href else ""
            entry = {
                "rel": sorted(rel),
                "href": resolved,
                "as": link.get("as") or None,
                "type": link.get("type") or None,
                "media": link.get("media") or None,
                "crossorigin": link.get("crossorigin") or None,
                "fetchpriority": (link.get("fetchpriority") or "").lower() or None,
            }
            preloads.append(entry)
            if not href:
                warnings.append("A preload declaration is missing href.")
            if "preload" in rel and not entry["as"]:
                warnings.append(f"Preload {resolved or '[missing href]'} is missing an 'as' value.")
        high_priority_images = [
            item for item in preloads if item["as"] == "image" and item["fetchpriority"] == "high"
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
                    "Presence of preload markup does not prove the resource was useful or discovered early enough.",
                    "Performance impact requires browser or field evidence.",
                ],
            },
            warnings=warnings,
        )

    def redirect_chain(self, url: str, max_redirects: int = 10, **_: Any) -> AdapterResult:
        chain = self.http.redirect_chain(url, max_redirects=max_redirects)
        warnings: list[str] = []
        if chain["loop_detected"]:
            warnings.append("Redirect loop detected.")
        if chain["limit_reached"]:
            warnings.append("Redirect chain reached the configured hop ceiling.")
        if chain["blocked_target"]:
            warnings.append("Redirect target was blocked by canonical public-URL safety.")
        if chain["hop_count"] > 2:
            warnings.append(f"Redirect chain contains {chain['hop_count']} HTTP responses.")
        return AdapterResult(
            source=self.name,
            status="ok" if not warnings else ("blocked" if chain["data_state"] == "BLOCKED" else "needs-review"),
            data={"operation": "redirect-chain", **chain},
            warnings=warnings,
        )

    def indexability(self, url: str, **_: Any) -> AdapterResult:
        safe, hop, html, parser = self._page(url)
        header_robots = self._header(hop.headers, "x-robots-tag") or ""
        meta_values = [
            meta.get("content", "")
            for meta in parser.metas
            if meta.get("name", "").lower() in {"robots", "googlebot", "googlebot-news"}
        ]
        directives = self._directive_tokens([header_robots, *meta_values])
        canonical_values = []
        for link in parser.links:
            if "canonical" in self._tokens(link.get("rel")) and link.get("href"):
                canonical_values.append(urllib.parse.urljoin(hop.final_url, link["href"]))
        blocking: list[str] = []
        if not 200 <= hop.status_code < 300:
            blocking.append(f"http_status_{hop.status_code}")
        if "noindex" in directives or "none" in directives:
            if any("noindex" in self._directive_tokens([value]) or "none" in self._directive_tokens([value]) for value in meta_values):
                blocking.append("meta_robots_noindex")
            if "noindex" in self._directive_tokens([header_robots]) or "none" in self._directive_tokens([header_robots]):
                blocking.append("x_robots_tag_noindex")
        if len(canonical_values) > 1:
            blocking.append("multiple_html_canonicals")
        canonical = canonical_values[0] if len(canonical_values) == 1 else None
        canonical_public = None
        if canonical:
            try:
                canonical = validate_public_url(canonical)
                canonical_public = True
            except ValueError:
                canonical_public = False
                blocking.append("invalid_or_non_public_canonical")
        indexable = not blocking
        warnings = [f"Technical indexability blocker: {item}." for item in blocking]
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
                "canonical_count": len(canonical_values),
                "indexable": indexable,
                "blocking_reasons": blocking,
                "data_state": "AVAILABLE",
                "limitations": [
                    "This is a technical eligibility assessment, not proof that Google indexed or will index the URL.",
                    "Robots.txt crawl rules and Google index state require separate evidence.",
                ],
            },
            warnings=warnings,
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
            raw = json.loads(Path(fixture_path).read_text(encoding="utf-8-sig"))
            source = "fixture"
            live = False
            normalized = raw
            warnings: list[str] = []
        else:
            adapter = self.pagespeed or GooglePageSpeedLiveAdapter()
            live_result = adapter.fetch(url=str(url), strategy=strategy, include_crux=True)
            source = "pagespeed_live"
            live = True
            normalized = live_result.data
            warnings = list(live_result.warnings)
        metrics = self._cwv_metrics(normalized)
        missing = [name for name, item in metrics.items() if item["value"] is None]
        if missing:
            warnings.append("Missing Core Web Vitals evidence for: " + ", ".join(missing))
        status = "ok" if not missing else "partial"
        performance_score = self._performance_score(normalized)
        return AdapterResult(
            source=self.name,
            status=status,
            data={
                "operation": "cwv",
                "source": source,
                "strategy": strategy,
                "performance_score": performance_score,
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
            safe, hop, html_value, parser = self._page(url)
            source_value = hop.final_url
        else:
            safe = None
            html_value = str(html)
            parser = _PageParser()
            parser.feed(html_value)
            source_value = source or "html"
        items: list[Any] = []
        invalid: list[dict[str, Any]] = []
        for index, text in enumerate(parser.jsonld_texts):
            if not text:
                invalid.append({"script_index": index, "error": "empty JSON-LD script"})
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as exc:
                invalid.append({"script_index": index, "error": str(exc)})
                continue
            if isinstance(parsed, list):
                items.extend(parsed)
            else:
                items.append(parsed)
        types = sorted(self._schema_types(items))
        warnings = []
        if invalid:
            warnings.append(f"{len(invalid)} JSON-LD script(s) could not be parsed.")
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
                "types": types,
                "invalid_scripts": invalid,
                "data_state": "AVAILABLE" if items else "EMPTY",
                "limitations": [
                    "Detection and JSON parsing do not prove eligibility for a Google rich result.",
                    "Google feature-specific required properties must be checked against current official documentation.",
                ],
            },
            warnings=warnings,
        )

    def schema_validate(self, *, jsonld: str | dict[str, Any] | list[Any], **_: Any) -> AdapterResult:
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
                errors.append({"item": index, "error": "item must be a JSON object"})
                continue
            if "@context" not in item:
                errors.append({"item": index, "error": "missing @context"})
            if "@type" not in item:
                errors.append({"item": index, "error": "missing @type"})
            types.update(self._type_values(item.get("@type")))
        warnings = [entry["error"] for entry in errors]
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
                    "Feature-specific required and recommended properties change and require current official validation.",
                ],
            },
            warnings=warnings,
        )

    def schema_generate(
        self,
        *,
        schema_type: str,
        values: dict[str, Any],
        **_: Any,
    ) -> AdapterResult:
        if schema_type not in _SUPPORTED_SCHEMA:
            raise ValueError(f"schema_type must be one of the supported types: {sorted(_SUPPORTED_SCHEMA)}")
        if not isinstance(values, dict):
            raise TypeError("values must be an object")
        contract = _SUPPORTED_SCHEMA[schema_type]
        allowed = set(contract["required"]) | set(contract["optional"])
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError("unsupported fields for this bounded generator: " + ", ".join(unknown))
        missing = [field for field in contract["required"] if values.get(field) in {None, "", []}]
        if missing:
            raise ValueError("missing required fields: " + ", ".join(missing))
        jsonld: dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": schema_type,
        }
        for field in (*contract["required"], *contract["optional"]):
            if field in values and values[field] not in {None, "", []}:
                jsonld[field] = values[field]
        omitted = [field for field in contract["optional"] if field not in jsonld]
        return AdapterResult(
            source=self.name,
            status="ok",
            data={
                "operation": "schema-generate",
                "jsonld": jsonld,
                "schema_type": schema_type,
                "omitted_optional_fields": omitted,
                "data_state": "AVAILABLE",
                "provenance": "operator_supplied_values_only",
                "limitations": [
                    "The generator includes only operator-supplied facts and does not invent ratings, reviews, offers, identity, or eligibility claims.",
                    "Generated baseline markup still requires page-level and Google feature-specific validation.",
                ],
            },
            warnings=[],
        )

    def _page(self, url: str) -> tuple[str, HttpHop, str, _PageParser]:
        safe = validate_public_url(url)
        hop = self.http.get(safe)
        html = self._decode(hop)
        parser = _PageParser()
        parser.feed(html)
        return safe, hop, html, parser

    @staticmethod
    def _decode(hop: HttpHop) -> str:
        content_type = TechnicalInspectionService._header(hop.headers, "content-type") or ""
        match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, flags=re.I)
        encoding = match.group(1) if match else "utf-8"
        try:
            return hop.body.decode(encoding, "replace")
        except LookupError:
            return hop.body.decode("utf-8", "replace")

    @staticmethod
    def _parse_robots(text: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        groups: list[dict[str, Any]] = []
        current_agents: list[str] = []
        current_rules: list[dict[str, str]] = []
        sitemaps: list[str] = []
        unknown: list[str] = []

        def flush() -> None:
            nonlocal current_agents, current_rules
            if current_agents:
                groups.append({"user_agents": current_agents, "rules": current_rules})
            current_agents = []
            current_rules = []

        rules_started = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            name, value = (part.strip() for part in line.split(":", 1))
            directive = name.lower()
            if directive == "user-agent":
                if rules_started:
                    flush()
                    rules_started = False
                current_agents.append(value)
            elif directive in {"allow", "disallow"}:
                if not current_agents:
                    current_agents = ["*"]
                current_rules.append({"directive": directive, "value": value})
                rules_started = True
            elif directive == "sitemap":
                if value:
                    sitemaps.append(value)
            elif directive not in {"crawl-delay", "host"}:
                unknown.append(line)
        flush()
        return groups, list(dict.fromkeys(sitemaps)), unknown

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    @staticmethod
    def _tokens(value: str | None) -> set[str]:
        return {item.lower() for item in re.split(r"[\s,]+", value or "") if item}

    @staticmethod
    def _directive_tokens(values: list[str]) -> set[str]:
        return {
            token.lower()
            for value in values
            for token in re.split(r"[\s,;]+", value or "")
            if token
        }

    @staticmethod
    def _header(headers: dict[str, str], name: str) -> str | None:
        for key, value in headers.items():
            if key.lower() == name.lower():
                return value
        return None

    @classmethod
    def _schema_types(cls, items: list[Any]) -> set[str]:
        output: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            output.update(cls._type_values(item.get("@type")))
            graph = item.get("@graph")
            if isinstance(graph, list):
                output.update(cls._schema_types(graph))
        return output

    @staticmethod
    def _type_values(value: Any) -> set[str]:
        if isinstance(value, str):
            return {value}
        if isinstance(value, list):
            return {str(item) for item in value if isinstance(item, str)}
        return set()

    @classmethod
    def _cwv_metrics(cls, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        lighthouse = payload.get("lighthouseResult") or payload
        audits = lighthouse.get("audits") or {}
        raw = {
            "lcp_ms": cls._audit_number(audits, "largest-contentful-paint", payload, "lcp_ms"),
            "inp_ms": cls._audit_number(audits, "interaction-to-next-paint", payload, "inp_ms"),
            "cls": cls._audit_number(audits, "cumulative-layout-shift", payload, "cls"),
        }
        return {
            "lcp_ms": {"value": raw["lcp_ms"], "rating": cls._rating(raw["lcp_ms"], 2500, 4000)},
            "inp_ms": {"value": raw["inp_ms"], "rating": cls._rating(raw["inp_ms"], 200, 500)},
            "cls": {"value": raw["cls"], "rating": cls._rating(raw["cls"], 0.1, 0.25)},
        }

    @staticmethod
    def _audit_number(audits: dict[str, Any], audit_id: str, payload: dict[str, Any], fallback: str) -> float | None:
        value = (audits.get(audit_id) or {}).get("numericValue")
        if value is None:
            value = payload.get(fallback)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _performance_score(payload: dict[str, Any]) -> float | None:
        lighthouse = payload.get("lighthouseResult") or payload
        value = ((lighthouse.get("categories") or {}).get("performance") or {}).get("score")
        if value is None:
            value = payload.get("performance_score")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _rating(value: float | None, good: float, poor: float) -> str:
        if value is None:
            return "not_available"
        if value <= good:
            return "good"
        if value <= poor:
            return "needs_improvement"
        return "poor"
