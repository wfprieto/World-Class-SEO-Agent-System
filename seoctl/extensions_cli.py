"""Optional provider, Bing preflight, and IndexNow command families."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from adapters.base import AdapterNotConfigured
from integrations.extensions.indexnow import IndexNowService
from integrations.extensions.providers import ProviderService
from seoctl.cli import (
    EXIT_BLOCKED,
    EXIT_FAILED,
    EXIT_INPUT,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    envelope,
)


def _providers() -> ProviderService:
    return ProviderService()


def _indexnow() -> IndexNowService:
    return IndexNowService()


def _result(command: str, result):  # type: ignore[no-untyped-def]
    code = EXIT_OK
    if result.status in {"not_configured", "unavailable"}:
        code = EXIT_UNAVAILABLE
    elif result.status == "blocked":
        code = EXIT_BLOCKED
    elif result.status in {
        "failed", "invalid_response", "unauthorized", "rate_limited"
    }:
        code = EXIT_FAILED
    return envelope(command, result.status, result.data, warnings=result.warnings), code


def _read_urls(path: str) -> list[str]:
    target = Path(path)
    if target.stat().st_size > 5_000_000:
        raise ValueError("URL input exceeds 5000000 bytes")
    text = target.read_text(encoding="utf-8-sig")
    if target.suffix.lower() == ".json":
        payload = json.loads(text)
        if not isinstance(payload, list) or not all(isinstance(row, str) for row in payload):
            raise ValueError("JSON URL input must be an array of strings")
        return payload
    return [
        row.strip() for row in text.splitlines()
        if row.strip() and not row.lstrip().startswith("#")
    ]


def _integrations_list(args: argparse.Namespace):
    return _result("integrations.list", _providers().list())


def _integrations_preflight(args: argparse.Namespace):
    return _result(
        "integrations.preflight",
        _providers().preflight(provider=args.provider),
    )


def _integrations_config(args: argparse.Namespace):
    return _result(
        "integrations.config",
        _providers().config(provider=args.provider, client=args.client),
    )


def _integrations_estimate(args: argparse.Namespace):
    return _result(
        "integrations.estimate",
        _providers().estimate(
            provider=args.provider,
            units=args.units,
            unit_cost=args.unit_cost,
            approved_ceiling=args.ceiling,
            approved=args.approve,
        ),
    )


def _bing_preflight(args: argparse.Namespace):
    return _result(
        "bing.preflight",
        _providers().preflight(provider="bing-webmaster"),
    )


def _indexnow_validate(args: argparse.Namespace):
    return _result(
        "indexnow.validate",
        _indexnow().validate(
            urls=_read_urls(args.urls),
            key_location=args.key_location,
        ),
    )


def _indexnow_submit(args: argparse.Namespace):
    return _result(
        "indexnow.submit",
        _indexnow().submit(
            urls=_read_urls(args.urls),
            key_location=args.key_location,
            execute=args.execute,
            confirmation=args.confirm,
            endpoint=args.endpoint,
        ),
    )


HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "integrations_list": _integrations_list,
    "integrations_preflight": _integrations_preflight,
    "integrations_config": _integrations_config,
    "integrations_estimate": _integrations_estimate,
    "bing_preflight": _bing_preflight,
    "indexnow_validate": _indexnow_validate,
    "indexnow_submit": _indexnow_submit,
}


def build_parser(family: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"seoctl {family}",
        description="Governed optional integrations and IndexNow execution",
    )
    sub = parser.add_subparsers(dest="action")
    if family == "integrations":
        command = sub.add_parser("list", help="List optional providers without contacting them")
        command.set_defaults(handler="integrations_list")

        command = sub.add_parser("preflight", help="Check configuration and governance state")
        command.add_argument("--provider", required=True)
        command.set_defaults(handler="integrations_preflight")

        command = sub.add_parser("config", help="Render a credential-free client template")
        command.add_argument("--provider", required=True)
        command.add_argument("--client", choices=["generic", "codex", "claude"], default="generic")
        command.set_defaults(handler="integrations_config")

        command = sub.add_parser("estimate", help="Apply the metered-provider cost gate")
        command.add_argument("--provider", required=True)
        command.add_argument("--units", type=int, required=True)
        command.add_argument("--unit-cost", type=float)
        command.add_argument("--ceiling", type=float)
        command.add_argument("--approve", action="store_true")
        command.set_defaults(handler="integrations_estimate")
    elif family == "bing":
        command = sub.add_parser(
            "preflight",
            help="Report Bing Webmaster configuration and contract-verification state",
        )
        command.set_defaults(handler="bing_preflight")
    elif family == "indexnow":
        for name, help_text, handler in (
            ("validate", "Validate an IndexNow URL set without sending it", "indexnow_validate"),
            ("submit", "Submit only after separate write confirmation", "indexnow_submit"),
        ):
            command = sub.add_parser(name, help=help_text)
            command.add_argument("--urls", required=True)
            command.add_argument("--key-location")
            command.set_defaults(handler=handler)
            if name == "submit":
                command.add_argument(
                    "--endpoint",
                    default="https://api.indexnow.org/indexnow",
                )
                command.add_argument("--execute", action="store_true")
                command.add_argument("--confirm", default="")
    else:
        raise ValueError("family must be integrations, bing, or indexnow")
    return parser


def run(argv: list[str] | None = None):
    arguments = list(argv or [])
    if not arguments or arguments[0] not in {"integrations", "bing", "indexnow"}:
        return envelope(
            "integrations.unknown",
            "input_error",
            error={"type": "MissingFamily", "message": "Choose integrations, bing, or indexnow."},
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
            error={"type": type(exc).__name__, "state": "FAILED", "message": str(exc)[:500]},
        ), EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    payload, code = run(argv)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code
