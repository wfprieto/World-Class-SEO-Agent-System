"""Operator commands for evidence-supplied AI, review, and reporting intelligence."""
from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from integrations.product_proof.intelligence import (
    AICitationOpportunityAnalyzer,
    AITimeoutAnalyzer,
    PerformanceNarrativeAnalyzer,
    ReviewComplianceAnalyzer,
)
from seoctl.cli import EXIT_FAILED, EXIT_INPUT, EXIT_OK, envelope


def _wrap(command: str, result):  # type: ignore[no-untyped-def]
    return envelope(command, result.status, result.data, warnings=result.warnings), EXIT_OK


def _timeouts(args: argparse.Namespace):
    return _wrap("intelligence.ai-timeouts", AITimeoutAnalyzer().analyze(log_path=args.log, server_stack=args.server_stack))


def _citations(args: argparse.Namespace):
    return _wrap("intelligence.ai-citations", AICitationOpportunityAnalyzer().analyze(observations_path=args.observations))


def _reviews(args: argparse.Namespace):
    return _wrap("intelligence.review-compliance", ReviewComplianceAnalyzer().analyze(input_path=args.input))


def _narrative(args: argparse.Namespace):
    return _wrap("intelligence.performance-narrative", PerformanceNarrativeAnalyzer().analyze(input_path=args.input))


HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "intelligence_ai_timeouts": _timeouts,
    "intelligence_ai_citations": _citations,
    "intelligence_review_compliance": _reviews,
    "intelligence_performance_narrative": _narrative,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seoctl intelligence", description="Evidence-supplied SEO intelligence analyzers")
    sub = parser.add_subparsers(dest="action")
    timeout = sub.add_parser("ai-timeouts", help="Analyze AI crawler 499 and response-time evidence from a server log")
    timeout.add_argument("--log", required=True)
    timeout.add_argument("--server-stack", required=True)
    timeout.set_defaults(handler="intelligence_ai_timeouts")
    citation = sub.add_parser("ai-citations", help="Analyze dated AI/AIO citation observations")
    citation.add_argument("--observations", required=True)
    citation.set_defaults(handler="intelligence_ai_citations")
    review = sub.add_parser("review-compliance", help="Screen operator-supplied review practices")
    review.add_argument("--input", required=True)
    review.set_defaults(handler="intelligence_review_compliance")
    narrative = sub.add_parser("performance-narrative", help="Build GOOD/BETTER/BEST performance language from a pre-agreed target")
    narrative.add_argument("--input", required=True)
    narrative.set_defaults(handler="intelligence_performance_narrative")
    return parser


def run(argv: list[str] | None = None):
    arguments = list(argv or [])
    if arguments and arguments[0] == "intelligence":
        arguments.pop(0)
    parser = build_parser()
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        if exc.code == 0:
            raise
        return envelope("intelligence.unknown", "input_error", error={"type": "ArgumentError", "message": "Invalid command arguments."}), EXIT_INPUT
    handler = getattr(args, "handler", None)
    if not handler:
        return envelope("intelligence.unknown", "input_error", error={"type": "MissingCommand", "message": "Choose an intelligence command."}), EXIT_INPUT
    try:
        return HANDLERS[handler](args)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return envelope(f"intelligence.{args.action}", "input_error", error={"type": type(exc).__name__, "message": str(exc)}), EXIT_INPUT
    except Exception as exc:  # noqa: BLE001
        return envelope(f"intelligence.{args.action}", "failed", error={"type": type(exc).__name__, "state": "FAILED", "message": str(exc)}), EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    payload, code = run(argv)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code
