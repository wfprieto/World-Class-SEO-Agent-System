"""Technical SEO inspection operations built on bounded public evidence."""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Any

from contracts.adapter import AdapterResult
from contracts.construction import PageSpeedPort
from integrations.technical.http import BoundedHttpClient, HttpHop
from integrations.technical.page_inspection import (
    inspect_hreflang,
    inspect_indexability,
    inspect_preload,
)
from integrations.technical.parsing import (
    SUPPORTED_SCHEMA,
    PageParser,
    cwv_metrics,
    decode_http_body,
    is_missing,
    parse_jsonld_scripts,
    parse_robots,
    performance_score,
    schema_types,
    type_values,
)
from integrations.technical.sitemap_inspection import inspect_sitemap
from security.url_safety import validate_public_url


class TechnicalInspectionService:
    name = "technical_inspection"

    def __init__(
        self,
        *,
        http: Any | None = None,
        pagespeed: PageSpeedPort | None = None,
    ) -> None:
        self.http = http or BoundedHttpClient()
        self.pagespeed = pagespeed

    def robots(self, url: str, **_: Any) -> AdapterResult:
        safe = validate_public_url(url)
        parsed = urllib.parse.urlsplit(safe)
        robots_url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/robots.txt", "", ""))
        hop = self.http.get(robots_url)
        text = decode_http_body(hop)
        groups, sitemaps, unknown = parse_robots(text)
        warnings: list[str] = []
        if hop.status_code == 404:
            warnings.append("robots.txt was not found; this is not equivalent to a crawl block.")
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
        return inspect_sitemap(self.http, url, source=self.name)

    def hreflang(self, url: str, **_: Any) -> AdapterResult:
        safe, hop, parser = self._page(url)
        return inspect_hreflang(self.name, safe, hop, parser)

    def preload(self, url: str, **_: Any) -> AdapterResult:
        safe, hop, parser = self._page(url)
        return inspect_preload(self.name, safe, hop, parser)

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
            warnings.append("Redirect target was blocked by canonical public-URL safety.")
        if chain["hop_count"] > 2:
            warnings.append(f"Redirect chain contains {chain['hop_count']} HTTP responses.")
        status = (
            "ok"
            if not warnings
            else ("blocked" if chain["data_state"] == "BLOCKED" else "needs-review")
        )
        return AdapterResult(
            source=self.name,
            status=status,
            data={"operation": "redirect-chain", **chain},
            warnings=warnings,
        )

    def indexability(self, url: str, **_: Any) -> AdapterResult:
        safe, hop, parser = self._page(url)
        return inspect_indexability(self.name, safe, hop, parser)

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
            payload = json.loads(Path(fixture_path).read_text(encoding="utf-8-sig"))
            source = "fixture"
            live = False
            warnings: list[str] = []
        else:
            if self.pagespeed is None:
                return AdapterResult(
                    self.name,
                    "not_configured",
                    {"operation": "cwv", "data_state": "NOT_CONFIGURED", "live_measurement": False},
                    [
                        "PageSpeed transport is not configured; use seoctl.composition.build_technical_service."
                    ],
                )
            result = self.pagespeed.fetch(
                url=str(url),
                strategy=strategy,
                include_crux=True,
            )
            payload = result.data
            source = "pagespeed_live"
            live = True
            warnings = list(result.warnings)
        metrics = cwv_metrics(payload)
        missing = [name for name, item in metrics.items() if item["value"] is None]
        if missing:
            warnings.append("Missing Core Web Vitals evidence for: " + ", ".join(missing))
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
                errors.append({"item": index, "error": "item must be a JSON object"})
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
            raise ValueError("unsupported fields for this bounded generator: " + ", ".join(unknown))
        missing = [field for field in contract["required"] if is_missing(values.get(field))]
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
        omitted = [field for field in contract["optional"] if field not in output]
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
