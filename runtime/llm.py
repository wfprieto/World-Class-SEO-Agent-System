"""Model-agnostic LLM clients for the SEO runtime."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import AsyncIterator, Protocol

from tenacity import retry, stop_after_attempt, wait_exponential


logger = logging.getLogger(__name__)
_MAX_RESPONSE_BYTES = 10_000_000


class LLMConfigurationError(RuntimeError):
    """Raised when a configured LLM provider is missing required or safe settings."""


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
        request = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        content = (
            "Echo execution complete.\n\n"
            "This dry run proves routing, prompt assembly, memory and tool dispatch "
            "without calling a paid LLM.\n\n"
            f"Request:\n{request[:1200]}"
        )
        return LLMResponse(
            provider=self.provider,
            model=self.model,
            content=content,
            raw={"dry_run": True},
        )

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        response = await self.complete(messages)
        for token in response.content.split(" "):
            yield token + " "
            await asyncio.sleep(0)


def _approved_base_url(value: str, *, allow_custom: bool) -> tuple[str, bool]:
    parsed = urllib.parse.urlsplit(value.rstrip("/"))
    if parsed.scheme != "https":
        raise LLMConfigurationError("LLM base URL must use HTTPS.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise LLMConfigurationError("LLM base URL must have a hostname and no embedded credentials.")
    if parsed.query or parsed.fragment:
        raise LLMConfigurationError("LLM base URL cannot contain query parameters or fragments.")
    custom = parsed.hostname.lower() != "api.openai.com"
    if custom and not allow_custom:
        raise LLMConfigurationError(
            "Custom OpenAI-compatible endpoints require explicit ALLOW_CUSTOM_LLM_BASE_URL=true approval."
        )
    normalized = urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "")
    )
    return normalized, custom


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible client with an explicit custom-endpoint boundary."""

    provider = "openai-compatible"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        *,
        allow_custom_base_url: bool = False,
    ) -> None:
        raw_base = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        env_approval = os.getenv("ALLOW_CUSTOM_LLM_BASE_URL", "").lower() in {
            "1", "true", "yes",
        }
        self.base_url, custom = _approved_base_url(
            raw_base,
            allow_custom=allow_custom_base_url or env_approval,
        )
        # A custom endpoint does not silently inherit the OpenAI production credential.
        configured_key = (
            os.getenv("OPENAI_COMPATIBLE_API_KEY")
            if custom and api_key is None
            else os.getenv("OPENAI_API_KEY")
        )
        self.api_key = api_key or configured_key
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1")
        if not self.api_key:
            variable = "OPENAI_COMPATIBLE_API_KEY" if custom else "OPENAI_API_KEY"
            raise LLMConfigurationError(f"{variable} is required for this endpoint.")

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [asdict(message) for message in messages],
            "temperature": 0.2,
        }
        data = await asyncio.to_thread(
            self._post_json,
            f"{self.base_url}/chat/completions",
            payload,
        )
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(provider=self.provider, model=self.model, content=content, raw=data)

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        response = await self.complete(messages)
        yield response.content

    def _post_json(self, url: str, payload: dict) -> dict:
        logger.info("Calling approved OpenAI-compatible endpoint for model %s", self.model)
        return self._post_json_with_retry(url, payload)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _post_json_with_retry(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > _MAX_RESPONSE_BYTES:
                raise RuntimeError("LLM response exceeds size limit")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise RuntimeError("LLM response exceeds size limit")
            decoded = json.loads(raw.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise RuntimeError("LLM response JSON must be an object")
            return decoded


class AnthropicClient:
    """Minimal Anthropic Messages API client using only the Python standard library."""

    provider = "anthropic"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        if not self.api_key:
            raise LLMConfigurationError("ANTHROPIC_API_KEY is required for the Anthropic client.")

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        system = "\n\n".join(
            message.content for message in messages if message.role == "system"
        )
        user_messages = [asdict(message) for message in messages if message.role != "system"]
        payload = {
            "model": self.model,
            "max_tokens": 4000,
            "temperature": 0.2,
            "system": system,
            "messages": user_messages,
        }
        data = await asyncio.to_thread(
            self._post_json,
            "https://api.anthropic.com/v1/messages",
            payload,
        )
        content_blocks = data.get("content", [])
        content = "\n".join(
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        )
        return LLMResponse(provider=self.provider, model=self.model, content=content, raw=data)

    async def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]:
        response = await self.complete(messages)
        yield response.content

    def _post_json(self, url: str, payload: dict) -> dict:
        logger.info("Calling Anthropic messages endpoint for model %s", self.model)
        return self._post_json_with_retry(url, payload)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _post_json_with_retry(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > _MAX_RESPONSE_BYTES:
                raise RuntimeError("LLM response exceeds size limit")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(raw) > _MAX_RESPONSE_BYTES:
                raise RuntimeError("LLM response exceeds size limit")
            decoded = json.loads(raw.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise RuntimeError("LLM response JSON must be an object")
            return decoded


def build_llm_client(provider: str = "echo", model: str | None = None) -> LLMClient:
    normalized = provider.lower().strip()
    if normalized in {"echo", "dry-run", "dryrun"}:
        return EchoLLMClient(model=model or "echo-seo-runtime")
    if normalized in {"openai", "openai-compatible"}:
        return OpenAICompatibleClient(model=model)
    if normalized == "anthropic":
        return AnthropicClient(model=model)
    raise LLMConfigurationError(f"Unsupported LLM provider: {provider}")
