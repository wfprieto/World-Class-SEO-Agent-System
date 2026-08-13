from __future__ import annotations

from typing import Any

import pytest

from adapters.gsc_live_example import GSCLiveExampleAdapter
from integrations.google.client import GoogleAPIError


class _OAuth:
    def token(self) -> str:
        return "credential-value"


class _Client:
    def __init__(self) -> None:
        self.call: dict[str, Any] = {}

    def request(self, endpoint: str, **kwargs: Any) -> dict[str, Any]:
        self.call = {"endpoint": endpoint, **kwargs}
        return {"rows": [{"clicks": 2, "impressions": 7}]}


def test_gsc_example_delegates_credentials_to_bounded_google_transport() -> None:
    client = _Client()
    adapter = GSCLiveExampleAdapter(oauth=_OAuth(), client=client)  # type: ignore[arg-type]

    result = adapter.fetch(
        "https://example.com/",
        start_date="2026-07-01",
        end_date="2026-07-02",
    )

    assert client.call["service"] == "gsc"
    assert client.call["access_token"] == "credential-value"
    assert client.call["endpoint"].startswith("https://www.googleapis.com/")
    assert "credential-value" not in repr(result)


def test_gsc_example_rejects_unapproved_oauth_host_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GSC_CLIENT_ID", "client")
    monkeypatch.setenv("GSC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("GSC_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("GSC_TOKEN_URI", "https://attacker.invalid/token")

    with pytest.raises(GoogleAPIError, match="approved HTTPS Google OAuth host") as captured:
        GSCLiveExampleAdapter()._access_token()

    assert captured.value.state == "BLOCKED"
