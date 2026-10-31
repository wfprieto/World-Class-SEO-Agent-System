"""Synthetic captured argv only; no handlers, file opens or actual commands."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from scripts.publication_arguments import _SPECS, command_options

MINIMUM = {
    "google.gsc-query": ["--site-url", "sc-domain:example.com"],
    "google.gsc-aggregate": ["--site-url", "sc-domain:example.com"],
    "google.ga4-report": ["--property-id", "properties/123"],
    "render.page": ["--url", "https://example.com/"],
    "render.screenshot": ["--url", "https://example.com/", "--output", "/synthetic/capture.png"],
    "render.health": [], "bing.preflight": [], "browser.install": [],
    "links.commoncrawl": ["--domain", "example.com"], "domain.history": ["--domain", "example.com"],
    "media.youtube-search": ["--query", "SYNTHETIC query"],
    "indexnow.validate": ["--urls", "/synthetic/input.json"],
    "indexnow.submit": ["--urls", "/synthetic/input.json", "--execute", "--confirm", "INDEXNOW_SUBMIT"],
}
FULL = {
    "google.gsc-query": ["--start-date", "2026-10-01", "--end-date=2026-10-02", "--dimension", "query",
        "--dimension=device", "--row-limit", "+1000", "--max-pages", "2", "--search-type", "web",
        "--aggregation-type", "auto", "--data-state", "all"],
    "google.gsc-aggregate": ["--start-date=2026-1-1", "--end-date", "2026-10-02", "--search-type", "discover",
        "--aggregation-type", "byPage", "--data-state", "final"],
    "google.ga4-report": ["--start-date", "2026-10-01", "--end-date", "2026-10-02", "--dimension", "date",
        "--dimension", "country", "--metric", "sessions", "--metric", "activeUsers", "--limit", "1000",
        "--offset", "10", "--currency-code", "USD"],
    "render.page": ["--wait-until", "domcontentloaded", "--timeout-ms", "1000", "--width", "320",
        "--height", "200", "--block-resource-type", "image", "--block-resource-type", "image"],
    "render.screenshot": ["--wait-until", "load", "--timeout-ms", "120000", "--width", "7680", "--height",
        "4320", "--block-resource-type", "font", "--block-resource-type", "media", "--full-page"],
    "render.health": [], "bing.preflight": [], "browser.install": [],
    "links.commoncrawl": ["--index", "CC-MAIN-SYNTHETIC", "--max-pages", "5", "--page-size", "1000"],
    "domain.history": [], "media.youtube-search": ["--max-results", "50", "--pages", "3", "--region-code", "US",
        "--relevance-language", "en", "--order", "date", "--safe-search", "strict"],
    "indexnow.validate": ["--key-location", "https://example.com/synthetic-key.txt"],
    "indexnow.submit": ["--key-location", "https://example.com/synthetic-key.txt", "--endpoint", "https://api.indexnow.org/indexnow"],
}


def valid_argv(command: str) -> list[str]:
    """Clearly SYNTHETIC captured argv; no command is run and no path needs to exist."""
    if command not in MINIMUM:
        raise ValueError("Unknown synthetic captured command")
    path = ["-m", "playwright", "install", "chromium"] if command == "browser.install" else ["-m", "seoctl", *command.split(".")]
    return ["/synthetic/venv/bin/python3.13", *path, *MINIMUM[command]]


def _source_parser(command: str) -> argparse.ArgumentParser:
    """Only build/parse canonical argument definitions; never call their handlers."""
    family = command.split(".")[0]
    if family == "google":
        from seoctl.google_cli import build_parser

        return build_parser()
    if family == "render":
        from seoctl.technical_cli import build_parser as technical

        return technical(family)
    if family in {"links", "domain", "media"}:
        from seoctl.authority_cli import build_parser as authority

        return authority(family)
    from seoctl.extensions_cli import build_parser as extensions

    return extensions(family)


@pytest.mark.parametrize("command", MINIMUM)
def test_minimal_synthetic_capture_and_no_default_options(command: str) -> None:
    argv = valid_argv(command)
    before = list(argv)
    options = command_options(command, argv)
    assert argv == before
    assert all(name.startswith("--") and isinstance(values, list) for name, values in options.items())
    if command in {"browser.install", "render.health", "bing.preflight"}:
        assert options == {}
    if command == "indexnow.submit":
        assert options["--execute"] == []
        assert options["--confirm"] == ["INDEXNOW_SUBMIT"]


@pytest.mark.parametrize("command", MINIMUM)
def test_complete_options_are_accepted_by_actual_source_parser_without_execution(command: str) -> None:
    argv = [*valid_argv(command), *FULL[command]]
    options = command_options(command, argv)
    if command == "browser.install":
        assert options == {}
        return
    parsed = _source_parser(command).parse_args(argv[4:])
    assert parsed.handler == command.replace(".", "_").replace("-", "_")
    for name, values in options.items():
        actual = getattr(parsed, name[2:].replace("-", "_"))
        if not values:
            assert actual is True
        elif isinstance(actual, list):
            assert actual == values
        else:
            assert str(actual) == values[0].lstrip("+")


@pytest.mark.parametrize("command", [item for item in MINIMUM if item != "browser.install"])
def test_complete_option_inventory_and_cardinality_match_source_definitions(command: str) -> None:
    parser = _source_parser(command)
    group = next(item for item in parser._actions if isinstance(item, argparse._SubParsersAction))
    leaf = group.choices[command.split(".")[1]]
    actions = {name: item for item in leaf._actions for name in item.option_strings
               if name.startswith("--") and name not in {"--help", "--fixture"}}
    assert set(actions) == set(_SPECS[command])
    for name, rule in _SPECS[command].items():
        action = actions[name]
        assert rule.repeat == isinstance(action, argparse._AppendAction)
        assert (rule.kind == "flag") == (action.nargs == 0)
        assert rule.required == (action.required or name in {"--execute", "--confirm"})
        if action.choices:
            assert rule.choices == frozenset(action.choices)


def test_shell_wrapper_cannot_masquerade_as_actual_source_command() -> None:
    with pytest.raises(ValueError):
        command_options("google.gsc-query", ["sh", "-c", "python -m seoctl google gsc-query --site-url sc-domain:example.com"])


@pytest.mark.parametrize("command", MINIMUM)
@pytest.mark.parametrize("extra", [["--fixture", "/synthetic/no.json"], ["--as-of", "2099-01-01"],
    ["--help"], ["--verification-clock", "2099-01-01"], ["--unknown"], ["extra-command"], ["--"], [";", "echo"]])
def test_unknown_fixture_clock_help_and_extra_positionals_fail(command: str, extra: list[str]) -> None:
    with pytest.raises(ValueError):
        command_options(command, [*valid_argv(command), *extra])


@pytest.mark.parametrize("command", [item for item in MINIMUM if MINIMUM[item]])
def test_duplicate_required_singleton_including_equals_form_fails(command: str) -> None:
    argv = valid_argv(command)
    name, value = MINIMUM[command][:2]
    for duplicate in ([name, value], [name + "=" + value]):
        with pytest.raises(ValueError):
            command_options(command, [*argv, *duplicate])


@pytest.mark.parametrize("command", [item for item in MINIMUM if MINIMUM[item]])
def test_missing_and_empty_required_target_fails(command: str) -> None:
    argv = valid_argv(command)
    for broken in (argv[:5] + argv[7:], argv[:6] + [""] + argv[7:]):
        with pytest.raises(ValueError):
            command_options(command, broken)


@pytest.mark.parametrize("executable", ["python", "python.exe", "python3", "python3.11", "python3.12", "python3.13",
    "/usr/bin/python3.11", "/opt/hostedtoolcache/Python/3.13.4/x64/bin/python", "C:/Python313/python.exe",
    r"C:\Program Files\Python312\python.exe", r"D:\outside-source-venv\Scripts\PYTHON.EXE"])
def test_supported_direct_python_names_and_canonical_absolute_paths(executable: str) -> None:
    assert command_options("render.health", [executable, *valid_argv("render.health")[1:]]) == {}


@pytest.mark.parametrize("executable", ["", "py", "py.exe", "env", "bash", "cmd.exe", "powershell", "pypy3", "python2",
    "python3.10", "python3.14", "python3.131", "pythonw.exe", "python -m seoctl", '"python"', "'python'", "python\n",
    ".venv/bin/python", "./python", "../python", "/usr/../bin/python", "/usr//bin/python", "//usr/bin/python",
    r"C:python.exe", r"C:\Python313\..\python.exe", r"C:\Python313.\python.exe", r"\\?\C:\Python313\python.exe",
    "/usr/\x7f/bin/python3.13"])
def test_wrapped_unsupported_relative_quoted_and_ambiguous_executables_fail(executable: str) -> None:
    with pytest.raises(ValueError):
        command_options("render.health", [executable, *valid_argv("render.health")[1:]])


@pytest.mark.parametrize("change", ["module", "family", "action", "interpreter-flag", "two-modules", "quoted-command"])
def test_module_and_exact_registered_path_are_bound(change: str) -> None:
    argv = valid_argv("google.gsc-query")
    if change == "module":
        argv[2] = "untrusted"
    elif change == "family":
        argv[3] = "media"
    elif change == "action":
        argv[4] = "gsc-aggregate"
    elif change == "interpreter-flag":
        argv.insert(1, "-B")
    elif change == "two-modules":
        argv[1:1] = ["-m", "other"]
    else:
        argv = [" ".join(argv)]
    with pytest.raises(ValueError):
        command_options("google.gsc-query", argv)


@pytest.mark.parametrize("argv", [None, [], "python -m seoctl", ("python", "-m"), [False], ["python", None], ["python\x00"]])
def test_non_array_or_non_string_capture_is_not_actual_argv(argv: object) -> None:
    with pytest.raises(ValueError):
        command_options("render.health", argv)


@pytest.mark.parametrize("value", ["-1", "-.5", "-1.5", "-1.", "-", "- literal query", "-h invalid"])
def test_actual_source_option_value_tokenization_is_preserved(value: str) -> None:
    argv = valid_argv("media.youtube-search")
    argv[-1] = value
    parser = _source_parser("media.youtube-search")
    if value in {"-1.", "-h invalid"}:
        with pytest.raises(SystemExit):
            parser.parse_args(argv[4:])
        with pytest.raises(ValueError):
            command_options("media.youtube-search", argv)
    else:
        assert parser.parse_args(argv[4:]).query == value
        assert command_options("media.youtube-search", argv)["--query"] == [value]


@pytest.mark.parametrize("query", ["--fixture=/synthetic/input", "-1.", "flowers; echo literal", "café buffalo",
    "  café buffalo  ", "\tSYNTHETIC query\n", "cafe\u0301 buffalo", "x" * 500])
def test_explicit_equals_query_is_literal_inert_data_not_a_second_command(query: str) -> None:
    argv = valid_argv("media.youtube-search")[:-2] + ["--query=" + query]
    assert _source_parser("media.youtube-search").parse_args(argv[4:]).query == query
    assert command_options("media.youtube-search", argv)["--query"] == [query]


@pytest.mark.parametrize(("command", "extra"), [
    ("google.gsc-query", ["--dimension", "query", "--dimension=query"]),
    ("google.ga4-report", ["--metric", "sessions", "--metric", "sessions"]),
    ("google.gsc-aggregate", ["--dimension", "query"]),
    ("google.gsc-query", ["--aggregation-type", "byProperty", "--dimension", "page"]),
    ("google.gsc-query", ["--row-limit", "25001"]), ("google.gsc-query", ["--max-pages", "0"]),
    ("google.gsc-query", ["--search-type", "unknown"]), ("google.gsc-query", ["--data-state", "fake"]),
    ("google.ga4-report", ["--limit", "0"]), ("google.ga4-report", ["--offset", "-1"]),
    ("google.ga4-report", ["--currency-code", "usd"]), ("google.ga4-report", ["--metric", "not:a:name"]),
    ("render.page", ["--width", "319"]), ("render.page", ["--height", "4321"]),
    ("render.page", ["--timeout-ms", "999"]), ("render.page", ["--wait-until", "unknown"]),
    ("render.page", ["--block-resource-type", "websocket"]), ("render.page", ["--full-page"]),
    ("render.screenshot", ["--full-page=true"]), ("render.screenshot", ["--full-page", "false"]),
    ("render.screenshot", ["--full-page", "--full-page"]),
    ("links.commoncrawl", ["--max-pages", "6"]), ("links.commoncrawl", ["--page-size", "1001"]),
    ("media.youtube-search", ["--max-results", "51"]), ("media.youtube-search", ["--pages", "4"]),
    ("media.youtube-search", ["--order", "unknown"]), ("media.youtube-search", ["--safe-search", "unknown"]),
    ("google.gsc-query", ["--row-limit", "True"]), ("google.gsc-query", ["--row-limit", "1.0"]),
    ("google.gsc-query", ["--row-limit", "1", "--row-limit", "1"]),
    ("google.gsc-query", ["--row-limit"]), ("google.gsc-query", ["--dimension"]),
    ("indexnow.submit", ["--execute=false"]), ("indexnow.submit", ["--execute"]),
    ("indexnow.submit", ["--confirm", "INDEXNOW_SUBMIT"]),
])
def test_source_cardinality_choice_and_bounded_value_invariants(command: str, extra: list[str]) -> None:
    with pytest.raises(ValueError):
        command_options(command, [*valid_argv(command), *extra])


@pytest.mark.parametrize("command", ["google.gsc-query", "google.gsc-aggregate", "google.ga4-report"])
def test_real_report_dates_allowed_but_invalid_or_verification_dates_fail(command: str) -> None:
    argv = valid_argv(command)
    assert command_options(command, argv + ["--start-date=2026-10-01", "--end-date", "2026-10-02"])["--start-date"] == ["2026-10-01"]
    for dates in (["--start-date", "2026-02-30"], ["--start-date", "today"],
                  ["--start-date", "2026-10-02", "--end-date", "2026-10-01"]):
        with pytest.raises(ValueError):
            command_options(command, argv + dates)


@pytest.mark.parametrize("query", ["", "   \t\n", "x" * 501])
def test_youtube_preserves_source_nonempty_and_character_limit(query: str) -> None:
    argv = valid_argv("media.youtube-search")
    argv[-1] = query
    with pytest.raises(ValueError):
        command_options("media.youtube-search", argv)


@pytest.mark.parametrize("mutation", ["missing-execute", "missing-confirm", "wrong-confirm"])
def test_actual_explicit_indexnow_submission_not_dry_run(mutation: str) -> None:
    argv = valid_argv("indexnow.submit")
    if mutation == "missing-execute":
        argv.remove("--execute")
    elif mutation == "missing-confirm":
        argv[-2:] = []
    else:
        argv[-1] = "VALIDATE_ONLY"
    with pytest.raises(ValueError):
        command_options("indexnow.submit", argv)


def test_argv_files_commands_and_network_are_not_executed(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Inert argv validation performed an actual operation")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert command_options("indexnow.submit", valid_argv("indexnow.submit"))["--urls"] == ["/synthetic/input.json"]
    assert command_options("render.screenshot", valid_argv("render.screenshot"))["--output"] == ["/synthetic/capture.png"]
    with pytest.raises(ValueError):
        command_options("unknown.command", valid_argv("render.health"))
    with pytest.raises(ValueError):
        valid_argv("unknown.command")


@pytest.mark.parametrize("name", ["--row-limit", "--start-date"])
def test_invalid_scalar_errors_do_not_echo_captured_private_data(name: str) -> None:
    sentinel = "SYNTHETIC_PRIVATE_CAPTURE_DO_NOT_ECHO"
    with pytest.raises(ValueError) as failure:
        command_options("google.gsc-query", [*valid_argv("google.gsc-query"), name, sentinel])
    assert sentinel not in str(failure.value)
