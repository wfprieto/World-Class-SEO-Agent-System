"""Non-exiting argparse adapter for the JSON-first ``seoctl`` contract."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from typing import NoReturn


def _command_id(prog: str) -> str:
    parts = prog.split()
    if parts and parts[0] == "seoctl":
        parts = parts[1:]
    if len(parts) >= 2:
        return ".".join(parts[:2])
    if parts:
        return f"{parts[0]}.unknown"
    return "seoctl.unknown"


class CliArgumentError(Exception):
    """A parser rejection that retains command identity without writing or exiting."""

    def __init__(self, prog: str) -> None:
        super().__init__("Invalid command arguments.")
        self.command_id = _command_id(prog)
        self.error_code = "INVALID_ARGUMENTS"


class JsonArgumentParser(argparse.ArgumentParser):
    """Raise a typed error instead of leaking usage text or ``SystemExit``."""

    def error(self, message: str) -> NoReturn:
        del message
        raise CliArgumentError(self.prog)


@contextmanager
def non_exiting_parser_errors() -> Iterator[None]:
    """Install the adapter only while the single-threaded CLI parses arguments."""
    original = argparse.ArgumentParser.error
    setattr(argparse.ArgumentParser, "error", JsonArgumentParser.error)  # noqa: B010
    try:
        yield
    finally:
        setattr(argparse.ArgumentParser, "error", original)  # noqa: B010
