"""Inert captured command grammar; never an execution or permission boundary."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn


@dataclass(frozen=True)
class _Option:
    kind: str = "value"
    required: bool = False
    repeat: bool = False
    choices: frozenset[str] = frozenset()
    bounds: tuple[int, int | None] | None = None


def _choices(*values: str, repeat: bool = False, required: bool = False) -> _Option:
    return _Option(choices=frozenset(values), repeat=repeat, required=required)


_GSC = {
    "--site-url": _Option(required=True), "--start-date": _Option("date"), "--end-date": _Option("date"),
    "--search-type": _choices("web", "image", "video", "news", "discover", "googleNews"),
    "--aggregation-type": _choices("auto", "byPage", "byProperty"),
    "--data-state": _choices("final", "all", "hourly_all"),
}
_RENDER = {
    "--url": _Option(required=True), "--wait-until": _choices("commit", "domcontentloaded", "load", "networkidle"),
    "--timeout-ms": _Option("integer", bounds=(1000, 120000)),
    "--width": _Option("integer", bounds=(320, 7680)), "--height": _Option("integer", bounds=(200, 4320)),
    "--block-resource-type": _choices("document", "stylesheet", "image", "media", "font", "script",
        "texttrack", "xhr", "fetch", "eventsource", "manifest", "other", repeat=True),
}
_URLS = {"--urls": _Option(required=True), "--key-location": _Option()}
_SPECS: dict[str, dict[str, _Option]] = {
    "google.gsc-query": {**_GSC, "--dimension": _choices("country", "device", "date", "hour", "page", "query",
        "searchAppearance", repeat=True), "--row-limit": _Option("integer", bounds=(1, 25000)),
        "--max-pages": _Option("integer", bounds=(1, 100))},
    "google.gsc-aggregate": dict(_GSC),
    "google.ga4-report": {"--property-id": _Option(required=True), "--start-date": _Option("date"),
        "--end-date": _Option("date"), "--dimension": _Option("name", repeat=True),
        "--metric": _Option("name", repeat=True), "--limit": _Option("integer", bounds=(1, 250000)),
        "--offset": _Option("integer", bounds=(0, None)), "--currency-code": _Option("currency")},
    "render.page": dict(_RENDER),
    "render.screenshot": {**_RENDER, "--output": _Option(required=True), "--full-page": _Option("flag")},
    "render.health": {}, "bing.preflight": {}, "browser.install": {},
    "links.commoncrawl": {"--domain": _Option(required=True), "--index": _Option(),
        "--max-pages": _Option("integer", bounds=(1, 5)), "--page-size": _Option("integer", bounds=(1, 1000))},
    "domain.history": {"--domain": _Option(required=True)},
    "media.youtube-search": {"--query": _Option(required=True),
        "--max-results": _Option("integer", bounds=(1, 50)), "--pages": _Option("integer", bounds=(1, 3)),
        "--region-code": _Option(), "--relevance-language": _Option(),
        "--order": _choices("date", "rating", "relevance", "title", "videoCount", "viewCount"),
        "--safe-search": _choices("moderate", "none", "strict")},
    "indexnow.validate": dict(_URLS),
    "indexnow.submit": {**_URLS, "--endpoint": _Option(), "--execute": _Option("flag", required=True),
        "--confirm": _choices("INDEXNOW_SUBMIT", required=True)},
}
_PYTHON = re.compile(r"python(?:3(?:\.(?:11|12|13))?)?(?:\.exe)?")


def _require(condition: bool, message: str = "Captured arguments contradict source command grammar") -> None:
    if not condition:
        raise ValueError(message)


def _python(executable: str) -> None:
    _require(not any(ord(character) < 32 or ord(character) == 127 or character in "\"'" for character in executable))
    if re.match(r"^[A-Za-z]:[/\\]", executable):
        parts = executable[3:].replace("\\", "/").split("/")
        _require(all(part and not part.endswith((" ", ".")) for part in parts))
        _require(not any(character in '<>:"|?*' for character in executable[2:]))
        name = parts[-1].lower()
    elif executable.startswith("/"):
        parts = executable[1:].split("/")
        _require("\\" not in executable and all(parts))
        name = parts[-1]
    else:
        _require("/" not in executable and "\\" not in executable)
        parts, name = [executable], executable.lower()
    _require(not any(part in {".", ".."} for part in parts))
    _require(_PYTHON.fullmatch(name) is not None, "Only a direct supported Python executable may be captured")


def _argv(command: str, value: object) -> list[str]:
    _require(isinstance(command, str) and command in _SPECS, "Unknown captured command")
    _require(isinstance(value, list) and bool(value))
    assert isinstance(value, list)
    _require(all(isinstance(item, str) and "\x00" not in item for item in value))
    argv: list[str] = list(value)
    _python(argv[0])
    expected = (["-m", "playwright", "install", "chromium"] if command == "browser.install"
                else ["-m", "seoctl", *command.split(".")])
    _require(argv[1:1 + len(expected)] == expected, "Captured module/command path does not match")
    return argv[1 + len(expected):]


def _validate(rule: _Option, text: str) -> None:
    _require(not rule.required or bool(text.strip()), "Required option value cannot be empty")
    _require(not rule.choices or text in rule.choices)
    if rule.kind == "integer":
        number = int(text)
        assert rule.bounds is not None
        low, high = rule.bounds
        _require(number >= low and (high is None or number <= high))
    elif rule.kind == "date" and text:
        datetime.strptime(text, "%Y-%m-%d")  # Same pure source selector, not a verification clock.
    elif rule.kind == "name":
        _require(re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", text) is not None)
    elif rule.kind == "currency":
        _require(re.fullmatch(r"[A-Z]{3}", text) is not None)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ValueError("Captured arguments are not an unambiguous source command")


class _Capture(argparse.Action):
    def __init__(self, option_strings: list[str], dest: str, rule: _Option) -> None:
        super().__init__(option_strings, dest, nargs=0 if rule.kind == "flag" else None,
                         default=argparse.SUPPRESS, required=rule.required)
        self.rule = rule

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace,
                 values: object, option_string: str | None = None) -> None:
        _require(self.rule.repeat or not hasattr(namespace, self.dest), "Duplicate singleton captured option")
        captures: list[str] = getattr(namespace, self.dest, [])
        if self.rule.kind != "flag":
            _require(isinstance(values, str))
            assert isinstance(values, str)
            _validate(self.rule, values)
            captures = [*captures, values]
        setattr(namespace, self.dest, captures)


def _parse(argv: list[str], spec: dict[str, _Option]) -> dict[str, list[str]]:
    parser = _Parser(add_help=False, allow_abbrev=False)
    for name, rule in spec.items():
        parser.add_argument(name, dest=name, action=_Capture, rule=rule)
    # Recognize source help tokenization, but never print/exit or count it as execution.
    parser.add_argument("-h", "--help", dest="_forbidden_help", action="store_true", default=argparse.SUPPRESS)
    namespace = parser.parse_args(argv)
    _require(not getattr(namespace, "_forbidden_help", False), "Help is not a capability execution")
    options: dict[str, list[str]] = vars(namespace)
    return options


def _relations(command: str, options: dict[str, list[str]]) -> None:
    for name in ("--dimension", "--metric"):
        values = options.get(name, [])
        _require(len(values) == len(set(values)), "Source dimensions and metrics must be unique")
    start, end = options.get("--start-date", [""])[0], options.get("--end-date", [""])[0]
    if start and end:
        _require(datetime.strptime(start, "%Y-%m-%d") <= datetime.strptime(end, "%Y-%m-%d"))
    if command == "google.gsc-query" and options.get("--aggregation-type") == ["byProperty"]:
        _require("page" not in options.get("--dimension", []))
    if command == "media.youtube-search":
        _require(len(options["--query"][0]) <= 500)


def command_options(command: str, value: object) -> dict[str, list[str]]:
    """Return explicit source options only; no defaults, execution, file opens or version proof."""
    try:
        argv = _argv(command, value)
        options = _parse(argv, _SPECS[command])
        _relations(command, options)
        return options
    except ValueError:
        raise ValueError("Captured arguments are not a valid explicit source capability command") from None
