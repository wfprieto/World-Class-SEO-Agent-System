"""Search Analytics truthful states, warning order and result normalization."""
from __future__ import annotations

from typing import Any

from contracts.adapter import AdapterResult


def _query_warnings(truncated: bool, aggregate_metadata: dict[str, Any],
                    detail_metadata: list[dict[str, Any]], dims: list[str]) -> list[str]:
    warnings: list[str] = []
    if truncated:
        warnings.append(
            "Dimension rows reached the configured pagination ceiling; aggregate totals remain valid but row coverage is partial."
        )
    if aggregate_metadata or detail_metadata:
        warnings.append(
            "Search Console reported incomplete recent data; inspect provider metadata before comparison."
        )
    if dims:
        warnings.append(
            "Visible dimension rows can exclude anonymized or lower-volume data and must not be summed as property totals."
        )
    return warnings


def query_result(
    source: str, property_value: str, start: str, end: str, dims: list[str],
    row_limit: int, max_pages: int, data_state: str, search_type: str, aggregation_type: str,
    aggregate_response: dict[str, Any], aggregate: dict[str, float], rows: list[dict[str, Any]],
    truncated: bool, detail_pages: int, detail_metadata: list[dict[str, Any]],
    request_telemetry: list[dict[str, Any]],
) -> AdapterResult:
    aggregate_metadata = aggregate_response.get("metadata") or {}
    warnings = _query_warnings(truncated, aggregate_metadata, detail_metadata, dims)
    if not aggregate_response.get("rows") and not rows:
        normalized_state = "EMPTY"
    elif truncated or aggregate_metadata or detail_metadata:
        normalized_state = "PARTIAL"
    else:
        normalized_state = "AVAILABLE"
    adapter_status = {
        "AVAILABLE": "ok",
        "EMPTY": "ok",
        "PARTIAL": "partial",
    }[normalized_state]
    return AdapterResult(
        source=source,
        status=adapter_status,
        data={
            "site_url": property_value,
            "aggregate": aggregate,
            "aggregate_source": "dimensionless_aggregate_query",
            "rows": rows,
            "row_count": len(rows),
            "dimensions": dims,
            "date_range": {
                "start": start,
                "end": end,
                "timezone": "America/Los_Angeles",
            },
            "pagination": {
                "row_limit": row_limit,
                "max_pages": max_pages,
                "detail_pages_requested": detail_pages,
                "rows_truncated": truncated,
            },
            "data_state": normalized_state,
            "provider_data_state": data_state,
            "search_type": search_type,
            "aggregation_type": aggregate_response.get(
                "responseAggregationType",
                aggregation_type,
            ),
            "provider_metadata": {
                "aggregate": aggregate_metadata,
                "detail_pages": detail_metadata,
            },
            "request_metadata": request_telemetry,
            "warnings": warnings,
            "limitations": [
                "Search Analytics returns top rows and does not guarantee every dimension row.",
                "Dimension rows must not be summed to replace the separate aggregate totals.",
            ],
        },
        warnings=warnings,
    )
