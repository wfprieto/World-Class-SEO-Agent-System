"""Chrome UX Report current/history integrations and LCP subpart analysis."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from contracts.adapter import AdapterNotConfigured, AdapterResult
from integrations.google.client import GoogleAPIError, GoogleJsonClient
from integrations.google.crux_bounds import history_array, history_dimensions
from integrations.google.crux_lcp import _LCP_PARTS as _LCP_PARTS
from integrations.google.crux_lcp import decompose_lcp_history as decompose_lcp_history
from security.url_safety import validate_public_url

CRUX_CURRENT_ENDPOINT = (
    "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
)
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



def _credentials(api_key: str | None) -> str:
    resolved = (
        api_key
        or os.getenv("GOOGLE_CRUX_API_KEY")
        or os.getenv("GOOGLE_PAGESPEED_API_KEY")
    )
    if not resolved:
        raise AdapterNotConfigured(
            "Set GOOGLE_CRUX_API_KEY or GOOGLE_PAGESPEED_API_KEY."
        )
    return resolved


def _target(value: str, target_type: str) -> tuple[str, str]:
    normalized_type = target_type.strip().lower()
    if normalized_type not in {"url", "origin"}:
        raise ValueError("target_type must be url or origin")
    safe_target = validate_public_url(value)
    if normalized_type == "origin":
        parsed = urlsplit(safe_target)
        safe_target = f"{parsed.scheme}://{parsed.netloc}"
    return safe_target, normalized_type


def _form_factor(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in _FORM_FACTORS:
        raise ValueError(f"form_factor must be one of {sorted(_FORM_FACTORS)}")
    return _FORM_FACTORS[normalized]


def _metrics(values: list[str] | None) -> list[str]:
    selected = list(values or _DEFAULT_METRICS)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("metrics must be a non-empty unique list")
    if len(selected) > 50 or any(not isinstance(item, str) or not item for item in selected):
        raise ValueError("metrics must contain at most 50 non-empty names")
    return selected


def _not_found(
    *,
    source: str,
    target: str,
    target_type: str,
    form_factor: str,
    error: GoogleAPIError,
) -> AdapterResult:
    return AdapterResult(
        source=source,
        status="not_found",
        data={
            "target": target,
            "target_type": target_type,
            "form_factor": form_factor,
            "data_state": "NOT_FOUND",
            "metrics": {},
            "request_metadata": {},
            "limitations": [
                "No eligible CrUX field record was found for this target and form factor.",
                "A missing record is not a zero score and does not prove good or bad performance.",
            ],
        },
        warnings=[str(error)],
    )


class CrUXCurrentAdapter:
    name = "google_crux_current"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: GoogleJsonClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.client = client or GoogleJsonClient(
            allowed_hosts={"chromeuxreport.googleapis.com"}
        )

    def fetch(
        self,
        target: str,
        target_type: str = "url",
        form_factor: str = "mobile",
        metrics: list[str] | None = None,
        **_: Any,
    ) -> AdapterResult:
        key = _credentials(self.api_key)
        safe_target, normalized_type = _target(target, target_type)
        normalized_form = _form_factor(form_factor)
        selected_metrics = _metrics(metrics)
        try:
            response = self.client.request(
                CRUX_CURRENT_ENDPOINT,
                service="crux_current",
                payload={
                    normalized_type: safe_target,
                    "formFactor": normalized_form,
                    "metrics": selected_metrics,
                },
                api_key=key,
            )
        except GoogleAPIError as exc:
            if exc.state == "NOT_FOUND":
                return _not_found(
                    source=self.name,
                    target=safe_target,
                    target_type=normalized_type,
                    form_factor=normalized_form,
                    error=exc,
                )
            raise
        record = response.get("record") or {}
        raw_metrics = record.get("metrics") or {}
        normalized_metrics = {
            name: self._normalize_metric(raw_metrics.get(name) or {})
            for name in selected_metrics
            if raw_metrics.get(name)
        }
        warnings: list[str] = []
        unavailable = sorted(set(selected_metrics) - set(normalized_metrics))
        if unavailable:
            warnings.append("No current CrUX evidence was returned for: " + ", ".join(unavailable))
        data_state = "AVAILABLE" if normalized_metrics else "EMPTY"
        return AdapterResult(
            source=self.name,
            status="ok" if normalized_metrics else "partial",
            data={
                "target": safe_target,
                "target_type": normalized_type,
                "form_factor": normalized_form,
                "collection_period": record.get("collectionPeriod"),
                "metrics": normalized_metrics,
                "data_state": data_state,
                "request_metadata": dict(getattr(self.client, "last_telemetry", {}) or {}),
                "limitations": [
                    "CrUX current data is an eligible-user field aggregate, not a lab test.",
                    "Mobile, desktop, and tablet records are separate and are never blended.",
                ],
            },
            warnings=warnings,
        )

    @staticmethod
    def _normalize_metric(metric: dict[str, Any]) -> dict[str, Any]:
        percentiles = metric.get("percentiles") or {}
        value = percentiles.get("p75")
        try:
            p75 = float(value) if value is not None else None
        except (TypeError, ValueError):
            p75 = None
        histogram = []
        for item in metric.get("histogram") or []:
            if not isinstance(item, dict):
                continue
            histogram.append(
                {
                    "start": item.get("start"),
                    "end": item.get("end"),
                    "density": item.get("density"),
                }
            )
        return {"p75": p75, "histogram": histogram}


class CrUXHistoryAdapter:
    name = "google_crux_history"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: GoogleJsonClient | None = None,
    ) -> None:
        self.api_key = api_key
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
        key = _credentials(self.api_key)
        safe_target, normalized_type = _target(target, target_type)
        normalized_form = _form_factor(form_factor)
        if not isinstance(collection_period_count, int) or not 1 <= collection_period_count <= 40:
            raise ValueError("collection_period_count must be an integer from 1 to 40")
        selected_metrics = _metrics(metrics)
        try:
            response = self.client.request(
                CRUX_HISTORY_ENDPOINT,
                service="crux_history",
                payload={
                    normalized_type: safe_target,
                    "formFactor": normalized_form,
                    "metrics": selected_metrics,
                    "collectionPeriodCount": collection_period_count,
                },
                api_key=key,
            )
        except GoogleAPIError as exc:
            if exc.state == "NOT_FOUND":
                return _not_found(
                    source=self.name,
                    target=safe_target,
                    target_type=normalized_type,
                    form_factor=normalized_form,
                    error=exc,
                )
            raise
        record = response.get("record") or {}
        collection_periods = history_array(record.get("collectionPeriods"), 40)
        series, available, warnings = self._history_series(record, collection_periods, selected_metrics)
        lcp = decompose_lcp_history(series)
        data_state = "AVAILABLE" if collection_periods and available else "EMPTY"
        return AdapterResult(
            source=self.name,
            status="ok" if data_state == "AVAILABLE" else "partial",
            data={
                "target": safe_target,
                "target_type": normalized_type,
                "form_factor": normalized_form,
                "collection_period_count_requested": collection_period_count,
                "collection_period_count_returned": len(collection_periods),
                "collection_periods": collection_periods,
                "metrics": series,
                "lcp_subparts": lcp,
                "data_state": data_state,
                "request_metadata": dict(getattr(self.client, "last_telemetry", {}) or {}),
                "update_model": {
                    "cadence": "weekly_best_effort",
                    "rolling_window_days": 28,
                    "maximum_periods": 40,
                    "default_periods": 25,
                    "overlapping_periods": True,
                },
                "limitations": [
                    "Each weekly point is a 28-day rolling aggregate, so adjacent periods overlap.",
                    "Missing CrUX data means the target lacks an eligible field record; it does not prove good or bad performance.",
                ],
            },
            warnings=warnings,
        )

    @staticmethod
    def _history_series(
        record: dict[str, Any], collection_periods: list[dict[str, Any]], selected_metrics: list[str],
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], list[str]]:
        metric_data = record.get("metrics") or {}
        series = {
            metric: CrUXHistoryAdapter._normalize_metric_series(metric_data.get(metric) or {}, collection_periods)
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
        return series, available, warnings

    @staticmethod
    def _normalize_metric_series(
        metric: dict[str, Any],
        collection_periods: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        history_dimensions(metric, collection_periods)
        percentiles = metric.get("percentilesTimeseries") or {}
        p75_values = percentiles.get("p75s") or []
        histograms = metric.get("histogramTimeseries") or []
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
                if not isinstance(histogram, dict):
                    continue
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
