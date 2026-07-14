"""Tool dispatch for runtime adapters with bounded isolation and telemetry."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Protocol, runtime_checkable

from adapters.base import AdapterNotConfigured, AdapterResult
from adapters.registry import default_adapters
from runtime.telemetry import OperationTelemetry, redact


class ToolDispatchError(RuntimeError):
    """Raised when a runtime tool cannot be dispatched."""


@runtime_checkable
class RuntimeAdapter(Protocol):
    """Canonical runtime adapter contract."""

    def fetch(self, **kwargs: Any) -> AdapterResult: ...


@dataclass
class ToolRequest:
    tool: str
    arguments: dict[str, Any]
    required: bool = False
    timeout_seconds: float | None = None


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolDispatcher:
    def __init__(
        self,
        adapters: dict[str, Any] | None = None,
        *,
        max_telemetry_events: int = 1_000,
        default_timeout_seconds: float = 60.0,
    ) -> None:
        if not isinstance(max_telemetry_events, int) or not 1 <= max_telemetry_events <= 100_000:
            raise ValueError("max_telemetry_events must be an integer from 1 to 100000")
        if not isinstance(default_timeout_seconds, (int, float)) or not 0.1 <= float(
            default_timeout_seconds
        ) <= 600:
            raise ValueError("default_timeout_seconds must be from 0.1 to 600")
        raw_adapters = adapters if adapters is not None else dict(default_adapters())
        self.adapters: dict[str, RuntimeAdapter] = {}
        for name, adapter in raw_adapters.items():
            if not isinstance(name, str) or not name.strip():
                raise TypeError("adapter names must be non-empty strings")
            if not isinstance(adapter, RuntimeAdapter):
                raise TypeError(f"adapter {name!r} does not implement fetch(**kwargs)")
            self.adapters[name] = adapter
        self.max_telemetry_events = max_telemetry_events
        self.default_timeout_seconds = float(default_timeout_seconds)
        self._telemetry: list[dict[str, Any]] = []

    def _record(self, trace: OperationTelemetry, *, status: str, metadata: dict[str, Any]) -> None:
        event = trace.finish(status=status, metadata=metadata)
        if len(self._telemetry) >= self.max_telemetry_events:
            self._telemetry.pop(0)
        self._telemetry.append(event)

    def telemetry_snapshot(self) -> list[dict[str, Any]]:
        """Return a redacted copy of bounded per-operation telemetry."""
        return [dict(event) for event in self._telemetry]

    def _failure(
        self,
        request: ToolRequest,
        trace: OperationTelemetry,
        *,
        status: str,
        error_type: str,
        message: str,
        evidence_state: str,
    ) -> ToolDispatchResult:
        self._record(trace, status=status, metadata={"required": request.required})
        return ToolDispatchResult(
            tool=request.tool,
            status="unavailable" if status == "NOT_CONFIGURED" else "failed",
            data=None,
            warnings=[],
            error_type=error_type,
            sanitized_error=str(redact(message))[:500],
            evidence_state=evidence_state,
            required=request.required,
        )

    async def dispatch(self, request: ToolRequest) -> ToolDispatchResult:
        trace = OperationTelemetry(operation=request.tool)
        trace.request_count = 1
        if request.tool not in self.adapters:
            return self._failure(
                request,
                trace,
                status="FAILED",
                error_type="UnknownTool",
                message=f"Unknown tool adapter: {request.tool}",
                evidence_state="BLOCKED" if request.required else "MISSING",
            )

        adapter = self.adapters[request.tool]
        timeout = (
            self.default_timeout_seconds
            if request.timeout_seconds is None
            else float(request.timeout_seconds)
        )
        if not 0.1 <= timeout <= 600:
            return self._failure(
                request,
                trace,
                status="FAILED",
                error_type="InvalidTimeout",
                message="Tool timeout must be from 0.1 to 600 seconds.",
                evidence_state="BLOCKED" if request.required else "INVALID",
            )

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(adapter.fetch, **request.arguments),
                timeout=timeout,
            )
            if not isinstance(result, AdapterResult):
                raise TypeError("adapter fetch() must return AdapterResult")
        except AdapterNotConfigured as exc:
            return self._failure(
                request,
                trace,
                status="NOT_CONFIGURED",
                error_type=type(exc).__name__,
                message=str(exc),
                evidence_state="BLOCKED" if request.required else "MISSING",
            )
        except TimeoutError:
            return self._failure(
                request,
                trace,
                status="TIMEOUT",
                error_type="ToolTimeout",
                message=f"Tool {request.tool} exceeded its {timeout:g}-second execution limit.",
                evidence_state="BLOCKED" if request.required else "INVALID",
            )
        except asyncio.CancelledError:
            self._record(trace, status="CANCELLED", metadata={"required": request.required})
            raise
        except Exception as exc:  # Final isolation boundary: one adapter must not erase siblings.
            return self._failure(
                request,
                trace,
                status="FAILED",
                error_type="InternalAdapterError",
                message=f"{type(exc).__name__}: {exc}",
                evidence_state="BLOCKED" if request.required else "INVALID",
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
            warnings=list(result.warnings),
            evidence_state=evidence_state,
            required=request.required,
        )

    async def dispatch_many(self, requests: list[ToolRequest]) -> list[ToolDispatchResult]:
        """Return one result per request; one adapter failure never erases the others."""
        return list(await asyncio.gather(*(self.dispatch(request) for request in requests)))
