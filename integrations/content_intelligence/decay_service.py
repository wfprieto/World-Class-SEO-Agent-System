"""Deterministic content intelligence with explicit truth boundaries.

The service measures supplied text and supplied review records. It does not
claim Google ranking potential, originality, factual accuracy, expertise,
source existence, user satisfaction, or causal explanations that were not
independently established.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from contracts.adapter import AdapterResult
from integrations.content_intelligence.analysis import (
    number_or_none,
    parse_period,
)


def decay(
    name: str,
    *,
    current: dict[str, Any],
    prior: dict[str, Any],
    decline_threshold: float = 0.2,
    **_: Any,
) -> AdapterResult:
    current_range, prior_range, current_metrics, prior_metrics = _comparison_inputs(
        current, prior, decline_threshold
    )
    metric_names = sorted(set(current_metrics) | set(prior_metrics))
    normalized: dict[str, dict[str, Any]] = {}
    decline_signals: list[str] = []
    warnings: list[str] = []
    for metric in metric_names:
        previous = number_or_none(prior_metrics.get(metric), f"prior metric {metric}")
        present = number_or_none(current_metrics.get(metric), f"current metric {metric}")
        normalized[metric], declined = _metric_change(
            metric, previous, present, float(decline_threshold)
        )
        if declined:
            decline_signals.append(metric)
        if previous is None or present is None:
            warnings.append(f"Metric {metric} is missing from one comparison period.")
    signal = "OBSERVED_DECLINE" if decline_signals else "NO_THRESHOLD_DECLINE_OBSERVED"
    if decline_signals:
        warnings.append("Observed decline threshold exceeded for: " + ", ".join(decline_signals))
    return AdapterResult(
        source=name,
        status="needs-review" if decline_signals else "ok",
        data={
            "operation": "decay",
            "data_state": "PARTIAL" if warnings else "AVAILABLE",
            "prior_period": {
                "start": prior_range[0].isoformat(),
                "end": prior_range[1].isoformat(),
            },
            "current_period": {
                "start": current_range[0].isoformat(),
                "end": current_range[1].isoformat(),
            },
            "decline_threshold": float(decline_threshold),
            "metrics": normalized,
            "decline_metrics": decline_signals,
            "decay_signal": signal,
            "cause": "NOT_ASSESSED",
            "recommended_next_evidence": [
                "Confirm comparable query, page, market, device, and attribution scope.",
                "Review technical, SERP, competitor, seasonality, and conversion evidence before assigning cause.",
            ],
            "limitations": [
                "A period-over-period decline is an observation, not proof of content decay or its cause.",
                "Metric definitions and attribution windows must be equivalent for a valid comparison.",
            ],
        },
        warnings=warnings,
    )


def _metric_direction(metric: str, previous: float, present: float) -> str:
    lower_is_better = metric.lower() in {
        "average_position",
        "avg_position",
        "bounce_rate",
        "error_rate",
        "latency",
        "lcp_ms",
        "inp_ms",
        "cls",
    }
    if math.isclose(present, previous):
        return "stable"
    if (present < previous and not lower_is_better) or (present > previous and lower_is_better):
        return "worse"
    return "better"


def _metric_change(
    metric: str,
    previous: float | None,
    present: float | None,
    threshold: float,
) -> tuple[dict[str, Any], bool]:
    percent_change = None
    absolute_change = None
    direction = "not_comparable"
    declined = False
    if previous is not None and present is not None:
        absolute_change = present - previous
        percent_change = round(absolute_change / abs(previous), 6) if previous != 0 else None
        direction = _metric_direction(metric, previous, present)
        if direction == "worse":
            magnitude = (
                abs(percent_change)
                if percent_change is not None
                else math.inf
                if previous == 0 and present != 0
                else 0
            )
            declined = magnitude >= threshold
    return {
        "prior": previous,
        "current": present,
        "absolute_change": absolute_change,
        "percent_change": percent_change,
        "direction": direction,
    }, declined


def _comparison_inputs(
    current: dict[str, Any], prior: dict[str, Any], decline_threshold: float
) -> tuple[tuple[date, date], tuple[date, date], dict[str, Any], dict[str, Any]]:
    if not isinstance(current, dict) or not isinstance(prior, dict):
        raise TypeError("current and prior snapshots must be objects")
    if not isinstance(decline_threshold, (int, float)) or not 0 < float(decline_threshold) <= 1:
        raise ValueError("decline_threshold must be greater than 0 and at most 1")
    current_range = parse_period(current, "current")
    prior_range = parse_period(prior, "prior")
    if current_range[0] <= prior_range[1]:
        raise ValueError("current period must start after prior period ends")
    current_metrics = current.get("metrics") or {}
    prior_metrics = prior.get("metrics") or {}
    if not isinstance(current_metrics, dict) or not isinstance(prior_metrics, dict):
        raise TypeError("snapshot metrics must be objects")

    return current_range, prior_range, current_metrics, prior_metrics
