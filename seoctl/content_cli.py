"""Content command family with legacy delegation and deterministic intelligence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from integrations.content_intelligence.service import ContentIntelligenceService
from seoctl import cli as core_cli
from seoctl.cli import (
    EXIT_BLOCKED,
    EXIT_FAILED,
    EXIT_INPUT,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    envelope,
)

_LEGACY_ACTIONS = {"relevance", "serp", "brief-decision"}


def _service() -> ContentIntelligenceService:
    return ContentIntelligenceService()


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _result(command: str, result):  # type: ignore[no-untyped-def]
    if result.status in {"blocked"}:
        code = EXIT_BLOCKED
    elif result.status in {"not_configured", "unavailable"}:
        code = EXIT_UNAVAILABLE
    elif result.status in {"failed", "invalid", "invalid_response"}:
        code = EXIT_FAILED
    else:
        code = EXIT_OK
    return envelope(
        command,
        result.status,
        result.data,
        warnings=result.warnings,
    ), code


def _quality(args: argparse.Namespace):
    sources = _read_json(args.sources) if args.sources else []
    result = _service().quality(
        text=_read_text(args.input),
        title=args.title,
        audience=args.audience,
        purpose=args.purpose,
        author=args.author,
        reviewed_by=args.reviewed_by,
        sources=sources,
        risk_class=args.risk_class,
    )
    return _result("content.quality", result)


def _verify(args: argparse.Namespace):
    result = _service().verify(
        claims=_read_json(args.claims),
        sources=_read_json(args.sources),
    )
    return _result("content.verify", result)


def _entities(args: argparse.Namespace):
    catalog = _read_json(args.catalog) if args.catalog else []
    result = _service().entities(
        text=_read_text(args.input),
        catalog=catalog,
    )
    return _result("content.entities", result)


def _brief(args: argparse.Namespace):
    result = _service().brief(
        relevance=_read_json(args.relevance),
        serp=_read_json(args.serp),
        information_gains=_read_json(args.information_gain),
        sources=_read_json(args.sources),
        audience=args.audience,
        intent=args.intent,
        primary_question=args.primary_question,
        required_sections=args.section,
        conditions_resolved=args.conditions_resolved,
    )
    return _result("content.brief", result)


def _decay(args: argparse.Namespace):
    result = _service().decay(
        current=_read_json(args.current),
        prior=_read_json(args.prior),
        decline_threshold=args.decline_threshold,
    )
    return _result("content.decay", result)


def _compare(args: argparse.Namespace):
    result = _service().compare(
        left_text=_read_text(args.left),
        right_text=_read_text(args.right),
        left_label=args.left_label,
        right_label=args.right_label,
    )
    return _result("content.compare", result)


def _humanize(args: argparse.Namespace):
    result = _service().humanize(text=_read_text(args.input))
    payload = dict(result.data)
    if args.output:
        path = Path(args.output).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(payload["transformed_text"], encoding="utf-8")
        temporary.replace(path)
        payload["output_path"] = str(path)
    wrapped = type(result)(
        source=result.source,
        status=result.status,
        data=payload,
        warnings=result.warnings,
    )
    return _result("content.humanize", wrapped)


HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "content_quality": _quality,
    "content_verify": _verify,
    "content_entities": _entities,
    "content_brief": _brief,
    "content_decay": _decay,
    "content_compare": _compare,
    "content_humanize": _humanize,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="seoctl content",
        description="Content evidence, diagnostics, comparison, and clarity tools",
    )
    sub = parser.add_subparsers(dest="action")

    # Existing commands remain canonical in seoctl.cli. They are declared here
    # only so one combined help surface remains available.
    sub.add_parser("relevance", help="Run the canonical content relevance gate")
    sub.add_parser("serp", help="Run the canonical SERP evidence analyzer")
    sub.add_parser(
        "brief-decision",
        help="Run the canonical relevance and SERP brief decision gate",
    )

    quality = sub.add_parser(
        "quality",
        help="Score measurable editorial signals without claiming ranking quality",
    )
    quality.add_argument("--input", required=True)
    quality.add_argument("--title")
    quality.add_argument("--audience")
    quality.add_argument("--purpose")
    quality.add_argument("--author")
    quality.add_argument("--reviewed-by")
    quality.add_argument("--sources")
    quality.add_argument(
        "--risk-class",
        default="general",
        choices=["general", "ymyl", "medical", "legal", "financial", "safety"],
    )
    quality.set_defaults(handler="content_quality")

    verify = sub.add_parser(
        "verify",
        help="Validate supplied claim-to-source review records",
    )
    verify.add_argument("--claims", required=True)
    verify.add_argument("--sources", required=True)
    verify.set_defaults(handler="content_verify")

    entities = sub.add_parser(
        "entities",
        help="Match supplied entity catalogs and report low-confidence candidates",
    )
    entities.add_argument("--input", required=True)
    entities.add_argument("--catalog")
    entities.set_defaults(handler="content_entities")

    brief = sub.add_parser(
        "brief",
        help="Build an evidence-gated content brief from canonical decisions",
    )
    brief.add_argument("--relevance", required=True)
    brief.add_argument("--serp", required=True)
    brief.add_argument("--information-gain", required=True)
    brief.add_argument("--sources", required=True)
    brief.add_argument("--audience", required=True)
    brief.add_argument("--intent", required=True)
    brief.add_argument("--primary-question", required=True)
    brief.add_argument("--section", action="append", default=[])
    brief.add_argument("--conditions-resolved", action="store_true")
    brief.set_defaults(handler="content_brief")

    decay = sub.add_parser(
        "decay",
        help="Compare two metric periods without assigning an unsupported cause",
    )
    decay.add_argument("--current", required=True)
    decay.add_argument("--prior", required=True)
    decay.add_argument("--decline-threshold", type=float, default=0.2)
    decay.set_defaults(handler="content_decay")

    compare = sub.add_parser(
        "compare",
        help="Compare measurable content structure and vocabulary",
    )
    compare.add_argument("--left", required=True)
    compare.add_argument("--right", required=True)
    compare.add_argument("--left-label", default="left")
    compare.add_argument("--right-label", default="right")
    compare.set_defaults(handler="content_compare")

    humanize = sub.add_parser(
        "humanize",
        help="Apply clarity-only transformations without detector evasion",
    )
    humanize.add_argument("--input", required=True)
    humanize.add_argument("--output")
    humanize.set_defaults(handler="content_humanize")
    return parser


def run(argv: list[str] | None = None):
    arguments = list(argv or [])
    if arguments and arguments[0] == "content":
        arguments.pop(0)
    if arguments and arguments[0] in _LEGACY_ACTIONS:
        return core_cli.run(["content", *arguments])
    parser = build_parser()
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        if exc.code == 0:
            raise
        return envelope(
            "content.unknown",
            "input_error",
            error={"type": "ArgumentError", "message": "Invalid command arguments."},
        ), EXIT_INPUT
    handler_name = getattr(args, "handler", None)
    if not handler_name:
        return envelope(
            "content.unknown",
            "input_error",
            error={"type": "MissingCommand", "message": "Choose a content command."},
        ), EXIT_INPUT
    try:
        return HANDLERS[handler_name](args)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return envelope(
            f"content.{args.action}",
            "input_error",
            error={"type": type(exc).__name__, "message": str(exc)},
        ), EXIT_INPUT
    except Exception as exc:  # noqa: BLE001
        return envelope(
            f"content.{args.action}",
            "failed",
            error={"type": type(exc).__name__, "state": "FAILED", "message": str(exc)},
        ), EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    payload, code = run(argv)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code
