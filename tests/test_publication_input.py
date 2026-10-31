"""Content and argv binding, without opening any captured file path."""

import hashlib

import pytest

from scripts.publication_input import captured_urls


def capture(content: str = "https://example.com/b\nhttps://example.com/a\n") -> dict:
    return {"kind": "command_input", "candidate_commit": "a" * 40,
            "prepared_subject_sha256": "b" * 64, "argument_path": "/not-opened/urls.txt",
            "format": "urls-text", "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}


def validate(row: dict) -> dict:
    return captured_urls(row, argument_path="/not-opened/urls.txt", candidate="a" * 40, digest="b" * 64, platform="ubuntu")


def test_captured_urls_parse_actual_text_rules_without_opening_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import pathlib

    monkeypatch.setattr(pathlib.Path, "open", lambda *_args, **_kwargs: pytest.fail("Publisher opened input path"))
    value = capture("\ufeff# source comment\r\nhttps://EXAMPLE.com:443/b\r\nhttps://example.com/a\r\n")
    assert validate(value) == {"kind": "indexnow_url_set", "values": ["https://example.com/a", "https://example.com/b"]}


@pytest.mark.parametrize("field,value", [("content", "https://different.example.com/"),
    ("sha256", "c" * 64), ("candidate_commit", "c" * 40),
    ("prepared_subject_sha256", "c" * 64), ("argument_path", "/different.txt"),
    ("format", "urls-json"), ("kind", "arbitrary")])
def test_capture_cannot_swap_bytes_argument_or_binding(field: str, value: object) -> None:
    row = capture()
    row[field] = value
    with pytest.raises(ValueError):
        validate(row)


def test_json_capture_matches_actual_source_array_and_bom_rules() -> None:
    content = '\ufeff["https://example.com/a", "https://example.com/a"]'
    row = {**capture(content), "argument_path": "/not-opened/urls.JSON", "format": "urls-json"}
    assert captured_urls(row, argument_path="/not-opened/urls.JSON", candidate="a" * 40, digest="b" * 64, platform="ubuntu") == {
        "kind": "indexnow_url_set", "values": ["https://example.com/a"]}


def test_dotfile_named_json_is_actual_text_input_not_json_format() -> None:
    row = {**capture("https://example.com/a\n"), "argument_path": "/not-opened/.json"}
    assert captured_urls(row, argument_path="/not-opened/.json", candidate="a" * 40, digest="b" * 64, platform="ubuntu") == {
        "kind": "indexnow_url_set", "values": ["https://example.com/a"]}


def test_dotfile_cannot_smuggle_json_interpretation_the_source_would_not_use() -> None:
    row = {**capture('["https://example.com/a"]'), "argument_path": "/not-opened/.json", "format": "urls-json"}
    with pytest.raises(ValueError):
        captured_urls(row, argument_path="/not-opened/.json", candidate="a" * 40, digest="b" * 64, platform="ubuntu")


@pytest.mark.parametrize("platform,content,format_name", [
    ("windows", "https://example.com/a\n", "urls-text"),
    ("ubuntu", '["https://example.com/a"]', "urls-json"),
])
def test_input_suffix_uses_actual_source_platform_without_path_access(platform: str, content: str, format_name: str) -> None:
    path = r"C:\not-opened\.json"
    row = {**capture(content), "argument_path": path, "format": format_name}
    assert captured_urls(row, argument_path=path, candidate="a" * 40, digest="b" * 64, platform=platform) == {
        "kind": "indexnow_url_set", "values": ["https://example.com/a"]}


@pytest.mark.parametrize("content", ['{"urls":["https://example.com/"]}', '[true]', '[NaN]',
    '["https://example.com/a", "https://other.example.com/b"]'])
def test_unsupported_json_payloads_fail_closed(content: str) -> None:
    row = {**capture(content), "argument_path": "/not-opened/urls.json", "format": "urls-json"}
    with pytest.raises(ValueError):
        captured_urls(row, argument_path="/not-opened/urls.json", candidate="a" * 40, digest="b" * 64, platform="ubuntu")
