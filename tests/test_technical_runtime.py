from __future__ import annotations

import asyncio

from adapters.base import AdapterResult
from adapters.registry import default_adapters
from integrations.technical.browser import PlaywrightRenderer
from runtime.tools import ToolDispatcher, ToolRequest


def test_browser_health_handles_parent_module_probe_failure(monkeypatch):
    def missing(_name):
        raise ModuleNotFoundError("playwright")

    monkeypatch.setattr(
        "integrations.technical.browser.importlib.util.find_spec",
        missing,
    )
    health = PlaywrightRenderer().health()
    assert health.state == "NOT_CONFIGURED"
    assert health.dependency == "missing"
    assert health.executable is None


def test_runtime_registry_exposes_cohesive_technical_tools():
    adapters = default_adapters()
    assert "rendered_page_execution" in adapters
    assert "technical_execution" in adapters
    assert callable(adapters["rendered_page_execution"].fetch)
    assert callable(adapters["technical_execution"].fetch)


def test_tool_dispatcher_preserves_normalized_technical_evidence():
    class FakeTechnical:
        def fetch(self, operation, **kwargs):
            return AdapterResult(
                source="technical_execution",
                status="ok",
                data={
                    "operation": operation,
                    "url": kwargs["url"],
                    "data_state": "AVAILABLE",
                },
                warnings=[],
            )

    dispatcher = ToolDispatcher(adapters={"technical_execution": FakeTechnical()})
    result = asyncio.run(
        dispatcher.dispatch(
            ToolRequest(
                tool="technical_execution",
                arguments={
                    "operation": "indexability",
                    "url": "https://example.com/page",
                },
                required=True,
            )
        )
    )
    assert result.status == "ok"
    assert result.evidence_state == "AVAILABLE"
    assert result.data["operation"] == "indexability"
