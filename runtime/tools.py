"""Tool dispatch for runtime adapters with per-tool failure isolation and telemetry."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any

from adapters.base import AdapterNotConfigured
from adapters.registry import default_adapters
from runtime.telemetry import OperationTelemetry, redact


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
    def __init__(
        self,
        adapters: dict[str, Any] | None = None,
        *,
        max_telemetry_events: int = 1_000,
    ) -> None:
        if not isinstance(max_telemetry_events, int) or not 1 <= max_telemetry_events <= 100_000:
            raise ValueError("max_telemetry_events must be an integer from 1 to 100000")
        self.adapters = adapters or default_adapters()
        self.max_telemetry_events = max_telemetry_events
        self._telemetry: list[dict[str, Any]] = []

    def _record(self, trace: OperationTelemetry, *, status: str, metadata: dict[str, Any]) -> None:
        event = trace.finish(status=status, metadata=metadata)
        if len(self._telemetry) >= self.max_telemetry_events:
            self._telemetry.pop(0)
        self._telemetry.append(event)

    def telemetry_snapshot(self) -> list[dict[str, Any]]:
        """Return a redacted copy of bounded per-operation telemetry."""
        return [dict(event) for event in self._telemetry]

    async def dispatch(self, request: ToolRequest) -> ToolDispatchResult:
        trace = OperationTelemetry(operation=request.tool)
        trace.request_count = 1
        if request.tool not in self.adapters:
            self._record(trace, status="FAILED", metadata={"required": request.required})
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
            self._record(trace, status="NOT_CONFIGURED", metadata={"required": request.required})
            return ToolDispatchResult(
                tool=request.tool,
                status="unavailable",
                data=None,
                warnings=[],
                error_type=type(exc).__name__,
                sanitized_error=str(redact(str(exc)))[:500],
                evidence_state="BLOCKED" if request.required else "MISSING",
                required=request.required,
            )
        except (TypeError, ValueError, OSError, RuntimeError) as exc:
            self._record(trace, status="FAILED", metadata={"required": request.required})
            return ToolDispatchResult(
                tool=request.tool,
                status="failed",
                data=None,
                warnings=[],
                error_type=type(exc).__name__,
                sanitized_error=str(redact(str(exc)))[:500],
                evidence_state="BLOCKED" if request.required else "INVALID",
                required=request.required,
            )
        evidence_state = "AVAILABLE" if result.status in {"ok", "complete", "success"} else "PARTIAL"
        self._record(
            trace,
            status=str(result.status).upper(),
            metadata={"evidence_state": evidence_state, "required": request.required},
        )
        return ToolDispatchResult(
            tool=request.tool,
            status=result.status,
            data=result.data,
            warnings=result.warnings,
            evidence_state=evidence_state,
            required=request.required,
        )

    async def dispatch_many(self, requests: list[ToolRequest]) -> list[ToolDispatchResult]:
        """Return one result per request; one adapter failure never erases the others."""
        return await asyncio.gather(*(self.dispatch(request) for request in requests))
