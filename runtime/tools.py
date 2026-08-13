"""Tool dispatch for runtime adapters with bounded isolation and telemetry."""

from __future__ import annotations

import asyncio
import ipaddress
import os
import urllib.parse
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from adapters.registry import default_adapters
from runtime.adapter_contracts import (
    BLOCKING_ADAPTER_STATUSES,
    INVALID_ADAPTER_STATUSES,
    MISSING_ADAPTER_STATUSES,
    PARTIAL_ADAPTER_STATUSES,
    SUCCESS_ADAPTER_STATUSES,
    AdapterNotConfigured,
    RuntimeAdapter,
    validate_adapter_result,
)
from runtime.telemetry import OperationTelemetry, redact


class ToolDispatchError(RuntimeError):
    """Raised when a runtime tool cannot be dispatched."""


@dataclass
class ToolRequest:
    tool: str
    arguments: dict[str, Any]
    required: bool = False
    timeout_seconds: float | None = None
    budget_approved: bool = False


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


@dataclass(frozen=True)
class ToolAccessRequirement:
    tool: str
    requires_budget_approval: bool = False
    credential_env: tuple[str, ...] = ()
    notes: str = ""


TOOL_ACCESS_REQUIREMENTS: dict[str, ToolAccessRequirement] = {
    "gsc_live": ToolAccessRequirement(
        tool="gsc_live",
        credential_env=("GOOGLE_APPLICATION_CREDENTIALS",),
        notes="Google Search Console live API access.",
    ),
    "google_search_console": ToolAccessRequirement(
        tool="google_search_console",
        credential_env=("GOOGLE_APPLICATION_CREDENTIALS",),
        notes="Google Search Console live API access.",
    ),
    "ga4_live": ToolAccessRequirement(
        tool="ga4_live",
        credential_env=("GOOGLE_APPLICATION_CREDENTIALS",),
        notes="GA4 Data API access.",
    ),
    "google_analytics_data": ToolAccessRequirement(
        tool="google_analytics_data",
        credential_env=("GOOGLE_APPLICATION_CREDENTIALS",),
        notes="GA4 Data API access.",
    ),
    "google_pagespeed_live": ToolAccessRequirement(
        tool="google_pagespeed_live",
        credential_env=("GOOGLE_PAGESPEED_API_KEY",),
        notes="PageSpeed Insights live API access.",
    ),
    "pagespeed_live": ToolAccessRequirement(
        tool="pagespeed_live",
        credential_env=("GOOGLE_PAGESPEED_API_KEY",),
        notes="PageSpeed Insights live API access.",
    ),
    "google_crux_current": ToolAccessRequirement(
        tool="google_crux_current",
        credential_env=("GOOGLE_PAGESPEED_API_KEY",),
        notes="CrUX live API access.",
    ),
    "crux_current": ToolAccessRequirement(
        tool="crux_current",
        credential_env=("GOOGLE_PAGESPEED_API_KEY",),
        notes="CrUX live API access.",
    ),
    "google_crux_history": ToolAccessRequirement(
        tool="google_crux_history",
        credential_env=("GOOGLE_PAGESPEED_API_KEY",),
        notes="CrUX history API access.",
    ),
    "crux_history": ToolAccessRequirement(
        tool="crux_history",
        credential_env=("GOOGLE_PAGESPEED_API_KEY",),
        notes="CrUX history API access.",
    ),
    "authority_media": ToolAccessRequirement(
        tool="authority_media",
        requires_budget_approval=True,
        notes="Authority/media data can involve paid or quota-limited providers.",
    ),
}


SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "client_secret",
    "key",
    "password",
    "refresh_token",
    "secret",
    "token",
}


REQUIRED_TOOL_FAILURE_STATES = frozenset({"BLOCKED", "INVALID", "MISSING"})


def _adapter_evidence_state(status: str, *, required: bool) -> str:
    """Map one validated status to its fail-closed workflow evidence state."""

    if status in SUCCESS_ADAPTER_STATUSES:
        return "AVAILABLE"
    if status in INVALID_ADAPTER_STATUSES:
        return "INVALID"
    if status in MISSING_ADAPTER_STATUSES:
        return "MISSING"
    if required and status in PARTIAL_ADAPTER_STATUSES | BLOCKING_ADAPTER_STATUSES:
        return "BLOCKED"
    if status in BLOCKING_ADAPTER_STATUSES:
        return "INVALID"
    return "PARTIAL"


