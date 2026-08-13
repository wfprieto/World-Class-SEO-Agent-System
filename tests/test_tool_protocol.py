from __future__ import annotations

import asyncio

from adapters.base import AdapterResult
from runtime.tools import TOOL_ACCESS_REQUIREMENTS, ToolDispatcher, ToolRequest


class NeverCalledAdapter:
    def fetch(self, **kwargs):
        raise AssertionError("adapter should have been blocked by preflight")


class OkAdapter:
    def fetch(self, **kwargs):
        return AdapterResult(source="ok", status="ok", data={"called": True}, warnings=[])


def test_cost_bearing_tools_require_budget_approval_before_dispatch():
    dispatcher = ToolDispatcher(adapters={"authority_media": NeverCalledAdapter()})
    result = asyncio.run(dispatcher.dispatch(ToolRequest("authority_media", {})))

    assert result.status == "failed"
    assert result.error_type == "BudgetApprovalRequired"
    assert result.evidence_state == "BLOCKED"


def test_live_tools_return_missing_when_credentials_are_absent(monkeypatch):
    monkeypatch.delenv("GOOGLE_PAGESPEED_API_KEY", raising=False)

    dispatcher = ToolDispatcher(adapters={"google_pagespeed_live": NeverCalledAdapter()})
    result = asyncio.run(
        dispatcher.dispatch(ToolRequest("google_pagespeed_live", {"url": "https://example.com/"}))
    )

    assert result.status == "unavailable"
    assert result.error_type == "MissingCredential"
    assert result.evidence_state == "MISSING"


def test_unsafe_target_urls_are_rejected_before_adapter_calls(monkeypatch):
    monkeypatch.setenv("GOOGLE_PAGESPEED_API_KEY", "fixture-key")

    dispatcher = ToolDispatcher(adapters={"google_pagespeed_live": NeverCalledAdapter()})
    result = asyncio.run(
        dispatcher.dispatch(
            ToolRequest(
                "google_pagespeed_live",
                {"url": "http://127.0.0.1/internal?token=secret"},
                required=True,
            )
        )
    )

    assert result.status == "failed"
    assert result.error_type == "UnsafeURL"
    assert result.evidence_state == "BLOCKED"


def test_free_export_adapter_can_dispatch_without_budget_or_credentials():
    dispatcher = ToolDispatcher(adapters={"crawler_csv": OkAdapter()})
    result = asyncio.run(dispatcher.dispatch(ToolRequest("crawler_csv", {"path": "crawl.csv"})))

    assert result.status == "ok"
    assert result.data["called"] is True


def test_access_requirement_registry_exposes_cost_and_credential_metadata():
    assert TOOL_ACCESS_REQUIREMENTS["authority_media"].requires_budget_approval is True
    assert "GOOGLE_PAGESPEED_API_KEY" in TOOL_ACCESS_REQUIREMENTS["google_pagespeed_live"].credential_env
