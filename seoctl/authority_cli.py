"""Authority, media, provenance, and drift command families."""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from integrations.authority_media.services import (
    BacklinkProfileService,
    CommonCrawlService,
    DomainHistoryService,
    DriftService,
    IPTCLabelService,
    TranscriptService,
    YouTubeSearchService,
)
from seoctl.cli import EXIT_BLOCKED, EXIT_FAILED, EXIT_INPUT, EXIT_OK, EXIT_UNAVAILABLE, envelope


def _result(command: str, result):  # type: ignore[no-untyped-def]
    if result.status in {"ok", "empty", "partial"}:
        code = EXIT_OK
    elif result.status in {"not_configured", "not_found", "unavailable"}:
        code = EXIT_UNAVAILABLE
    elif result.status == "blocked":
        code = EXIT_BLOCKED
    else:
        code = EXIT_FAILED
    return envelope(command, result.status, result.data, warnings=result.warnings), code


def _links_commoncrawl(args: argparse.Namespace):
    return _result(
        "links.commoncrawl",
        CommonCrawlService().search(
            args.domain,
            fixture_path=args.fixture,
            index=args.index,
            max_pages=args.max_pages,
            page_size=args.page_size,
        ),
    )


def _links_profile(args: argparse.Namespace):
    return _result("links.profile", BacklinkProfileService().profile(args.input))


def _links_gap(args: argparse.Namespace):
    return _result("links.gap", BacklinkProfileService().gap(args.target, args.competitor))


def _domain_history(args: argparse.Namespace):
    return _result("domain.history", DomainHistoryService().history(args.domain, fixture_path=args.fixture))


def _youtube_search(args: argparse.Namespace):
    return _result(
        "media.youtube-search",
        YouTubeSearchService().search(
            args.query,
            fixture_path=args.fixture,
            max_results=args.max_results,
            pages=args.pages,
            region_code=args.region_code,
            relevance_language=args.relevance_language,
            order=args.order,
            safe_search=args.safe_search,
        ),
    )


def _iptc_label(args: argparse.Namespace):
    return _result(
        "media.iptc-label",
        IPTCLabelService().inspect(
            args.input,
            label=args.label,
            write=args.write,
            authorize_write=args.authorize_write,
            output_path=args.output,
        ),
    )


def _transcript_check(args: argparse.Namespace):
    return _result("media.transcript-check", TranscriptService().check(args.input, video_id=args.video_id))


def _drift_baseline(args: argparse.Namespace):
    return _result("drift.baseline", DriftService().baseline(args.url, args.state, db_path=args.db))


def _drift_compare(args: argparse.Namespace):
    return _result("drift.compare", DriftService().compare(args.url, db_path=args.db))


def _drift_history(args: argparse.Namespace):
    return _result("drift.history", DriftService().history(args.url, db_path=args.db, limit=args.limit))


def _drift_report(args: argparse.Namespace):
    return _result("drift.report", DriftService().report(args.url, db_path=args.db, output_path=args.output))


def _drift_watch(args: argparse.Namespace):
    return _result("drift.watch", DriftService().watch(args.url, args.state, db_path=args.db))


HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "links_commoncrawl": _links_commoncrawl,
    "links_profile": _links_profile,
    "links_gap": _links_gap,
    "domain_history": _domain_history,
    "media_youtube_search": _youtube_search,
    "media_iptc_label": _iptc_label,
    "media_transcript_check": _transcript_check,
    "drift_baseline": _drift_baseline,
    "drift_compare": _drift_compare,
    "drift_history": _drift_history,
    "drift_report": _drift_report,
    "drift_watch": _drift_watch,
}


