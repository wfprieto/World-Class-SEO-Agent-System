from __future__ import annotations

import pytest

from runtime.llm import LLMConfigurationError, OpenAICompatibleClient


def test_openai_client_rejects_non_https_endpoint():
    with pytest.raises(LLMConfigurationError, match="HTTPS"):
        OpenAICompatibleClient(
            api_key="fixture-key",
            base_url="http://provider.example/v1",
            allow_custom_base_url=True,
        )


def test_custom_openai_compatible_endpoint_requires_explicit_approval():
    with pytest.raises(LLMConfigurationError, match="ALLOW_CUSTOM_LLM_BASE_URL"):
        OpenAICompatibleClient(
            api_key="fixture-key",
            base_url="https://provider.example/v1",
        )


def test_approved_custom_endpoint_uses_explicitly_supplied_key():
    client = OpenAICompatibleClient(
        api_key="fixture-custom-key",
        base_url="https://provider.example/v1",
        allow_custom_base_url=True,
    )
    assert client.base_url == "https://provider.example/v1"
    assert client.api_key == "fixture-custom-key"


def test_endpoint_rejects_embedded_credentials():
    with pytest.raises(LLMConfigurationError, match="embedded credentials"):
        OpenAICompatibleClient(
            api_key="fixture-key",
            base_url="https://user:password@provider.example/v1",
            allow_custom_base_url=True,
        )
