"""Top-level seoctl dispatcher for core and optional provider command families."""

from __future__ import annotations

import sys

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


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "content":
        return content_cli.main(arguments[1:])
    if arguments and arguments[0] == "google":
        return google_cli.main(arguments[1:])
    if arguments and arguments[0] in {"render", "technical", "schema"}:
        return technical_cli.main(arguments)
    if arguments and arguments[0] in {"links", "domain", "media", "drift"}:
        return authority_cli.main(arguments)
    if arguments and arguments[0] in {"integrations", "bing", "indexnow"}:
        return extensions_cli.main(arguments)
    if arguments and arguments[0] in {"audit", "knowledge"}:
        return audit_cli.main(arguments)
    if arguments and arguments[0] == "intelligence":
        return intelligence_cli.main(arguments)
    return cli.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
