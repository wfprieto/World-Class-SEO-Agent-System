"""Pure parsing helpers for bounded technical SEO inspection.

This module owns no network, routing, registry, or service behavior.  It keeps
untrusted response parsing independently testable while ``inspection`` remains
the canonical orchestration authority.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any

from integrations.technical.http import HttpHop

SUPPORTED_SCHEMA: dict[str, dict[str, tuple[str, ...]]] = {
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
        "optional": (
            "datePublished",
            "dateModified",
            "author",
            "image",
            "publisher",
            "description",
        ),
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


class PageParser(HTMLParser):
    """Collect only markup needed by the bounded technical inspections."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self.metas: list[dict[str, str]] = []
        self.jsonld_texts: list[str] = []
        self._jsonld_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        lower = tag.lower()
        if lower == "link":
            self.links.append(values)
        elif lower == "meta":
            self.metas.append(values)
        elif (
            lower == "script"
            and values.get("type", "").lower().split(";", 1)[0].strip()
            == "application/ld+json"
        ):
            self._jsonld_parts = []

    def handle_data(self, data: str) -> None:
        if self._jsonld_parts is not None:
            self._jsonld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._jsonld_parts is not None:
            self.jsonld_texts.append("".join(self._jsonld_parts).strip())
            self._jsonld_parts = None


def is_missing(value: Any) -> bool:
    return value is None or value == "" or value == []


def header_value(headers: dict[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value
    return None


def decode_http_body(hop: HttpHop) -> str:
    content_type = header_value(hop.headers, "content-type") or ""
    match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, flags=re.I)
    encoding = match.group(1) if match else "utf-8"
    try:
        return hop.body.decode(encoding, "replace")
    except LookupError:
        return hop.body.decode("utf-8", "replace")


def parse_robots(
    text: str,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    groups: list[dict[str, Any]] = []
    agents: list[str] = []
    rules: list[dict[str, str]] = []
    sitemaps: list[str] = []
    unknown: list[str] = []
    rules_started = False

    def flush() -> None:
        nonlocal agents, rules, rules_started
        if agents:
            groups.append({"user_agents": agents, "rules": rules})
        agents = []
        rules = []
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
            agents.append(value)
        elif directive in {"allow", "disallow"}:
            if not agents:
                agents = ["*"]
            rules.append({"directive": directive, "value": value})
            rules_started = True
        elif directive == "sitemap":
            if value:
                sitemaps.append(value)
        elif directive not in {"crawl-delay", "host"}:
            unknown.append(line)
    flush()
    return groups, list(dict.fromkeys(sitemaps)), unknown


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def tokens(value: str | None) -> set[str]:
    return {token.lower() for token in re.split(r"[\s,]+", value or "") if token}


def directive_tokens(values: list[str]) -> set[str]:
    return {
        token.lower()
        for value in values
        for token in re.split(r"[\s,;]+", value or "")
        if token
    }


def parse_jsonld_scripts(
    texts: list[str],
) -> tuple[list[Any], list[dict[str, Any]]]:
    items: list[Any] = []
    invalid: list[dict[str, Any]] = []
    for index, text in enumerate(texts):
        if not text:
            invalid.append({"script_index": index, "error": "empty JSON-LD script"})
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            invalid.append({"script_index": index, "error": str(exc)})
            continue
        items.extend(parsed if isinstance(parsed, list) else [parsed])
    return items, invalid


def type_values(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def schema_types(items: list[Any]) -> set[str]:
    output: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        output.update(type_values(item.get("@type")))
        graph = item.get("@graph")
        if isinstance(graph, list):
            output.update(schema_types(graph))
    return output


def _audit_number(
    audits: dict[str, Any],
    audit_id: str,
    payload: dict[str, Any],
    fallback: str,
) -> float | None:
    value = (audits.get(audit_id) or {}).get("numericValue")
    if value is None:
        value = payload.get(fallback)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _rating(value: float | None, good: float, poor: float) -> str:
    if value is None:
        return "not_available"
    if value <= good:
        return "good"
    if value <= poor:
        return "needs_improvement"
    return "poor"


def cwv_metrics(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lighthouse = payload.get("lighthouseResult") or payload
    audits = lighthouse.get("audits") or {}
    raw = {
        "lcp_ms": _audit_number(audits, "largest-contentful-paint", payload, "lcp_ms"),
        "inp_ms": _audit_number(audits, "interaction-to-next-paint", payload, "inp_ms"),
        "cls": _audit_number(audits, "cumulative-layout-shift", payload, "cls"),
    }
    return {
        "lcp_ms": {"value": raw["lcp_ms"], "rating": _rating(raw["lcp_ms"], 2500, 4000)},
        "inp_ms": {"value": raw["inp_ms"], "rating": _rating(raw["inp_ms"], 200, 500)},
        "cls": {"value": raw["cls"], "rating": _rating(raw["cls"], 0.1, 0.25)},
    }


def performance_score(payload: dict[str, Any]) -> float | None:
    lighthouse = payload.get("lighthouseResult") or payload
    value = ((lighthouse.get("categories") or {}).get("performance") or {}).get("score")
    if value is None:
        value = payload.get("performance_score")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
