"""ToolDispatcher-compatible wrappers for the technical execution services."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from adapters.base import AdapterResult
from integrations.technical.browser import RenderedPageService
from integrations.technical.inspection import TechnicalInspectionService


class RenderedPageExecutionAdapter:
    """Expose browser health, render, and screenshot through one runtime adapter."""

    name = "rendered_page_execution"

    def __init__(self, service: RenderedPageService | None = None) -> None:
        self.service = service or RenderedPageService()

    def fetch(self, operation: str = "page", **kwargs: Any) -> AdapterResult:
        normalized = operation.strip().lower().replace("_", "-")
        if normalized == "health":
            health = self.service.health()
            return AdapterResult(
                source=self.name,
                status="ok" if health.state == "AVAILABLE" else "not_configured",
                data={**asdict(health), "data_state": health.state},
                warnings=([] if health.state == "AVAILABLE" else ["Optional Playwright Chromium is not configured."]),
            )
        if normalized in {"page", "render"}:
            return self.service.render(**kwargs)
        if normalized == "screenshot":
            return self.service.screenshot(**kwargs)
        raise ValueError("operation must be health, page, or screenshot")


class TechnicalExecutionAdapter:
    """Expose bounded technical inspections through one canonical runtime tool."""

    name = "technical_execution"

    def __init__(self, service: TechnicalInspectionService | None = None) -> None:
        self.service = service or TechnicalInspectionService()

    def fetch(self, operation: str, **kwargs: Any) -> AdapterResult:
        normalized = operation.strip().lower().replace("_", "-")
        handlers: dict[str, Callable[..., AdapterResult]] = {
            "robots": self.service.robots,
            "sitemap": self.service.sitemap,
            "hreflang": self.service.hreflang,
            "preload": self.service.preload,
            "redirect-chain": self.service.redirect_chain,
            "indexability": self.service.indexability,
            "cwv": self.service.cwv,
            "schema-detect": self.service.schema_detect,
            "schema-validate": self.service.schema_validate,
            "schema-generate": self.service.schema_generate,
        }
        handler = handlers.get(normalized)
        if handler is None:
            raise ValueError(
                "operation must be robots, sitemap, hreflang, preload, redirect-chain, "
                "indexability, cwv, schema-detect, schema-validate, or schema-generate"
            )
        return handler(**kwargs)
