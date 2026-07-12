"""Rendering, technical inspection, and structured-data command families."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from adapters.base import AdapterNotConfigured
from integrations.technical.browser import RenderedPageService
from integrations.technical.inspection import TechnicalInspectionService
from seoctl.cli import EXIT_FAILED, EXIT_INPUT, EXIT_OK, EXIT_UNAVAILABLE, envelope


def _browser() -> RenderedPageService:
    return RenderedPageService()


def _technical() -> TechnicalInspectionService:
    return TechnicalInspectionService()


def _result(command: str, result):  # type: ignore[no-untyped-def]
    code = EXIT_OK
    if result.status in {"not_configured", "unavailable"}:
        code = EXIT_UNAVAILABLE
    elif result.status in {"failed", "invalid_response"}:
        code = EXIT_FAILED
    return envelope(command, result.status, result.data, warnings=result.warnings), code


def _render_health(args: argparse.Namespace):
    health = _browser().health()
    status = "ok" if health.state == "AVAILABLE" else "not_configured"
    code = EXIT_OK if health.state == "AVAILABLE" else EXIT_UNAVAILABLE
    return envelope("render.health", status, asdict(health)), code


def _render_page(args: argparse.Namespace):
    result = _browser().render(
        args.url,
        wait_until=args.wait_until,
        timeout_ms=args.timeout_ms,
        width=args.width,
        height=args.height,
        block_resource_types=tuple(args.block_resource_type),
    )
    return _result("render.page", result)


def _render_screenshot(args: argparse.Namespace):
    result = _browser().screenshot(
        args.url,
        output=args.output,
        full_page=args.full_page,
        wait_until=args.wait_until,
        timeout_ms=args.timeout_ms,
        width=args.width,
        height=args.height,
        block_resource_types=tuple(args.block_resource_type),
    )
    return _result("render.screenshot", result)


def _robots(args: argparse.Namespace):
    return _result("technical.robots", _technical().robots(args.url))


def _sitemap(args: argparse.Namespace):
    return _result("technical.sitemap", _technical().sitemap(args.url))


def _hreflang(args: argparse.Namespace):
    return _result("technical.hreflang", _technical().hreflang(args.url))


def _preload(args: argparse.Namespace):
    return _result("technical.preload", _technical().preload(args.url))


def _redirect_chain(args: argparse.Namespace):
    return _result(
        "technical.redirect-chain",
        _technical().redirect_chain(args.url, max_redirects=args.max_redirects),
    )


def _indexability(args: argparse.Namespace):
    return _result("technical.indexability", _technical().indexability(args.url))


def _cwv(args: argparse.Namespace):
    return _result(
        "technical.cwv",
        _technical().cwv(
            url=args.url,
            fixture_path=args.fixture,
            strategy=args.strategy,
        ),
    )


def _schema_detect(args: argparse.Namespace):
    html = Path(args.html_file).read_text(encoding="utf-8-sig") if args.html_file else None
    return _result(
        "schema.detect",
        _technical().schema_detect(
            url=args.url,
            html=html,
            source=args.html_file,
        ),
    )


def _schema_validate(args: argparse.Namespace):
    raw = Path(args.file).read_text(encoding="utf-8-sig") if args.file else args.json
    return _result("schema.validate", _technical().schema_validate(jsonld=raw))


def _parse_values(values: list[str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            raise ValueError("--value entries must use key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key or key.startswith("@"):
            raise ValueError("--value keys must be non-empty schema property names")
        if key in output:
            raise ValueError(f"duplicate --value key: {key}")
        text = value.strip()
        if text.startswith(("[", "{")):
            output[key] = json.loads(text)
        else:
            output[key] = text
    return output


def _schema_generate(args: argparse.Namespace):
    return _result(
        "schema.generate",
        _technical().schema_generate(
            schema_type=args.schema_type,
            values=_parse_values(args.value),
        ),
    )


HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "render_health": _render_health,
    "render_page": _render_page,
    "render_screenshot": _render_screenshot,
    "technical_robots": _robots,
    "technical_sitemap": _sitemap,
    "technical_hreflang": _hreflang,
    "technical_preload": _preload,
    "technical_redirect_chain": _redirect_chain,
    "technical_indexability": _indexability,
    "technical_cwv": _cwv,
    "schema_detect": _schema_detect,
    "schema_validate": _schema_validate,
    "schema_generate": _schema_generate,
}


def _render_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--wait-until",
        choices=["commit", "domcontentloaded", "load", "networkidle"],
        default="networkidle",
    )
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--block-resource-type", action="append", default=[])


def build_parser(family: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"seoctl {family}",
        description="Bounded rendering and technical SEO execution",
    )
    sub = parser.add_subparsers(dest="action")
    if family == "render":
        health = sub.add_parser("health", help="Check Playwright and Chromium availability")
        health.set_defaults(handler="render_health")
        page = sub.add_parser("page", help="Render a public page with optional Playwright Chromium")
        _render_options(page)
        page.set_defaults(handler="render_page")
        screenshot = sub.add_parser("screenshot", help="Capture a bounded PNG screenshot")
        _render_options(screenshot)
        screenshot.add_argument("--output", required=True)
        screenshot.add_argument("--full-page", action="store_true")
        screenshot.set_defaults(handler="render_screenshot")
    elif family == "technical":
        for name, help_text, handler in (
            ("robots", "Fetch and parse robots.txt", "technical_robots"),
            ("sitemap", "Fetch and validate an XML sitemap", "technical_sitemap"),
            ("hreflang", "Inspect HTML hreflang alternates", "technical_hreflang"),
            ("preload", "Inspect preload and fetchpriority markup", "technical_preload"),
            ("indexability", "Assess technical indexability evidence", "technical_indexability"),
        ):
            command = sub.add_parser(name, help=help_text)
            command.add_argument("--url", required=True)
            command.set_defaults(handler=handler)
        redirects = sub.add_parser("redirect-chain", help="Follow a bounded, SSRF-safe redirect chain")
        redirects.add_argument("--url", required=True)
        redirects.add_argument("--max-redirects", type=int, default=10)
        redirects.set_defaults(handler="technical_redirect_chain")
        cwv = sub.add_parser("cwv", help="Normalize PageSpeed/CrUX or an offline fixture")
        target = cwv.add_mutually_exclusive_group(required=True)
        target.add_argument("--url")
        target.add_argument("--fixture")
        cwv.add_argument("--strategy", choices=["mobile", "desktop"], default="mobile")
        cwv.set_defaults(handler="technical_cwv")
    elif family == "schema":
        detect = sub.add_parser("detect", help="Detect JSON-LD from a URL or HTML file")
        target = detect.add_mutually_exclusive_group(required=True)
        target.add_argument("--url")
        target.add_argument("--html-file")
        detect.set_defaults(handler="schema_detect")
        validate = sub.add_parser("validate", help="Validate JSON syntax and schema.org baseline fields")
        target = validate.add_mutually_exclusive_group(required=True)
        target.add_argument("--json")
        target.add_argument("--file")
        validate.set_defaults(handler="schema_validate")
        generate = sub.add_parser("generate", help="Generate bounded JSON-LD from operator-supplied facts")
        generate.add_argument("--type", dest="schema_type", required=True)
        generate.add_argument("--value", action="append", default=[])
        generate.set_defaults(handler="schema_generate")
    else:
        raise ValueError("family must be render, technical, or schema")
    return parser


def run(argv: list[str] | None = None):
    arguments = list(argv or [])
    if not arguments or arguments[0] not in {"render", "technical", "schema"}:
        return envelope(
            "technical.unknown",
            "input_error",
            error={"type": "MissingFamily", "message": "Choose render, technical, or schema."},
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
    except AdapterNotConfigured as exc:
        return envelope(
            f"{family}.{args.action}",
            "not_configured",
            error={"type": type(exc).__name__, "state": "NOT_CONFIGURED", "message": str(exc)},
        ), EXIT_UNAVAILABLE
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
            error={"type": type(exc).__name__, "state": "FAILED", "message": str(exc)},
        ), EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    payload, code = run(argv)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code
