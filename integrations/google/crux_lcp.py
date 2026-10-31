"""Observed image-LCP subparts, with no estimation of missing evidence."""
from __future__ import annotations

from typing import Any

_LCP_PARTS = [
    "largest_contentful_paint_image_time_to_first_byte",
    "largest_contentful_paint_image_resource_load_delay",
    "largest_contentful_paint_image_resource_load_duration",
    "largest_contentful_paint_image_element_render_delay",
]

def _latest_observed(metric_series: dict[str, list[dict[str, Any]]]) -> dict[str, float | None]:
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
    return latest


def decompose_lcp_history(
    metric_series: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Return latest observed image-LCP subparts without inventing values."""
    latest = _latest_observed(metric_series)

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
    largest = max(
        ((name, value) for name, value in parts.items() if value is not None),
        key=lambda item: item[1],
        default=(None, None),
    )
    return {
        "evidence_state": "AVAILABLE" if complete and observed_lcp is not None else "INSUFFICIENT_EVIDENCE",
        "source": "crux_history_field_metrics",
        "unit": "milliseconds",
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
