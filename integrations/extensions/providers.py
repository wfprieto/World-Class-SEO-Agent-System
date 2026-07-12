"""Executable optional-provider discovery, preflight, config, and cost controls."""

from __future__ import annotations

from typing import Any

from adapters.base import AdapterResult
from adapters.mcp_extensions import (
    capability_report,
    estimate_cost,
    preflight,
    render_config,
)


class ProviderService:
    def list(self, connected_mcp: set[str] | None = None) -> AdapterResult:
        return AdapterResult(
            source="optional-integrations",
            status="ok",
            data=capability_report(connected_mcp),
            warnings=[
                "Availability is a credential or host-connection presence check, not a live smoke test."
            ],
        )

    def preflight(
        self, *, provider: str, connected_mcp: set[str] | None = None
    ) -> AdapterResult:
        data = preflight(provider, connected_mcp)
        status = {
            "AVAILABLE": "ok",
            "NOT_CONFIGURED": "not_configured",
            "BLOCKED_BY_CONTRACT": "blocked",
            "HOST_CLIENT_ONLY": "partial",
        }.get(str(data["state"]), "partial")
        return AdapterResult(
            source=f"optional-integrations:{provider}",
            status=status,
            data=data,
            warnings=list(data.get("warnings", [])),
        )

    def config(self, *, provider: str, client: str = "generic") -> AdapterResult:
        data = render_config(provider, client)
        status = "blocked" if data["state"] == "BLOCKED_BY_CONTRACT" else "ok"
        return AdapterResult(
            source=f"optional-integrations:{provider}",
            status=status,
            data=data,
            warnings=[
                "No host configuration was written and no provider connection was attempted."
            ],
        )

    def estimate(
        self,
        *,
        provider: str,
        units: int,
        unit_cost: float | None = None,
        approved_ceiling: float | None = None,
        approved: bool = False,
    ) -> AdapterResult:
        data = estimate_cost(
            provider,
            units=units,
            unit_cost=unit_cost,
            approved_ceiling=approved_ceiling,
            approved=approved,
        )
        status = "ok" if data["state"] in {"AVAILABLE", "APPROVED"} else "blocked"
        return AdapterResult(
            source=f"optional-integrations:{provider}",
            status=status,
            data=data,
            warnings=[
                "This is an operator-supplied cost model. It does not fetch current provider pricing."
            ],
        )


class ExtensionAdapter:
    name = "optional_extensions"

    def __init__(self) -> None:
        self.providers = ProviderService()

    def fetch(self, operation: str, **kwargs: Any) -> AdapterResult:
        handlers = {
            "list": self.providers.list,
            "preflight": self.providers.preflight,
            "config": self.providers.config,
            "estimate": self.providers.estimate,
        }
        if operation not in handlers:
            raise ValueError(f"unsupported optional-integration operation: {operation}")
        return handlers[operation](**kwargs)
