"""Hermetic critical-boundary cases preserve original transport coverage floors."""

from __future__ import annotations

import copy
import io
import socket
import urllib.request
from http.client import HTTPMessage
from typing import Any

import pytest

from adapters.base import AdapterNotConfigured
from adapters.google_pagespeed_live import PSI_ENDPOINT, GooglePageSpeedLiveAdapter
from contracts.google import GoogleAPIError
from integrations.google.transport import _NoCrossHostRedirects


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("critical-boundary fixtures must not dial any network")

    def numeric_only(host: str, port: int, *args: object, **kwargs: object) -> list[tuple]:
        assert host == "93.184.216.34", "no external DNS lookup is permitted"
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (host, port))]

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", numeric_only)


class FixtureClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def request(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        assert endpoint == PSI_ENDPOINT, "these cases must not request CrUX or another provider"
        self.calls.append(endpoint)
        return copy.deepcopy(self.payload)


def test_google_redirect_keeps_approved_original_host_and_method() -> None:
    handler = _NoCrossHostRedirects({"www.googleapis.com", "analyticsdata.googleapis.com"})
    original = urllib.request.Request(
        "https://www.googleapis.com/source", headers={"Authorization": "Bearer synthetic"}
    )
    with io.BytesIO() as response:
        redirected = handler.redirect_request(
            original, response, 302, "Found", HTTPMessage(), "https://www.googleapis.com/target"
        )
    assert redirected is not None
    assert redirected.full_url == "https://www.googleapis.com/target"
    assert redirected.get_method() == "GET"
    assert redirected.get_header("Authorization") == "Bearer synthetic"


@pytest.mark.parametrize(
    "destination",
    [
        "http://www.googleapis.com/target",
        "https://attacker.invalid/target",
        "https://analyticsdata.googleapis.com/target",
    ],
)
def test_google_redirect_never_forwards_across_host_or_https_boundary(destination: str) -> None:
    handler = _NoCrossHostRedirects({"www.googleapis.com", "analyticsdata.googleapis.com"})
    original = urllib.request.Request("https://www.googleapis.com/source")
    with io.BytesIO() as response, pytest.raises(GoogleAPIError) as caught:
        handler.redirect_request(original, response, 302, "Found", HTTPMessage(), destination)
    assert caught.value.state == "BLOCKED"
    assert caught.value.status == 302
    assert "original approved Google host" in str(caught.value)


@pytest.mark.parametrize(
    "options,message",
    [
        ({"timeout": 0}, "timeout must be positive"),
        ({"max_retries": 6}, "max_retries must be an integer from 0 to 5"),
        ({"max_response_bytes": 0}, "max_response_bytes must be positive"),
    ],
)
def test_pagespeed_rejects_invalid_transport_limits(options: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        GooglePageSpeedLiveAdapter("synthetic", crux_api_key="synthetic", **options)


def test_pagespeed_strategy_type_rejected_before_provider_request() -> None:
    client = FixtureClient({})
    adapter = GooglePageSpeedLiveAdapter("synthetic", crux_api_key="synthetic", client=client)
    with pytest.raises(TypeError, match="strategy must be a string"):
        adapter.fetch("https://93.184.216.34/", strategy=1)
    assert client.calls == []


@pytest.mark.parametrize(
    "payload,expected_warnings",
    [
        ({}, ["PageSpeed response did not contain lighthouseResult."]),
        (
            {"lighthouseResult": {"runtimeError": {"code": "NO_FCP"}, "runWarnings": ["fixture"]}},
            ["Lighthouse runtime error: NO_FCP", "Lighthouse reported 1 run warning(s)."],
        ),
    ],
)
def test_pagespeed_missing_lab_data_is_truthfully_partial(
    payload: dict[str, Any], expected_warnings: list[str],
) -> None:
    client = FixtureClient(payload)
    adapter = GooglePageSpeedLiveAdapter("synthetic", crux_api_key="synthetic", client=client)
    result = adapter.fetch("https://93.184.216.34/", include_crux=False)
    assert result.status == "partial"
    assert result.data["performance_score"] is None
    assert result.data["crux_status"] == "skipped"
    assert result.data["crux_field"] is None
    assert result.warnings == expected_warnings
    assert client.calls == [PSI_ENDPOINT]


def test_pagespeed_missing_port_is_not_silent_default_network() -> None:
    adapter = GooglePageSpeedLiveAdapter("synthetic", crux_api_key="synthetic")
    with pytest.raises(AdapterNotConfigured, match="transport is not configured"):
        adapter.fetch("https://93.184.216.34/", include_crux=False)
