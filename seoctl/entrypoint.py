"""Top-level seoctl dispatcher for core and optional provider command families."""

from __future__ import annotations

import sys

from seoctl import cli
from seoctl import google_cli

HANDLERS = {**cli.HANDLERS, **google_cli.HANDLERS}


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "google":
        return google_cli.main(arguments[1:])
    return cli.main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
