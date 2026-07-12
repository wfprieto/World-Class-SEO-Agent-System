"""Google first-party command family for seoctl."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Callable

from adapters.base import AdapterNotConfigured
from adapters.google_pagespeed_live import GooglePageSpeedLiveAdapter
from integrations.google.client import GoogleAPIError
from integrations.google.crux import CrUXHistoryAdapter
from integrations.google.ga4 import GoogleAnalyticsDataAdapter
from integrations.google.gsc import GoogleSearchConsoleAdapter
from seoctl.cli import (
    EXIT_BLOCKED,
    EXIT_FAILED,
    EXIT_INPUT,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    envelope,
)


def _list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _gsc_query(args: argparse.Namespace):
    result = GoogleSearchConsoleAdapter().query(
        site_url=args.site_url,
        start_date=args.start_date,
        end_date=args.end_date,
        dimensions=args.dimension,
        row_limit=args.row_limit,
        max_pages=args.max_pages,
        search_type=args.search_type,
        aggregation_type=args.aggregation_type,
        data_state=args.data_state,
    )
    return envelope("google.gsc-query", result.status, result.data, warnings=result.warnings), EXIT_OK


def _gsc_inspect(args: argparse.Namespace):
    result = GoogleSearchConsoleAdapter().inspect(
        inspection_url=args.url,
        site_url=args.site_url,
        language_code=args.language_code,
    )
    return envelope("google.gsc-inspect", result.status, result.data, warnings=result.warnings), EXIT_OK


def _ga4_report(args: argparse.Namespace):
    result = GoogleAnalyticsDataAdapter().fetch(
        property_id=args.property_id,
        start_date=args.start_date,
        end_date=args.end_date,
        dimensions=args.dimension,
        metrics=args.metric,
        limit=args.limit,
        offset=args.offset,
        currency_code=args.currency_code,
    )
    return envelope("google.ga4-report", result.status, result.data, warnings=result.warnings), EXIT_OK


def _pagespeed(args: argparse.Namespace):
    result = GooglePageSpeedLiveAdapter().fetch(
        url=args.url,
        strategy=args.strategy,
        include_crux=not args.no_crux,
    )
    return envelope("google.pagespeed", result.status, result.data, warnings=result.warnings), EXIT_OK


def _crux_history(args: argparse.Namespace):
    result = CrUXHistoryAdapter().fetch(
        target=args.target,
        target_type=args.target_type,
        form_factor=args.form_factor,
        metrics=args.metric or None,
        collection_period_count=args.periods,
    )
    return envelope("google.crux-history", result.status, result.data, warnings=result.warnings), EXIT_OK


def _lcp_subparts(args: argparse.Namespace):
    metrics = [
        "largest_contentful_paint",
        "largest_contentful_paint_image_time_to_first_byte",
        "largest_contentful_paint_image_resource_load_delay",
        "largest_contentful_paint_image_resource_load_duration",
        "largest_contentful_paint_image_element_render_delay",
    ]
    result = CrUXHistoryAdapter().fetch(
        target=args.target,
        target_type=args.target_type,
        form_factor=args.form_factor,
        metrics=metrics,
        collection_period_count=args.periods,
    )
    data = {
        "target": result.data["target"],
        "target_type": result.data["target_type"],
        "form_factor": result.data["form_factor"],
        "collection_period_count_returned": result.data["collection_period_count_returned"],
        "lcp_subparts": result.data["lcp_subparts"],
        "limitations": result.data["limitations"],
    }
    return envelope("google.lcp-subparts", result.status, data, warnings=result.warnings), EXIT_OK


HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "google_gsc_query": _gsc_query,
    "google_gsc_inspect": _gsc_inspect,
    "google_ga4_report": _ga4_report,
    "google_pagespeed": _pagespeed,
    "google_crux_history": _crux_history,
    "google_lcp_subparts": _lcp_subparts,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seoctl google",
        description="Google first-party SEO and analytics commands",
    )
    sub = parser.add_subparsers(dest="action")

    gsc = sub.add_parser("gsc-query", help="Query Search Analytics with separate aggregate totals")
    gsc.add_argument("--site-url", required=True)
    gsc.add_argument("--start-date")
    gsc.add_argument("--end-date")
    gsc.add_argument("--dimension", action="append", default=[])
    gsc.add_argument("--row-limit", type=int, default=25000)
    gsc.add_argument("--max-pages", type=int, default=4)
    gsc.add_argument("--search-type", default="web")
    gsc.add_argument("--aggregation-type", default="auto")
    gsc.add_argument("--data-state", default="final")
    gsc.set_defaults(handler="google_gsc_query")

    inspect = sub.add_parser("gsc-inspect", help="Inspect the version of a URL in Google's index")
    inspect.add_argument("--url", required=True)
    inspect.add_argument("--site-url", required=True)
    inspect.add_argument("--language-code", default="en-US")
    inspect.set_defaults(handler="google_gsc_inspect")

    ga4 = sub.add_parser("ga4-report", help="Run a GA4 Data API report with provider totals")
    ga4.add_argument("--property-id", required=True)
    ga4.add_argument("--start-date")
    ga4.add_argument("--end-date")
    ga4.add_argument("--dimension", action="append", default=[])
    ga4.add_argument("--metric", action="append", default=[])
    ga4.add_argument("--limit", type=int, default=10000)
    ga4.add_argument("--offset", type=int, default=0)
    ga4.add_argument("--currency-code")
    ga4.set_defaults(handler="google_ga4_report")

    pagespeed = sub.add_parser("pagespeed", help="Run PageSpeed lab and optional current CrUX evidence")
    pagespeed.add_argument("--url", required=True)
    pagespeed.add_argument("--strategy", choices=["mobile", "desktop"], default="mobile")
    pagespeed.add_argument("--no-crux", action="store_true")
    pagespeed.set_defaults(handler="google_pagespeed")

    history = sub.add_parser("crux-history", help="Query 1 to 40 rolling CrUX collection periods")
    history.add_argument("--target", required=True)
    history.add_argument("--target-type", choices=["url", "origin"], default="url")
    history.add_argument("--form-factor", choices=["mobile", "desktop", "tablet"], default="mobile")
    history.add_argument("--metric", action="append", default=[])
    history.add_argument("--periods", type=int, default=25)
    history.set_defaults(handler="google_crux_history")

    lcp = sub.add_parser("lcp-subparts", help="Decompose latest image LCP field subparts")
    lcp.add_argument("--target", required=True)
    lcp.add_argument("--target-type", choices=["url", "origin"], default="url")
    lcp.add_argument("--form-factor", choices=["mobile", "desktop", "tablet"], default="mobile")
    lcp.add_argument("--periods", type=int, default=25)
    lcp.set_defaults(handler="google_lcp_subparts")
    return parser


def run(argv: list[str] | None = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    handler_name = getattr(args, "handler", None)
    if not handler_name:
        return envelope(
            "google.unknown",
            "input_error",
            error={"type": "MissingCommand", "message": "Choose a Google command."},
        ), EXIT_INPUT
    try:
        return HANDLERS[handler_name](args)
    except AdapterNotConfigured as exc:
        return envelope(
            "google." + str(args.action),
            "unavailable",
            error={"type": type(exc).__name__, "message": str(exc)},
        ), EXIT_UNAVAILABLE
    except GoogleAPIError as exc:
        status = "unavailable" if exc.status in {None, 429, 500, 502, 503, 504} else "failed"
        code = EXIT_UNAVAILABLE if status == "unavailable" else EXIT_FAILED
        return envelope(
            "google." + str(args.action),
            status,
            error={"type": type(exc).__name__, "message": str(exc)},
        ), code
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return envelope(
            "google." + str(args.action),
            "input_error",
            error={"type": type(exc).__name__, "message": str(exc)},
        ), EXIT_INPUT
    except Exception as exc:  # noqa: BLE001
        return envelope(
            "google." + str(args.action),
            "failed",
            error={"type": type(exc).__name__, "message": str(exc)},
        ), EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    payload, code = run(argv)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code
