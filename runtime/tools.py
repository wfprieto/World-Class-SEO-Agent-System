"""Tool dispatch for runtime adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, asdict
from typing import Any

from adapters.registry import default_adapters


class ToolDispatchError(RuntimeError):
    """Raised when a runtime tool cannot be dispatched."""


@dataclass
class ToolRequest:
    tool: str
    arguments: dict[str, Any]


@dataclass
class ToolDispatchResult:
    tool: str
    status: str
    data: Any
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class ToolDispatcher:
    def __init__(self, adapters: dict[str, Any] | None = None) -> None:
        self.adapters = adapters or default_adapters()

    async def dispatch(self, request: ToolRequest) -> ToolDispatchResult:
        if request.tool not in self.adapters:
            raise ToolDispatchError(f"Unknown tool adapter: {request.tool}")
        adapter = self.adapters[request.tool]
        result = await asyncio.to_thread(adapter.fetch, **request.arguments)
        return ToolDispatchResult(
            tool=request.tool,
            status=result.status,
            data=result.data,
            warnings=result.warnings,
        )

    async def dispatch_many(self, requests: list[ToolRequest]) -> list[ToolDispatchResult]:
        return await asyncio.gather(*(self.dispatch(request) for request in requests))
