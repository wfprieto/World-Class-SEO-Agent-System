from __future__ import annotations

import asyncio
from typing import Any

import pytest

from adapters.base import AdapterResult as CompatibilityAdapterResult
from runtime.adapter_contracts import AdapterResult, validate_adapter_result
from runtime.tools import ToolDispatcher, ToolRequest


class _ReturningAdapter:
    def __init__(self, value: object) -> None:
        self.value = value

    def fetch(self, **kwargs: Any) -> Any:
        return self.value


def test_adapter_result_has_one_canonical_runtime_identity() -> None:
    assert CompatibilityAdapterResult is AdapterResult


@pytest.mark.parametrize(
    "result,error",
    [
        (object(), "must return AdapterResult"),
        (AdapterResult("", "ok", {}, []), "source must be"),
        (AdapterResult("fixture", "", {}, []), "status must be"),
        (AdapterResult("fixture", "ok", {}, [1]), "list of strings"),
        (AdapterResult("fixture", "ok", {"bad": object()}, []), "JSON-serializable"),
        (AdapterResult("fixture", "ok", {"bad": float("nan")}, []), "JSON-serializable"),
        (
            AdapterResult("fixture", "ok", {}, ["Authorization: Bearer abc123"]),
            "credential material",
        ),
    ],
)
def test_adapter_result_validation_rejects_malformed_boundary_values(
    result: object, error: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=error):
        validate_adapter_result(result)


def test_dispatcher_isolates_malformed_boundary_result() -> None:
    dispatcher = ToolDispatcher(
        {"bad": _ReturningAdapter(AdapterResult("fixture", "ok", {"bad": object()}, []))}
    )
    result = asyncio.run(dispatcher.dispatch(ToolRequest("bad", {}, required=True)))
    assert result.status == "failed"
    assert result.error_type == "InternalAdapterError"
    assert result.evidence_state == "BLOCKED"


def test_dispatch_many_preserves_order_and_completed_sibling_evidence() -> None:
    dispatcher = ToolDispatcher(
        {
            "good": _ReturningAdapter(AdapterResult("fixture", "ok", {"value": 1}, [])),
            "bad": _ReturningAdapter(AdapterResult("fixture", "ok", {"bad": object()}, [])),
        }
    )
    results = asyncio.run(
        dispatcher.dispatch_many(
            [
                ToolRequest("good", {"order": 1}),
                ToolRequest("bad", {"order": 2}),
                ToolRequest("good", {"order": 3}),
            ]
        )
    )
    assert [item.tool for item in results] == ["good", "bad", "good"]
    assert [item.evidence_state for item in results] == ["AVAILABLE", "INVALID", "AVAILABLE"]
