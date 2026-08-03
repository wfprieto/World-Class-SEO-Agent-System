"""Fixed security mutations for credential-bearing LLM transport."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from runtime.llm import (
    AnthropicClient,
    LLMConfigurationError,
    OpenAICompatibleClient,
    _RejectCredentialRedirects,
    _retryable_transport_failure,
)


class _Response:
    def __init__(self, payload: dict) -> None:
        self.headers = {"Content-Length": str(len(json.dumps(payload).encode()))}
        self._body = json.dumps(payload).encode()
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self, limit: int) -> bytes:
        return self._body[:limit]


class _Opener:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.requests: list[urllib.request.Request] = []

    def open(self, request: urllib.request.Request, *, timeout: float):
        self.requests.append(request)
        assert timeout == 120
        return self.response


def test_credential_redirect_policy_rejects_every_target_without_echoing_secret() -> None:
    handler = _RejectCredentialRedirects()
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": "Bearer test-secret-value"},
    )
    with pytest.raises(LLMConfigurationError) as caught:
        handler.redirect_request(
            request, None, 307, "redirect", {}, "https://attacker.invalid/capture"
        )
    assert "test-secret-value" not in str(caught.value)
    assert "attacker.invalid" not in str(caught.value)


@pytest.mark.parametrize("status", [408, 425, 429, 500, 503, 599])
def test_only_transient_http_statuses_are_retryable(status: int) -> None:
    error = urllib.error.HTTPError("https://provider.invalid", status, "failed", {}, None)
    assert _retryable_transport_failure(error)


@pytest.mark.parametrize("status", [301, 302, 307, 308, 400, 401, 403, 404, 422])
def test_redirect_and_permanent_http_statuses_are_not_retryable(status: int) -> None:
    error = urllib.error.HTTPError("https://provider.invalid", status, "failed", {}, None)
    assert not _retryable_transport_failure(error)


@pytest.mark.parametrize(
    "error",
    [ValueError("json"), RuntimeError("oversize"), LLMConfigurationError("policy")],
)
def test_parser_size_and_policy_failures_are_not_retryable(error: BaseException) -> None:
    assert not _retryable_transport_failure(error)


def test_openai_uses_injected_bounded_opener_and_closes_response() -> None:
    response = _Response({"choices": [{"message": {"content": "ok"}}]})
    opener = _Opener(response)
    client = OpenAICompatibleClient(api_key="secret", opener=opener)
    payload = client._post_json_with_retry(
        "https://api.openai.com/v1/chat/completions",
        {"model": "fixture", "messages": []},
    )
    assert payload["choices"][0]["message"]["content"] == "ok"
    assert opener.requests[0].headers["Authorization"] == "Bearer secret"
    assert response.closed


def test_anthropic_uses_injected_bounded_opener_and_closes_response() -> None:
    response = _Response({"content": []})
    opener = _Opener(response)
    client = AnthropicClient(api_key="secret", opener=opener)
    assert client._post_json_with_retry(
        "https://api.anthropic.com/v1/messages", {"messages": []}
    ) == {"content": []}
    assert opener.requests[0].headers["X-api-key"] == "secret"
    assert response.closed
