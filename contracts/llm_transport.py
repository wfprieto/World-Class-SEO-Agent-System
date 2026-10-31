"""Consumer-owned LLM transport contracts; no concrete network construction."""

from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType
from typing import Protocol, TypeVar

RequestT = TypeVar("RequestT", contravariant=True)


class LLMConfigurationError(RuntimeError):
    """Raised when a configured LLM provider is missing required or safe settings."""


class LLMResponseStream(Protocol):
    @property
    def headers(self) -> Mapping[str, str]: ...

    def read(self, size: int) -> bytes: ...

    def __enter__(self) -> LLMResponseStream: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class LLMOpener(Protocol[RequestT]):
    def open(
        self,
        request: RequestT,
        *,
        timeout: float,
    ) -> LLMResponseStream: ...
