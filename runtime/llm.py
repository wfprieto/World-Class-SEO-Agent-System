"""Model-agnostic LLM clients for the SEO runtime."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from dataclasses import dataclass, asdict
from typing import AsyncIterator, Protocol


class LLMConfigurationError(RuntimeError):
    """Raised when a configured LLM provider is missing required settings."""


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    provider: str
    model: str
    content: str
    raw: dict

    def to_dict(self) -> dict:
        return asdict(self)


class LLMClient(Protocol):
    provider: str
    model: str

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        """Return one completed model response."""

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        """Yield response chunks."""


class EchoLLMClient:
    """Offline client used for tests, dry runs and deterministic demos."""

    provider = "echo"

    def __init__(self, model: str = "echo-seo-runtime") -> None:
        self.model = model

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        request = next((message.content for message in reversed(messages) if message.role == "user"), "")
        content = (
            "Echo execution complete.\n\n"
            "This dry run proves routing, prompt assembly, memory and tool dispatch without calling a paid LLM.\n\n"
            f"Request:\n{request[:1200]}"
        )
        return LLMResponse(provider=self.provider, model=self.model, content=content, raw={"dry_run": True})

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        response = await self.complete(messages)
        for token in response.content.split(" "):
            yield token + " "
            await asyncio.sleep(0)


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat client using only the Python standard library."""

    provider = "openai-compatible"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        if not self.api_key:
            raise LLMConfigurationError("OPENAI_API_KEY is required for the OpenAI-compatible client.")

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [asdict(message) for message in messages],
            "temperature": 0.2,
        }
        data = await asyncio.to_thread(self._post_json, f"{self.base_url}/chat/completions", payload)
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(provider=self.provider, model=self.model, content=content, raw=data)

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        response = await self.complete(messages)
        yield response.content

    def _post_json(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))


class AnthropicClient:
    """Minimal Anthropic Messages API client using only the Python standard library."""

    provider = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        if not self.api_key:
            raise LLMConfigurationError("ANTHROPIC_API_KEY is required for the Anthropic client.")

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        system = "\n\n".join(message.content for message in messages if message.role == "system")
        user_messages = [asdict(message) for message in messages if message.role != "system"]
        payload = {
            "model": self.model,
            "max_tokens": 4000,
            "temperature": 0.2,
            "system": system,
            "messages": user_messages,
        }
        data = await asyncio.to_thread(self._post_json, "https://api.anthropic.com/v1/messages", payload)
        content_blocks = data.get("content", [])
        content = "\n".join(block.get("text", "") for block in content_blocks if block.get("type") == "text")
        return LLMResponse(provider=self.provider, model=self.model, content=content, raw=data)

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        response = await self.complete(messages)
        yield response.content

    def _post_json(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))


def build_llm_client(provider: str = "echo", model: str | None = None) -> LLMClient:
    normalized = provider.lower().strip()
    if normalized in {"echo", "dry-run", "dryrun"}:
        return EchoLLMClient(model=model or "echo-seo-runtime")
    if normalized in {"openai", "openai-compatible"}:
        return OpenAICompatibleClient(model=model)
    if normalized == "anthropic":
        return AnthropicClient(model=model)
    raise LLMConfigurationError(f"Unsupported LLM provider: {provider}")
