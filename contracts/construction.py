"""Neutral persistence and provider-control ports for explicit construction."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Any, Protocol

from contracts.adapter import AdapterResult

URLIdentity = Callable[[str], str]
RawFetch = Callable[[str], tuple[str, int | None, dict[str, str]]]


class RawPageResponse(Protocol):
    @property
    def body(self) -> bytes: ...

    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...


class RawPageClient(Protocol):
    def get(self, url: str) -> RawPageResponse: ...


class PageSpeedPort(Protocol):
    def fetch(
        self,
        url: str,
        strategy: str = "mobile",
        *,
        include_crux: bool = True,
    ) -> AdapterResult[dict[str, Any]]: ...


class PageDriftPort(Protocol):
    def capture(
        self,
        url: str,
        fields: dict[str, Any],
        *,
        source: str,
        status: str,
    ) -> int: ...

    def compare(self, url: str) -> dict[str, Any]: ...

    def history(self, url: str, limit: int = 20) -> list[dict[str, Any]]: ...


PageDriftFactory = Callable[[str | None], AbstractContextManager[PageDriftPort]]


class ProviderControls(Protocol):
    def capability_report(self, connected_mcp: set[str] | None = None) -> dict[str, Any]: ...

    def preflight(
        self,
        provider_id: str,
        connected_mcp: set[str] | None = None,
    ) -> dict[str, Any]: ...

    def render_config(self, provider_id: str, client: str = "generic") -> dict[str, Any]: ...

    def estimate_cost(
        self,
        provider_id: str,
        *,
        units: int,
        unit_cost: float | None = None,
        approved_ceiling: float | None = None,
        approved: bool = False,
    ) -> dict[str, Any]: ...


class ProviderServicePort(Protocol):
    def preflight(
        self,
        *,
        provider: str,
        connected_mcp: set[str] | None = None,
    ) -> AdapterResult[dict[str, Any]]: ...

    def estimate(
        self,
        *,
        provider: str,
        units: int,
        unit_cost: float | None = None,
        approved_ceiling: float | None = None,
        approved: bool = False,
    ) -> AdapterResult[dict[str, Any]]: ...
