"""Google Analytics Data API v1beta report integration."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from adapters.base import AdapterResult
from integrations.google.client import (
    GoogleJsonClient,
    GoogleOAuthConfig,
    GoogleOAuthProvider,
)

_ENDPOINT = "https://analyticsdata.googleapis.com/v1beta/{property}:runReport"
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class GoogleAnalyticsDataAdapter:
    name = "google_analytics_data"

    def __init__(
        self,
        *,
        oauth: GoogleOAuthProvider | None = None,
        client: GoogleJsonClient | None = None,
    ) -> None:
        self.oauth = oauth or GoogleOAuthProvider(
            GoogleOAuthConfig.from_env("GA4")
        )
        self.client = client or GoogleJsonClient(
            allowed_hosts={"analyticsdata.googleapis.com"}
        )

    def fetch(
        self,
        property_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        dimensions: list[str] | None = None,
        metrics: list[str] | None = None,
        limit: int = 10_000,
        offset: int = 0,
        dimension_filter: dict[str, Any] | None = None,
        metric_filter: dict[str, Any] | None = None,
        order_bys: list[dict[str, Any]] | None = None,
        keep_empty_rows: bool = False,
        return_property_quota: bool = True,
        currency_code: str | None = None,
        **_: Any,
    ) -> AdapterResult:
        property_name = self._property_name(property_id)
        start, end = self._date_range(start_date, end_date)
        dims = list(dimensions or ["landingPagePlusQueryString"])
        mets = list(metrics or ["sessions", "engagedSessions", "keyEvents"])
        self._validate_names(dims, "dimension")
        self._validate_names(mets, "metric")
        if not isinstance(limit, int) or not 1 <= limit <= 250_000:
            raise ValueError("limit must be an integer from 1 to 250000")
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if currency_code is not None and not re.fullmatch(r"[A-Z]{3}", currency_code):
            raise ValueError("currency_code must be a three-letter ISO 4217 code")

        request_payload: dict[str, Any] = {
            "dimensions": [{"name": item} for item in dims],
            "metrics": [{"name": item} for item in mets],
            "dateRanges": [{"startDate": start, "endDate": end}],
            "offset": str(offset),
            "limit": str(limit),
            "metricAggregations": ["TOTAL"],
            "keepEmptyRows": bool(keep_empty_rows),
            "returnPropertyQuota": bool(return_property_quota),
        }
        if dimension_filter:
            request_payload["dimensionFilter"] = dimension_filter
        if metric_filter:
            request_payload["metricFilter"] = metric_filter
        if order_bys:
            request_payload["orderBys"] = order_bys
        if currency_code:
            request_payload["currencyCode"] = currency_code

        response = self.client.request(
            _ENDPOINT.format(property=property_name),
            service="ga4_run_report",
            payload=request_payload,
            access_token=self.oauth.token(),
        )
        dimension_headers = [
            str(item.get("name", ""))
            for item in response.get("dimensionHeaders") or []
        ]
        metric_headers = [
            {
                "name": str(item.get("name", "")),
                "type": str(item.get("type", "")),
            }
            for item in response.get("metricHeaders") or []
        ]
        rows = [
            self._normalize_row(row, dimension_headers, metric_headers)
            for row in response.get("rows") or []
        ]
        totals = [
            self._normalize_metric_values(row.get("metricValues") or [], metric_headers)
            for row in response.get("totals") or []
        ]
        row_count = int(response.get("rowCount", len(rows)))
        warnings: list[str] = []
        if offset + len(rows) < row_count:
            warnings.append(
                "The report contains additional rows; increase offset or paginate to retrieve them."
            )
        metadata = response.get("metadata") or {}
        if metadata.get("dataLossFromOtherRow"):
            warnings.append(
                "Google Analytics reported data loss from the aggregated '(other)' row."
            )
        return AdapterResult(
            source=self.name,
            status="partial" if warnings else "ok",
            data={
                "property": property_name,
                "date_range": {"start": start, "end": end},
                "dimensions": dimension_headers or dims,
                "metrics": metric_headers or [{"name": item, "type": ""} for item in mets],
                "rows": rows,
                "row_count": row_count,
                "returned_rows": len(rows),
                "offset": offset,
                "limit": limit,
                "totals": totals,
                "totals_source": "ga4_metric_aggregation_total",
                "property_quota": response.get("propertyQuota"),
                "metadata": metadata,
                "currency_code": response.get("currencyCode") or currency_code,
                "time_zone": response.get("timeZone"),
                "limitations": [
                    "The API reports data collected by the configured GA4 property; missing events cannot be inferred as zero activity.",
                    "Overlapping date ranges would duplicate overlapping event data; this connector issues one date range per call."
                ],
            },
            warnings=warnings,
        )

    @staticmethod
    def _property_name(value: str) -> str:
        normalized = str(value).strip()
        if normalized.startswith("properties/"):
            identifier = normalized.removeprefix("properties/")
        else:
            identifier = normalized
        if not identifier.isdigit():
            raise ValueError("property_id must be numeric or use properties/<numeric-id>")
        return f"properties/{identifier}"

    @staticmethod
    def _date_range(start: str | None, end: str | None) -> tuple[str, str]:
        end_value = end or (date.today() - timedelta(days=1)).isoformat()
        start_value = start or (date.today() - timedelta(days=29)).isoformat()
        try:
            start_date = datetime.strptime(start_value, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("dates must use YYYY-MM-DD") from exc
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        return start_date.isoformat(), end_date.isoformat()

    @staticmethod
    def _validate_names(values: list[str], label: str) -> None:
        if not values or len(values) != len(set(values)):
            raise ValueError(f"{label}s must be a non-empty unique list")
        invalid = [value for value in values if not _NAME.fullmatch(value)]
        if invalid:
            raise ValueError(f"invalid {label} names: {invalid}")

    @classmethod
    def _normalize_row(
        cls,
        row: dict[str, Any],
        dimension_headers: list[str],
        metric_headers: list[dict[str, str]],
    ) -> dict[str, Any]:
        dimensions = {
            name: str(values[index].get("value", "")) if index < len(values) else None
            for index, name in enumerate(dimension_headers)
            for values in [row.get("dimensionValues") or []]
        }
        metrics = cls._normalize_metric_values(
            row.get("metricValues") or [],
            metric_headers,
        )
        return {"dimensions": dimensions, "metrics": metrics}

    @staticmethod
    def _normalize_metric_values(
        values: list[dict[str, Any]],
        metric_headers: list[dict[str, str]],
    ) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for index, header in enumerate(metric_headers):
            raw = str(values[index].get("value", "")) if index < len(values) else ""
            kind = header.get("type", "")
            if kind in {"TYPE_INTEGER"}:
                try:
                    output[header["name"]] = int(raw)
                    continue
                except ValueError:
                    pass
            if kind in {
                "TYPE_FLOAT",
                "TYPE_SECONDS",
                "TYPE_MILLISECONDS",
                "TYPE_MINUTES",
                "TYPE_HOURS",
                "TYPE_STANDARD",
                "TYPE_CURRENCY",
                "TYPE_FEET",
                "TYPE_MILES",
                "TYPE_METERS",
                "TYPE_KILOMETERS",
            }:
                try:
                    output[header["name"]] = float(raw)
                    continue
                except ValueError:
                    pass
            output[header["name"]] = raw
        return output
