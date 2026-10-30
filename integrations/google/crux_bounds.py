"""Validate returned CrUX dimensions before constructing retained cross-products."""

from __future__ import annotations

from typing import Any


def history_array(value: Any, maximum: int) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError('CrUX History provider returned invalid array dimensions')
    return value


def history_dimensions(metric: dict[str, Any], periods: list[dict[str, Any]]) -> None:
    history_array(periods, 40)
    if not isinstance(metric, dict):
        raise ValueError('CrUX History provider returned invalid metric dimensions')
    percentiles = metric.get('percentilesTimeseries') or {}
    if not isinstance(percentiles, dict):
        raise ValueError('CrUX History provider returned invalid percentile dimensions')
    history_array(percentiles.get('p75s'), 40)
    for histogram in history_array(metric.get('histogramTimeseries'), 50):
        if not isinstance(histogram, dict):
            raise ValueError('CrUX History provider returned invalid histogram dimensions')
        history_array(histogram.get('densities'), 40)
