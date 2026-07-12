"""Google Search Console Search Analytics and URL Inspection integration.

Search Analytics totals are queried without dimensions. They are never inferred
from dimension rows because Search Console can omit anonymized low-volume rows.
"""

from __future__ import annotations

import urllib.parse
from datetime import date, datetime, timedelta
from typing import Any

from adapters.base import AdapterResult
from adapters.url_safety import validate_public_url
from integrations.google.client import (
    GoogleJsonClient,
    GoogleOAuthConfig,
    GoogleOAuthProvider,
)

SEARCH_ANALYTICS = (
    "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
)
URL_INSPECTION = (
    "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
)
_ALLOWED_DIMENSIONS = {
    "country",
    "device",
    "date",
    "hour",
    "page",
    "query",
    "searchAppearance",
}
_ALLOWED_SEARCH_TYPES = {"web", "image", "video", "news", "discover", "googleNews"}
_ALLOWED_AGGREGATION = {"auto", "byPage", "byProperty"}
_ALLOWED_DATA_STATES = {"final", "all", "hourly_all"}


class GoogleSearchConsoleAdapter:
    name = "google_search_console"

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
            allowed_hosts={
                "www.googleapis.com",
                "searchconsole.googleapis.com",
            }
        )

    def fetch(self, operation: str = "query", **kwargs: Any) -> AdapterResult:
        normalized = operation.strip().lower().replace("_", "-")
        if normalized in {"query", "search-analytics"}:
            return self.query(**kwargs)
        if normalized in {"inspect", "url-inspection"}:
            return self.inspect(**kwargs)
        raise ValueError("operation must be query or inspect")

    def query(
        self,
        site_url: str,
        start_date: str | None = None,
        end_date: str | None = None,
        dimensions: list[str] | None = None,
        row_limit: int = 25_000,
        max_pages: int = 4,
        search_type: str = "web",
        aggregation_type: str = "auto",
        data_state: str = "final",
        dimension_filter_groups: list[dict[str, Any]] | None = None,
        **_: Any,
    ) -> AdapterResult:
        start, end = self._date_range(start_date, end_date)
        dims = list(dimensions or [])
        if len(dims) != len(set(dims)) or any(item not in _ALLOWED_DIMENSIONS for item in dims):
            raise ValueError(f"dimensions must be unique values from {sorted(_ALLOWED_DIMENSIONS)}")
        if not isinstance(row_limit, int) or not 1 <= row_limit <= 25_000:
            raise ValueError("row_limit must be an integer from 1 to 25000")
        if not isinstance(max_pages, int) or not 1 <= max_pages <= 100:
            raise ValueError("max_pages must be an integer from 1 to 100")
        if search_type not in _ALLOWED_SEARCH_TYPES:
            raise ValueError(f"search_type must be one of {sorted(_ALLOWED_SEARCH_TYPES)}")
        if aggregation_type not in _ALLOWED_AGGREGATION:
            raise ValueError(f"aggregation_type must be one of {sorted(_ALLOWED_AGGREGATION)}")
        if data_state not in _ALLOWED_DATA_STATES:
            raise ValueError(f"data_state must be one of {sorted(_ALLOWED_DATA_STATES)}")
        if aggregation_type == "byProperty" and (
            "page" in dims or self._filters_dimension(dimension_filter_groups, "page")
        ):
            raise ValueError("byProperty aggregation is invalid when grouping or filtering by page")

        token = self.oauth.token()
        endpoint = SEARCH_ANALYTICS.format(
            site=urllib.parse.quote(site_url, safe="")
        )
        common: dict[str, Any] = {
            "startDate": start,
            "endDate": end,
            "type": search_type,
            "aggregationType": aggregation_type,
            "dataState": data_state,
        }
        if dimension_filter_groups:
            common["dimensionFilterGroups"] = dimension_filter_groups

        aggregate_payload = dict(common)
        aggregate_payload["rowLimit"] = 1
        aggregate_response = self.client.request(
            endpoint,
            service="gsc_search_analytics",
            payload=aggregate_payload,
            access_token=token,
        )
        aggregate_row = (aggregate_response.get("rows") or [{}])[0]
        totals = {
            "clicks": float(aggregate_row.get("clicks", 0.0)),
            "impressions": float(aggregate_row.get("impressions", 0.0)),
            "ctr": float(aggregate_row.get("ctr", 0.0)),
            "position": (
                float(aggregate_row["position"])
                if aggregate_row.get("position") is not None
                else None
            ),
        }

        rows: list[dict[str, Any]] = []
        truncated = False
        if dims:
            for page_index in range(max_pages):
                request_payload = {
                    **common,
                    "dimensions": dims,
                    "rowLimit": row_limit,
                    "startRow": page_index * row_limit,
                }
                response = self.client.request(
                    endpoint,
                    service="gsc_search_analytics",
                    payload=request_payload,
                    access_token=token,
                )
                raw_rows = response.get("rows") or []
                for raw in raw_rows:
                    keys = list(raw.get("keys") or [])
                    rows.append(
                        {
                            "dimensions": {
                                dimension: keys[index] if index < len(keys) else None
                                for index, dimension in enumerate(dims)
                            },
                            "clicks": float(raw.get("clicks", 0.0)),
                            "impressions": float(raw.get("impressions", 0.0)),
                            "ctr": float(raw.get("ctr", 0.0)),
                            "position": (
                                float(raw["position"])
                                if raw.get("position") is not None
                                else None
                            ),
                        }
                    )
                if len(raw_rows) < row_limit:
                    break
            else:
                truncated = True

        warnings: list[str] = []
        if truncated:
            warnings.append(
                "Dimension rows reached the configured pagination ceiling; totals remain valid but row coverage is partial."
            )
        metadata = aggregate_response.get("metadata") or {}
        if metadata:
            warnings.append(
                "Search Console reported incomplete recent data; inspect response metadata before comparison."
            )
        return AdapterResult(
            source=self.name,
            status="partial" if truncated else "ok",
            data={
                "site_url": site_url,
                "date_range": {"start": start, "end": end, "timezone": "America/Los_Angeles"},
                "search_type": search_type,
                "aggregation_type": aggregate_response.get(
                    "responseAggregationType",
                    aggregation_type,
                ),
                "data_state": data_state,
                "totals": totals,
                "totals_source": "dimensionless_aggregate_query",
                "dimensions": dims,
                "rows": rows,
                "row_count": len(rows),
                "rows_truncated": truncated,
                "metadata": metadata,
                "limitations": [
                    "Search Analytics returns top rows and does not guarantee every dimension row.",
                    "Dimension rows must not be summed to replace the separate aggregate totals."
                ],
            },
            warnings=warnings,
        )

    def inspect(
        self,
        inspection_url: str,
        site_url: str,
        language_code: str = "en-US",
        **_: Any,
    ) -> AdapterResult:
        public_url = validate_public_url(inspection_url)
        if not self._belongs_to_property(public_url, site_url):
            raise ValueError("inspection_url must belong to the supplied Search Console property")
        token = self.oauth.token()
        response = self.client.request(
            URL_INSPECTION,
            service="gsc_url_inspection",
            payload={
                "inspectionUrl": public_url,
                "siteUrl": site_url,
                "languageCode": language_code,
            },
            access_token=token,
        )
        inspection = response.get("inspectionResult") or {}
        index = inspection.get("indexStatusResult") or {}
        return AdapterResult(
            source=self.name,
            status="ok" if index else "partial",
            data={
                "inspection_url": public_url,
                "site_url": site_url,
                "verdict": index.get("verdict"),
                "coverage_state": index.get("coverageState"),
                "indexing_state": index.get("indexingState"),
                "robots_txt_state": index.get("robotsTxtState"),
                "page_fetch_state": index.get("pageFetchState"),
                "google_canonical": index.get("googleCanonical"),
                "user_canonical": index.get("userCanonical"),
                "last_crawl_time": index.get("lastCrawlTime"),
                "crawled_as": index.get("crawledAs"),
                "referring_urls": index.get("referringUrls") or [],
                "sitemap": index.get("sitemap") or [],
                "mobile_usability": inspection.get("mobileUsabilityResult"),
                "rich_results": inspection.get("richResultsResult"),
                "inspection_scope": "google_index_version_only",
                "limitations": [
                    "The URL Inspection API reports the version in Google's index and does not test the live URL."
                ],
            },
            warnings=[] if index else ["URL Inspection returned no indexStatusResult."],
        )

    @staticmethod
    def _date_range(start: str | None, end: str | None) -> tuple[str, str]:
        end_value = end or (date.today() - timedelta(days=3)).isoformat()
        start_value = start or (date.today() - timedelta(days=31)).isoformat()
        try:
            start_date = datetime.strptime(start_value, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("dates must use YYYY-MM-DD") from exc
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        return start_date.isoformat(), end_date.isoformat()

    @staticmethod
    def _filters_dimension(groups: list[dict[str, Any]] | None, dimension: str) -> bool:
        return any(
            str(item.get("dimension")) == dimension
            for group in groups or []
            for item in group.get("filters", [])
            if isinstance(group, dict) and isinstance(item, dict)
        )

    @staticmethod
    def _belongs_to_property(url: str, property_value: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        if property_value.startswith("sc-domain:"):
            domain = property_value.removeprefix("sc-domain:").lower().strip(".")
            host = (parsed.hostname or "").lower().strip(".")
            return host == domain or host.endswith("." + domain)
        normalized = property_value.rstrip("/") + "/"
        return url.startswith(normalized)
