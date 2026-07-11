"""Tool dispatch for runtime adapters with per-tool failure isolation."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any

from adapters.base import AdapterNotConfigured
from adapters.registry import default_adapters


class ToolDispatchError(RuntimeError):
    """Raised when a runtime tool cannot be dispatched."""


@dataclass
class ToolRequest:
    tool: str
    arguments: dict[str, Any]
    required: bool = False


@dataclass
class ToolDispatchResult:
    tool: str
    status: str
    data: Any
    warnings: list[str]
    error_type: str | None = None
    sanitized_error: str | None = None
    evidence_state: str = "AVAILABLE"
    required: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class ToolDispatcher:
    def __init__(self, adapters: dict[str, Any] | None = None) -> None:
        self.adapters = adapters or default_adapters()

    async def dispatch(self, request: ToolRequest) -> ToolDispatchResult:
        if request.tool not in self.adapters:
            return ToolDispatchResult(
                tool=request.tool,
                status="failed",
                data=None,
                warnings=[],
                error_type="UnknownTool",
                sanitized_error=f"Unknown tool adapter: {request.tool}",
                evidence_state="BLOCKED" if request.required else "MISSING",
                required=request.required,
            )
        adapter = self.adapters[request.tool]
        try:
            result = await asyncio.to_thread(adapter.fetch, **request.arguments)
        except AdapterNotConfigured as exc:
            return ToolDispatchResult(
                tool=request.tool,
                status="unavailable",
                data=None,
                warnings=[],
                error_type=type(exc).__name__,
                sanitized_error=str(exc)[:500],
                evidence_state="BLOCKED" if request.required else "MISSING",
                required=request.required,
            )
        except (TypeError, ValueError, OSError, RuntimeError) as exc:
            return ToolDispatchResult(
                tool=request.tool,
                status="failed",
                data=None,
                warnings=[],
                error_type=type(exc).__name__,
                sanitized_error=str(exc)[:500],
                evidence_state="BLOCKED" if request.required else "INVALID",
                required=request.required,
            )
        return ToolDispatchResult(
            tool=request.tool,
            status=result.status,
            data=result.data,
            warnings=result.warnings,
            evidence_state=(
                "AVAILABLE"
                if result.status in {"ok", "complete", "success"}
                else "PARTIAL"
            ),
            required=request.required,
        )

    async def dispatch_many(self, requests: list[ToolRequest]) -> list[ToolDispatchResult]:
        """Return one result per request; one adapter failure never erases the others."""
        return await asyncio.gather(*(self.dispatch(request) for request in requests))
