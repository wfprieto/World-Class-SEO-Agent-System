"""Read-only Search Console Sitemaps API integration."""

from __future__ import annotations

import urllib.parse
from typing import Any

from adapters.base import AdapterResult
from adapters.url_safety import validate_public_url
from integrations.google.client import (
    GoogleJsonClient,
    GoogleOAuthConfig,
    GoogleOAuthProvider,
)
from integrations.google.gsc import GoogleSearchConsoleAdapter

_SITEMAPS = "https://www.googleapis.com/webmasters/v3/sites/{site}/sitemaps"


class GoogleSitemapsAdapter:
    """List or retrieve submitted sitemap evidence without write actions."""

    name = "google_search_console_sitemaps"

    def __init__(
        self,
        *,
        oauth: GoogleOAuthProvider | None = None,
        client: GoogleJsonClient | None = None,
    ) -> None:
        self.oauth = oauth or GoogleOAuthProvider(
            GoogleOAuthConfig.from_env("GSC")
        )
        self.client = client or GoogleJsonClient(
            allowed_hosts={"www.googleapis.com"}
        )

    def fetch(
        self,
        site_url: str,
        sitemap_url: str | None = None,
        sitemap_index: str | None = None,
        **_: Any,
    ) -> AdapterResult:
        if sitemap_url and sitemap_index:
            raise ValueError("sitemap_url and sitemap_index cannot be used together")
        property_value = GoogleSearchConsoleAdapter._validate_property(site_url)
        base = _SITEMAPS.format(
            site=urllib.parse.quote(property_value, safe="")
        )
        query: dict[str, str | int | None] = {}
        operation = "list"
        if sitemap_url:
            safe_sitemap = validate_public_url(sitemap_url)
            if not GoogleSearchConsoleAdapter._belongs_to_property(
                safe_sitemap,
                property_value,
            ):
                raise ValueError("sitemap_url must belong to the supplied Search Console property")
            endpoint = base + "/" + urllib.parse.quote(safe_sitemap, safe="")
            operation = "get"
        else:
            endpoint = base
            safe_sitemap = None
            if sitemap_index:
                safe_index = validate_public_url(sitemap_index)
                if not GoogleSearchConsoleAdapter._belongs_to_property(
                    safe_index,
                    property_value,
                ):
                    raise ValueError("sitemap_index must belong to the supplied Search Console property")
                query["sitemapIndex"] = safe_index

        response = self.client.request(
            endpoint,
            service="gsc_sitemaps",
            method="GET",
            query=query,
            access_token=self.oauth.token(),
        )
        raw_items = [response] if operation == "get" else list(response.get("sitemap") or [])
        items = [self._normalize(item) for item in raw_items if isinstance(item, dict)]
        warning_count = sum(item["warning_count"] for item in items)
        error_count = sum(item["error_count"] for item in items)
        warnings: list[str] = []
        if warning_count:
            warnings.append(f"Search Console reports {warning_count} sitemap warning(s).")
        if error_count:
            warnings.append(f"Search Console reports {error_count} sitemap error(s).")
        data_state = "AVAILABLE" if items else "EMPTY"
        return AdapterResult(
            source=self.name,
            status="ok",
            data={
                "site_url": property_value,
                "operation": operation,
                "requested_sitemap_url": safe_sitemap,
                "sitemaps": items,
                "sitemap_count": len(items),
                "warning_count": warning_count,
                "error_count": error_count,
                "data_state": data_state,
                "read_only": True,
                "request_metadata": dict(getattr(self.client, "last_telemetry", {}) or {}),
                "limitations": [
                    "This command reads Search Console submission status only.",
                    "It does not submit, delete, fetch, or modify a sitemap.",
                ],
            },
            warnings=warnings,
        )

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        contents = []
        for content in item.get("contents") or []:
            if not isinstance(content, dict):
                continue
            contents.append(
                {
                    "type": content.get("type"),
                    "submitted": content.get("submitted"),
                    "indexed": content.get("indexed"),
                }
            )
        warning_count = GoogleSitemapsAdapter._int(item.get("warnings"))
        error_count = GoogleSitemapsAdapter._int(item.get("errors"))
        return {
            "path": item.get("path"),
            "last_submitted": item.get("lastSubmitted"),
            "is_pending": item.get("isPending"),
            "is_sitemaps_index": item.get("isSitemapsIndex"),
            "type": item.get("type"),
            "last_downloaded": item.get("lastDownloaded"),
            "warning_count": warning_count,
            "error_count": error_count,
            "contents": contents,
        }

    @staticmethod
    def _int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
