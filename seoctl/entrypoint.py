"""Top-level seoctl dispatcher for core and optional provider command families."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable

from runtime.assets import resolve_asset_root
from seoctl import (
    audit_cli,
    authority_cli,
    cli,
    content_cli,
    extensions_cli,
    google_cli,
    intelligence_cli,
    technical_cli,
)
from seoctl.parser_contract import CliArgumentError, non_exiting_parser_errors
from seoctl.registry import command_specs

cli.ROOT = resolve_asset_root(cli.ROOT)

HANDLERS = {
    **cli.HANDLERS,
    **content_cli.HANDLERS,
    **google_cli.HANDLERS,
    **technical_cli.HANDLERS,
    **authority_cli.HANDLERS,
    **extensions_cli.HANDLERS,
    **audit_cli.HANDLERS,
    **intelligence_cli.HANDLERS,
}

FamilyMain = Callable[[list[str] | None], int]

# Family-level routing only. Individual command definitions and ownership remain
# canonical in the command registry and their existing family parsers.
FAMILY_DISPATCH: dict[str, tuple[FamilyMain, bool]] = {
    "audit": (audit_cli.main, False),
    "bing": (extensions_cli.main, False),
    "content": (content_cli.main, True),
    "domain": (authority_cli.main, False),
    "drift": (authority_cli.main, False),
    "google": (google_cli.main, True),
    "indexnow": (extensions_cli.main, False),
    "integrations": (extensions_cli.main, False),
    "intelligence": (intelligence_cli.main, True),
    "knowledge": (audit_cli.main, False),
    "links": (authority_cli.main, False),
    "media": (authority_cli.main, False),
    "render": (technical_cli.main, False),
    "schema": (technical_cli.main, False),
    "technical": (technical_cli.main, False),
}


def _invalid_command_id(arguments: list[str]) -> str:
    path = tuple(arguments[:2])
    aliases = {("google", "gsc-inspect"): "google.url-inspection"}
    if path in aliases:
        return aliases[path]
    for spec in command_specs():
        if path == spec.path:
            return spec.id
    if arguments and any(spec.path[0] == arguments[0] for spec in command_specs()):
        return f"{arguments[0]}.unknown"
    return "seoctl.unknown"


def _emit_argument_error(arguments: list[str]) -> int:
    payload = cli.envelope(
        _invalid_command_id(arguments),
        "input_error",
        error={
            "code": "INVALID_ARGUMENTS",
            "type": "ArgumentError",
            "message": "Invalid command arguments.",
        },
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return cli.EXIT_INPUT


def _invoke(main: FamilyMain, routed: list[str], original: list[str]) -> int:
    try:
        with non_exiting_parser_errors():
            return main(routed)
    except CliArgumentError:
        return _emit_argument_error(original)


def build_root_help_parser() -> argparse.ArgumentParser:
    """Build discoverability-only root help from the canonical registry."""
    parser = argparse.ArgumentParser(
        prog="seoctl",
        description="World-Class SEO Agent System operator CLI",
    )
    parser.add_argument(
        "--registry-check",
        action="store_true",
        help="Validate commands and agent execution ownership, then exit.",
    )
    groups = parser.add_subparsers(dest="family", metavar="COMMAND")
    actions_by_family: dict[str, list[str]] = {}
    for spec in command_specs():
        actions_by_family.setdefault(spec.path[0], []).append(spec.path[1])
    for family, actions in sorted(actions_by_family.items()):
        groups.add_parser(
            family,
            help="Available commands: " + ", ".join(sorted(actions)),
            add_help=False,
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["-h"] or arguments == ["--help"]:
        build_root_help_parser().print_help()
        return 0
    families = {spec.path[0] for spec in command_specs()}
    if len(arguments) == 1 and arguments[0] in families:
        return _emit_argument_error(arguments)
    if arguments:
        dispatch = FAMILY_DISPATCH.get(arguments[0])
        if dispatch is not None:
            family_main, strip_family = dispatch
            routed = arguments[1:] if strip_family else arguments
            return _invoke(family_main, routed, arguments)
    return _invoke(cli.main, arguments, arguments)


if __name__ == "__main__":
    raise SystemExit(main())
