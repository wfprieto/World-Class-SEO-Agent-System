"""Ignored client metadata must remain compatible across content boundaries."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import asdict
from typing import Any

import pytest

from integrations.content_intelligence.adapters import ContentIntelligenceAdapter
from runtime.tools import ToolDispatcher, ToolRequest
from seoctl.composition import build_content_service

CASES: dict[str, dict[str, Any]] = {
    "quality": {"text": "A controlled guide explains the implementation and its limits."},
    "verify": {"claims": [], "sources": []},
    "decay": {
        "prior": {
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "metrics": {"clicks": 100},
        },
        "current": {
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "metrics": {"clicks": 100},
        },
    },
}


def _invoke(boundary: str, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
    service = build_content_service()
    if boundary == "service":
        return asdict(getattr(service, operation)(**arguments))
    adapter = ContentIntelligenceAdapter(service)
    if boundary == "adapter":
        return asdict(adapter.fetch(operation, **arguments))
    dispatcher = ToolDispatcher({"content_intelligence": adapter})
    request = ToolRequest(
        tool="content_intelligence",
        arguments={"operation": operation, **arguments},
        required=True,
    )
    return asyncio.run(dispatcher.dispatch(request)).to_dict()


@pytest.mark.parametrize("boundary", ["service", "adapter", "dispatcher"])
@pytest.mark.parametrize("operation", CASES)
def test_ignored_name_metadata_keeps_all_content_results(
    boundary: str, operation: str,
) -> None:
    arguments = copy.deepcopy(CASES[operation])
    expected = _invoke(boundary, operation, arguments)
    assert expected["status"] in {"ok", "needs-review"}, "the metadata-free control must execute"
    extra = {**copy.deepcopy(arguments), "name": "synthetic-client-metadata", "unused": {"x": 1}}
    actual = _invoke(boundary, operation, extra)
    assert actual == expected, "ignored metadata must not crash, leak, or change analysis/evidence"
