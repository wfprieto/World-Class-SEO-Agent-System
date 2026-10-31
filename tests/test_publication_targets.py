"""Target equivalence is explicit; opaque equal hashes are not authorization."""

import hashlib
import json

import pytest

from scripts.publication_targets import (
    normalize_scope,
    normalize_target,
    scope_digest,
    target_digest,
)


@pytest.mark.parametrize("value,expected", [
    ({"kind": "web_url", "value": "HTTPS://EXAMPLE.COM:443"},
     {"kind": "web_url", "value": "https://example.com/"}),
    ({"kind": "web_url", "value": "https://example.com/café"},
     {"kind": "web_url", "value": "https://example.com/café"}),
    ({"kind": "gsc_property", "value": "sc-domain:EXAMPLE.COM"},
     {"kind": "gsc_property", "value": "sc-domain:example.com"}),
    ({"kind": "ga4_property", "value": "12345"},
     {"kind": "ga4_property", "value": "properties/12345"}),
    ({"kind": "domain", "value": "BÜCHER.DE"},
     {"kind": "domain", "value": "xn--bcher-kva.de"}),
    ({"kind": "youtube_query", "value": "  cafe\u0301  "},
     {"kind": "youtube_query", "value": "café"}),
    ({"kind": "indexnow_url_set", "values": ["https://EXAMPLE.COM/b", "https://example.com/a"]},
     {"kind": "indexnow_url_set", "values": ["https://example.com/a", "https://example.com/b"]}),
])
def test_known_target_normalization(value: dict, expected: dict) -> None:
    assert normalize_target(value) == expected
    raw = json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()
    assert target_digest(value) == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("value", [
    {"kind": "web_url", "value": "https://example.com@evil.invalid/"},
    {"kind": "web_url", "value": "https://127.0.0.1/"},
    {"kind": "web_url", "value": "https://[2001:4860:4860::8888%25eth0]/"},
    {"kind": "web_url", "value": "https://example.com:8443/"},
    {"kind": "web_url", "value": "https://example.com/raw\x7fcontrol"},
    {"kind": "web_url", "value": "https://example.com/raw\x80control"},
    {"kind": "web_url", "value": "https://0177.0.0.1/"},
    {"kind": "web_url", "value": "https://example.com/?api_key=private"},
    {"kind": "web_url", "value": "https://example.com/../private"},
    {"kind": "web_url", "value": "https://example.com/%252e%252e/private"},
    {"kind": "web_url", "value": "https://example.com/#fragment"},
    {"kind": "domain", "value": "*.example.com"},
    {"kind": "domain", "value": "faß.de"},
    {"kind": "ga4_property", "value": True},
    {"kind": "ga4_property", "value": "properties/12/other"},
    {"kind": "domain", "value": "example.com", "wildcard": True},
    {"kind": "indexnow_url_set", "values": ["https://a.example.com/", "https://b.example.com/"]},
    {"kind": "unknown", "value": "example.com"},
])
def test_ambiguous_or_unsupported_targets_fail_closed(value: dict) -> None:
    with pytest.raises(ValueError):
        normalize_target(value)


def test_scope_hash_binds_normalized_targets_methods_endpoints_and_redirects() -> None:
    value = {"targets": [{"kind": "web_url", "value": "https://EXAMPLE.COM/"}],
             "methods": ["GET"], "endpoint_hosts": ["EXAMPLE.COM"], "redirect_targets": []}
    result = normalize_scope(value)
    assert result["endpoint_hosts"] == ["example.com"]
    assert scope_digest(value) == hashlib.sha256(json.dumps(
        result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    changed = {**value, "methods": ["POST"]}
    assert scope_digest(changed) != scope_digest(value)


@pytest.mark.parametrize("change", ["wildcard", "unknown_method", "duplicate", "unknown_key"])
def test_scope_cannot_expand_implicitly(change: str) -> None:
    value = {"targets": [{"kind": "web_url", "value": "https://example.com/"}],
             "methods": ["GET"], "endpoint_hosts": ["example.com"], "redirect_targets": []}
    if change == "wildcard":
        value["endpoint_hosts"] = ["*.example.com"]
    elif change == "unknown_method":
        value["methods"] = ["DELETE"]
    elif change == "duplicate":
        value["targets"] *= 2
    else:
        value["allow_anywhere"] = True
    with pytest.raises(ValueError):
        normalize_scope(value)
