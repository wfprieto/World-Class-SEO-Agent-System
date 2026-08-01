from __future__ import annotations

from integrations.technical.http import HttpHop
from integrations.technical.parsing import (
    PageParser,
    cwv_metrics,
    decode_http_body,
    parse_jsonld_scripts,
    parse_robots,
    performance_score,
    schema_types,
)


def test_page_parser_ignores_non_jsonld_and_preserves_empty_jsonld_boundary():
    parser = PageParser()
    parser.feed(
        "<script type='text/javascript'>{ignored: true}</script>"
        "<script type='application/ld+json; charset=utf-8'></script>"
    )

    assert parser.jsonld_texts == [""]
    items, invalid = parse_jsonld_scripts(parser.jsonld_texts)
    assert items == []
    assert invalid == [{"script_index": 0, "error": "empty JSON-LD script"}]


def test_jsonld_parser_preserves_script_index_for_malformed_and_flattens_arrays():
    items, invalid = parse_jsonld_scripts(
        ['{"@type":"Article"}', "{broken", '[{"@type":"WebSite"}]']
    )

    assert items == [{"@type": "Article"}, {"@type": "WebSite"}]
    assert len(invalid) == 1
    assert invalid[0]["script_index"] == 1
    assert "Expecting property name" in invalid[0]["error"]


def test_schema_type_collection_ignores_non_objects_and_walks_graphs():
    assert schema_types(
        [
            None,
            {"@type": ["Article", 3], "@graph": [{"@type": "Person"}, "bad"]},
        ]
    ) == {"Article", "Person"}


def test_decode_unknown_charset_falls_back_to_utf8_replacement():
    hop = HttpHop(
        requested_url="https://example.com",
        final_url="https://example.com",
        status_code=200,
        headers={"Content-Type": "text/html; charset=not-a-real-codec"},
        body=b"caf\xc3\xa9",
        elapsed_ms=1,
    )

    assert decode_http_body(hop) == "café"


def test_robots_parser_ignores_comments_and_preserves_unknown_directives():
    groups, sitemaps, unknown = parse_robots(
        "Disallow: /private # comment\n"
        "Sitemap: https://example.com/map.xml\n"
        "Sitemap: https://example.com/map.xml\n"
        "Clean-param: ref /\n"
        "Malformed line\n"
    )

    assert groups == [
        {"user_agents": ["*"], "rules": [{"directive": "disallow", "value": "/private"}]}
    ]
    assert sitemaps == ["https://example.com/map.xml"]
    assert unknown == ["Clean-param: ref /"]


def test_cwv_parsing_rejects_non_numeric_values_without_inventing_evidence():
    payload = {
        "lcp_ms": "not-a-number",
        "inp_ms": None,
        "cls": [],
        "performance_score": "unknown",
    }

    metrics = cwv_metrics(payload)
    assert all(item == {"value": None, "rating": "not_available"} for item in metrics.values())
    assert performance_score(payload) is None
