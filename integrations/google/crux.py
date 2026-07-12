"""Chrome UX Report History API integration and LCP subpart analysis."""

from __future__ import annotations

import os
from typing import Any

from adapters.base import AdapterNotConfigured, AdapterResult
from adapters.url_safety import validate_public_url
from integrations.google.client import GoogleJsonClient

CRUX_HISTORY_ENDPOINT = (
    "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord"
)
_FORM_FACTORS = {"mobile": "PHONE", "desktop": "DESKTOP", "tablet": "TABLET"}
_DEFAULT_METRICS = [
    "cumulative_layout_shift",
    "first_contentful_paint",
    "interaction_to_next_paint",
    "largest_contentful_paint",
    "experimental_time_to_first_byte",
    "largest_contentful_paint_image_time_to_first_byte",
    "largest_contentful_paint_image_resource_load_delay",
    "largest_contentful_paint_image_resource_load_duration",
    "largest_contentful_paint_image_element_render_delay",
]
_LCP_PARTS = [
    "largest_contentful_paint_image_time_to_first_byte",
    "largest_contentful_paint_image_resource_load_delay",
    "largest_contentful_paint_image_resource_load_duration",
    "largest_contentful_paint_image_element_render_delay",
]


class CrUXHistoryAdapter:
    name = "google_crux_history"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: GoogleJsonClient | None = None,
    ) -> None:
        self.api_key = (
            api_key
            or os.getenv("GOOGLE_CRUX_API_KEY")
            or os.getenv("GOOGLE_PAGESPEED_API_KEY")
        )
        self.client = client or GoogleJsonClient(
            allowed_hosts={"chromeuxreport.googleapis.com"}
        )

    def fetch(
        self,
        target: str,
        target_type: str = "url",
        form_factor: str = "mobile",
        metrics: list[str] | None = None,
        collection_period_count: int = 25,
        **_: Any,
    ) -> AdapterResult:
        if not self.api_key:
            raise AdapterNotConfigured(
                "Set GOOGLE_CRUX_API_KEY or GOOGLE_PAGESPEED_API_KEY."
            )
        normalized_type = target_type.strip().lower()
        if normalized_type not in {"url", "origin"}:
            raise ValueError("target_type must be url or origin")
        safe_target = validate_public_url(target)
        if normalized_type == "origin":
            from urllib.parse import urlsplit

            parsed = urlsplit(safe_target)
            safe_target = f"{parsed.scheme}://{parsed.netloc}"
        normalized_form = form_factor.strip().lower()
        if normalized_form not in _FORM_FACTORS:
            raise ValueError(f"form_factor must be one of {sorted(_FORM_FACTORS)}")
        if not isinstance(collection_period_count, int) or not 1 <= collection_period_count <= 40:
            raise ValueError("collection_period_count must be an integer from 1 to 40")
        selected_metrics = list(metrics or _DEFAULT_METRICS)
        if not selected_metrics or len(selected_metrics) != len(set(selected_metrics)):
            raise ValueError("metrics must be a non-empty unique list")

        response = self.client.request(
            CRUX_HISTORY_ENDPOINT,
            service="crux_history",
            payload={
                normalized_type: safe_target,
                "formFactor": _FORM_FACTORS[normalized_form],
                "metrics": selected_metrics,
                "collectionPeriodCount": collection_period_count,
            },
            api_key=self.api_key,
        )
        record = response.get("record") or {}
        collection_periods = record.get("collectionPeriods") or []
        metric_data = record.get("metrics") or {}
        series = {
            metric: self._normalize_metric_series(metric_data.get(metric) or {}, collection_periods)
            for metric in selected_metrics
        }
        available = {
            metric: values
            for metric, values in series.items()
            if any(item.get("p75") is not None for item in values)
        }
        warnings: list[str] = []
        if not collection_periods:
            warnings.append("CrUX History returned no collection periods for this target.")
        unavailable = sorted(set(selected_metrics) - set(available))
        if unavailable:
            warnings.append(
                "No p75 history was available for: " + ", ".join(unavailable)
            )
        lcp = decompose_lcp_history(series)
        return AdapterResult(
            source=self.name,
            status="ok" if collection_periods and available else "partial",
            data={
                "target": safe_target,
                "target_type": normalized_type,
                "form_factor": _FORM_FACTORS[normalized_form],
                "collection_period_count_requested": collection_period_count,
                "collection_period_count_returned": len(collection_periods),
                "collection_periods": collection_periods,
                "metrics": series,
                "lcp_subparts": lcp,
                "update_model": {
                    "cadence": "weekly_best_effort",
                    "rolling_window_days": 28,
                    "maximum_periods": 40,
                    "default_periods": 25,
                    "overlapping_periods": True,
                },
                "limitations": [
                    "Each weekly point is a 28-day rolling aggregate, so adjacent periods overlap.",
                    "Missing CrUX data means the target lacks an eligible field record; it does not prove good or bad performance."
                ],
            },
            warnings=warnings,
        )

    @staticmethod
    def _normalize_metric_series(
        metric: dict[str, Any],
        collection_periods: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        percentiles = metric.get("percentilesTimeseries") or {}
        p75_values = percentiles.get("p75s") or []
        histograms = (metric.get("histogramTimeseries") or {}).get("histogramTimeseries") or []
        output: list[dict[str, Any]] = []
        count = max(len(collection_periods), len(p75_values))
        for index in range(count):
            value = p75_values[index] if index < len(p75_values) else None
            if value is not None:
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    value = None
            bins = []
            for histogram in histograms:
                densities = histogram.get("densities") or []
                bins.append(
                    {
                        "start": histogram.get("start"),
                        "end": histogram.get("end"),
                        "density": densities[index] if index < len(densities) else None,
                    }
                )
            output.append(
                {
                    "collection_period": (
                        collection_periods[index]
                        if index < len(collection_periods)
                        else None
                    ),
                    "p75": value,
                    "histogram": bins,
                }
            )
        return output


def decompose_lcp_history(
    metric_series: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Return latest observed image-LCP subparts without inventing missing values."""
    latest: dict[str, float | None] = {}
    for metric in ["largest_contentful_paint", *_LCP_PARTS]:
        values = metric_series.get(metric) or []
        latest_value = next(
            (
                item.get("p75")
                for item in reversed(values)
                if item.get("p75") is not None
            ),
            None,
        )
        latest[metric] = float(latest_value) if latest_value is not None else None

    part_values = [latest[item] for item in _LCP_PARTS]
    complete = all(value is not None for value in part_values)
    subpart_sum = sum(value for value in part_values if value is not None) if complete else None
    observed_lcp = latest["largest_contentful_paint"]
    residual = (
        observed_lcp - subpart_sum
        if observed_lcp is not None and subpart_sum is not None
        else None
    )
    names = {
        _LCP_PARTS[0]: "time_to_first_byte",
        _LCP_PARTS[1]: "resource_load_delay",
        _LCP_PARTS[2]: "resource_load_duration",
        _LCP_PARTS[3]: "element_render_delay",
    }
    parts = {names[key]: latest[key] for key in _LCP_PARTS}
    largest = (
        max(
            ((name, value) for name, value in parts.items() if value is not None),
            key=lambda item: item[1],
            default=(None, None),
        )
    )
    return {
        "latest_lcp_p75_ms": observed_lcp,
        "parts_ms": parts,
        "parts_complete": complete,
        "parts_sum_ms": subpart_sum,
        "lcp_minus_parts_ms": residual,
        "largest_observed_part": {
            "name": largest[0],
            "value_ms": largest[1],
        },
        "interpretation": (
            "Subparts are observed CrUX field metrics for image LCP. Missing values are not estimated."
        ),
    }
