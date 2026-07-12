from __future__ import annotations

import asyncio

from adapters.base import AdapterResult
from adapters.registry import default_adapters
from runtime.tools import ToolDispatcher, ToolRequest


def test_runtime_registry_exposes_content_intelligence_tool():
    adapters = default_adapters()
    assert "content_intelligence" in adapters
    assert callable(adapters["content_intelligence"].fetch)


def test_tool_dispatcher_preserves_content_evidence_state():
    class FakeContent:
        def fetch(self, operation, **kwargs):
            return AdapterResult(
                source="content_intelligence",
                status="needs-review",
                data={
                    "operation": operation,
                    "data_state": "PARTIAL",
                    "unsupported_claims": 2,
                },
                warnings=["Two claims need evidence."],
            )

    dispatcher = ToolDispatcher(adapters={"content_intelligence": FakeContent()})
    result = asyncio.run(
        dispatcher.dispatch(
            ToolRequest(
                tool="content_intelligence",
                arguments={
                    "operation": "verify",
                    "claims": [],
                    "sources": [],
                },
                required=True,
            )
        )
    )
    assert result.status == "needs-review"
    assert result.evidence_state == "PARTIAL"
    assert result.data["unsupported_claims"] == 2
