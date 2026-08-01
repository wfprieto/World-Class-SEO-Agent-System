"""Top-level seoctl dispatcher for core and optional provider command families."""

from __future__ import annotations

import argparse
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
    if arguments:
        dispatch = FAMILY_DISPATCH.get(arguments[0])
        if dispatch is not None:
            family_main, strip_family = dispatch
            return family_main(arguments[1:] if strip_family else arguments)
    return cli.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