def build_parser(family: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"seoctl {family}", description="Bounded authority, media, and drift execution")
    sub = parser.add_subparsers(dest="action")
    if family == "links":
        commoncrawl = sub.add_parser("commoncrawl", help="Query a bounded Common Crawl URL-index sample")
        commoncrawl.add_argument("--domain", required=True)
        commoncrawl.add_argument("--fixture")
        commoncrawl.add_argument("--index")
        commoncrawl.add_argument("--max-pages", type=int, default=1)
        commoncrawl.add_argument("--page-size", type=int, default=100)
        commoncrawl.set_defaults(handler="links_commoncrawl")
        profile = sub.add_parser("profile", help="Normalize a supplied backlink export")
        profile.add_argument("--input", required=True)
        profile.set_defaults(handler="links_profile")
        gap = sub.add_parser("gap", help="Compare supplied target and competitor backlink exports")
        gap.add_argument("--target", required=True)
        gap.add_argument("--competitor", required=True)
        gap.set_defaults(handler="links_gap")
    elif family == "domain":
        history = sub.add_parser("history", help="Retrieve or normalize public RDAP registration history")
        history.add_argument("--domain", required=True)
        history.add_argument("--fixture")
        history.set_defaults(handler="domain_history")
    elif family == "media":
        youtube = sub.add_parser("youtube-search", help="Run bounded YouTube Data API search or a fixture")
        youtube.add_argument("--query", required=True)
        youtube.add_argument("--fixture")
        youtube.add_argument("--max-results", type=int, default=25)
        youtube.add_argument("--pages", type=int, default=1)
        youtube.add_argument("--region-code")
        youtube.add_argument("--relevance-language")
        youtube.add_argument("--order", choices=["date", "rating", "relevance", "title", "videoCount", "viewCount"], default="relevance")
        youtube.add_argument("--safe-search", choices=["moderate", "none", "strict"], default="moderate")
        youtube.set_defaults(handler="media_youtube_search")
        iptc = sub.add_parser("iptc-label", help="Validate or explicitly write an IPTC Digital Source Type JSON sidecar")
        iptc.add_argument("--input", required=True)
        iptc.add_argument("--label")
        iptc.add_argument("--write", action="store_true")
        iptc.add_argument("--authorize-write", action="store_true")
        iptc.add_argument("--output")
        iptc.set_defaults(handler="media_iptc_label")
        transcript = sub.add_parser("transcript-check", help="Run deterministic structural checks on a transcript file")
        transcript.add_argument("--input", required=True)
        transcript.add_argument("--video-id")
        transcript.set_defaults(handler="media_transcript_check")
    elif family == "drift":
        for name, help_text, handler in (
            ("baseline", "Record a page-state baseline in the canonical EvidenceStore", "drift_baseline"),
            ("watch", "Perform one bounded capture-and-compare operation", "drift_watch"),
        ):
            command = sub.add_parser(name, help=help_text)
            command.add_argument("--url", required=True)
            command.add_argument("--state", required=True)
            command.add_argument("--db")
            command.set_defaults(handler=handler)
        compare = sub.add_parser("compare", help="Compare the two latest compatible page-state snapshots")
        compare.add_argument("--url", required=True)
        compare.add_argument("--db")
        compare.set_defaults(handler="drift_compare")
        history = sub.add_parser("history", help="Read verified page-state history")
        history.add_argument("--url", required=True)
        history.add_argument("--db")
        history.add_argument("--limit", type=int, default=20)
        history.set_defaults(handler="drift_history")
        report = sub.add_parser("report", help="Render the current drift verdict as JSON")
        report.add_argument("--url", required=True)
        report.add_argument("--db")
        report.add_argument("--output")
        report.set_defaults(handler="drift_report")
    else:
        raise ValueError("family must be links, domain, media, or drift")
    return parser


def run(argv: list[str] | None = None):
    arguments = list(argv or [])
    if not arguments or arguments[0] not in {"links", "domain", "media", "drift"}:
        return envelope(
            "authority.unknown",
            "input_error",
            error={"type": "MissingFamily", "message": "Choose links, domain, media, or drift."},
        ), EXIT_INPUT
    family = arguments.pop(0)
    parser = build_parser(family)
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        if exc.code == 0:
            raise
        return envelope(
            f"{family}.unknown",
            "input_error",
            error={"type": "ArgumentError", "message": "Invalid command arguments."},
        ), EXIT_INPUT
    handler_name = getattr(args, "handler", None)
    if not handler_name:
        return envelope(
            f"{family}.unknown",
            "input_error",
            error={"type": "MissingCommand", "message": f"Choose a {family} command."},
        ), EXIT_INPUT
    try:
        return HANDLERS[handler_name](args)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return envelope(
            f"{family}.{args.action}",
            "input_error",
            error={"type": type(exc).__name__, "message": str(exc)},
        ), EXIT_INPUT
    except Exception as exc:  # noqa: BLE001
        return envelope(
            f"{family}.{args.action}",
            "failed",
            error={"type": type(exc).__name__, "state": "FAILED", "message": str(exc)[:500]},
        ), EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    payload, code = run(list(argv or []))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code