def _indeterminate_timeout_message(tool: str, timeout: float) -> str:
    return (
        f"Tool {tool} exceeded its {timeout:g}-second response deadline; "
        "thread-backed work may still be running, so side-effect outcome is unknown."
    )


def _credential_query_keys(query: str) -> set[str]:
    return {
        query_key.lower()
        for query_key, _ in urllib.parse.parse_qsl(query, keep_blank_values=True)
    } & SENSITIVE_QUERY_KEYS


def _unsafe_host_reason(key: str, host: str) -> str | None:
    normalized_host = host.rstrip(".").lower()
    if normalized_host in {"localhost", "local"}:
        return f"{key} points to a local host"
    try:
        ip = ipaddress.ip_address(normalized_host)
    except ValueError:
        return None
    return f"{key} points to a non-public address" if not ip.is_global else None


def _unsafe_url_reason(key: str, value: str) -> str | None:
    try:
        parsed = urllib.parse.urlsplit(value)
    except ValueError:
        return f"{key} contains an invalid URL"
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return f"{key} must use http or https"
    if parsed.username or parsed.password:
        return f"{key} must not contain credentials"
    if _credential_query_keys(parsed.query):
        return f"{key} contains credential-like query parameters"
    return _unsafe_host_reason(key, parsed.hostname) if parsed.hostname else None


class ToolDispatcher:
    def __init__(
        self,
        adapters: Mapping[str, RuntimeAdapter] | None = None,
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

    def _preflight_access(self, request: ToolRequest, trace: OperationTelemetry) -> ToolDispatchResult | None:
        requirement = TOOL_ACCESS_REQUIREMENTS.get(request.tool)
        if requirement and requirement.requires_budget_approval and not request.budget_approved:
            return self._failure(
                request,
                trace,
                status="FAILED",
                error_type="BudgetApprovalRequired",
                message=f"Tool {request.tool} requires explicit budget approval. {requirement.notes}",
                evidence_state="BLOCKED",
            )
        if requirement and requirement.credential_env:
            missing = [name for name in requirement.credential_env if not os.getenv(name)]
            if missing:
                return self._failure(
                    request,
                    trace,
                    status="NOT_CONFIGURED",
                    error_type="MissingCredential",
                    message=f"Tool {request.tool} is missing credential environment variables: {', '.join(missing)}",
                    evidence_state="BLOCKED" if request.required else "MISSING",
                )

        unsafe = self._first_unsafe_url_argument(request.arguments)
        if unsafe:
            return self._failure(
                request,
                trace,
                status="FAILED",
                error_type="UnsafeURL",
                message=unsafe,
                evidence_state="BLOCKED" if request.required else "INVALID",
            )
        return None

    def _first_unsafe_url_argument(self, arguments: dict[str, Any]) -> str | None:
        for key, value in arguments.items():
            if not isinstance(value, str) or key.lower() not in {
                "url",
                "target_url",
                "origin",
                "site_url",
            }:
                continue
            if reason := _unsafe_url_reason(key, value):
                return reason
        return None

    def _timeout_for(self, request: ToolRequest) -> float:
        timeout = (
            self.default_timeout_seconds
            if request.timeout_seconds is None
            else float(request.timeout_seconds)
        )
        if not 0.1 <= timeout <= 600:
            raise ValueError("Tool timeout must be from 0.1 to 600 seconds.")
        return timeout

    async def _fetch_result(self, adapter: RuntimeAdapter, request: ToolRequest, timeout: float) -> Any:
        return validate_adapter_result(
            await asyncio.wait_for(
                asyncio.to_thread(adapter.fetch, **request.arguments),
                timeout=timeout,
            )
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
        blocked = self._preflight_access(request, trace)
        if blocked is not None:
            return blocked
        try:
            timeout = self._timeout_for(request)
        except ValueError as exc:
            return self._failure(
                request,
                trace,
                status="FAILED",
                error_type="InvalidTimeout",
                message=str(exc),
                evidence_state="BLOCKED" if request.required else "INVALID",
            )

        try:
            result = await self._fetch_result(adapter, request, timeout)
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
                status="DEADLINE_EXCEEDED_INDETERMINATE",
                error_type="ToolDeadlineExceededWorkMayContinue",
                message=_indeterminate_timeout_message(request.tool, timeout),
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

        evidence_state = _adapter_evidence_state(result.status, required=request.required)
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
