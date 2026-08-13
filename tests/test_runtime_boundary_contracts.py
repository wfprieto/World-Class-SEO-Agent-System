from __future__ import annotations

import ast
import asyncio
import threading
from pathlib import Path
from typing import Any

import pytest

from adapters.base import AdapterResult as CompatibilityAdapterResult
from adapters.url_safety import validate_public_url as compatibility_validate_public_url
from contracts.adapter import AdapterResult as CanonicalAdapterResult
from runtime.adapter_contracts import (
    CANONICAL_ADAPTER_STATUSES,
    AdapterResult,
    validate_adapter_result,
)
from runtime.tools import REQUIRED_TOOL_FAILURE_STATES, ToolDispatcher, ToolRequest
from security.url_safety import validate_public_url as canonical_validate_public_url

ROOT = Path(__file__).resolve().parents[1]


class _ReturningAdapter:
    def __init__(self, value: object) -> None:
        self.value = value

    def fetch(self, **kwargs: Any) -> Any:
        return self.value


class _ThreadBackedSideEffectAdapter:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()
        self.completed = threading.Event()

    def fetch(self, **kwargs: Any) -> AdapterResult:
        self.started.set()
        self.release.wait(timeout=2)
        self.completed.set()
        return AdapterResult("fixture", "ok", {"side_effect": "complete"}, [])


def test_adapter_result_has_one_canonical_runtime_identity() -> None:
    assert CanonicalAdapterResult is AdapterResult
    assert CompatibilityAdapterResult is CanonicalAdapterResult


def test_url_safety_facade_preserves_canonical_policy_identity() -> None:
    assert compatibility_validate_public_url is canonical_validate_public_url


def test_integrations_do_not_import_the_adapter_compatibility_facade() -> None:
    offenders = []
    for path in sorted((ROOT / "integrations").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ImportFrom) and node.module == "adapters.base"
            for node in ast.walk(tree)
        ):
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


def test_integrations_do_not_import_the_url_safety_compatibility_facade() -> None:
    offenders = []
    for path in sorted((ROOT / "integrations").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ImportFrom) and node.module == "adapters.url_safety"
            for node in ast.walk(tree)
        ):
            offenders.append(path.relative_to(ROOT).as_posix())

    assert offenders == []


@pytest.mark.parametrize(
    "result,error",
    [
        (object(), "must return AdapterResult"),
        (AdapterResult("", "ok", {}, []), "source must be"),
        (AdapterResult("fixture", "", {}, []), "status must be"),
        (AdapterResult("fixture", "banana", {}, []), "unsupported adapter result status"),
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


@pytest.mark.asyncio
async def test_thread_timeout_reports_indeterminate_side_effect_outcome() -> None:
    adapter = _ThreadBackedSideEffectAdapter()
    dispatcher = ToolDispatcher({"side-effect": adapter})
    result = await dispatcher.dispatch(
        ToolRequest("side-effect", {}, required=True, timeout_seconds=0.1)
    )
    assert adapter.started.is_set()
    assert not adapter.completed.is_set()
    assert result.error_type == "ToolDeadlineExceededWorkMayContinue"
    assert result.evidence_state == "BLOCKED"
    assert "may still be running" in (result.sanitized_error or "")
    adapter.release.set()
    assert await asyncio.to_thread(adapter.completed.wait, 1)


def test_canonical_status_vocabulary_covers_success_partial_and_failure_states() -> None:
    expected = {
        "ok",
        "complete",
        "success",
        "needs-review",
        "partial",
        "empty",
        "not_found",
        "not_configured",
        "invalid",
        "invalid_response",
        "blocked",
        "failed",
        "unauthorized",
        "rate_limited",
    }
    assert expected == CANONICAL_ADAPTER_STATUSES


def test_required_unknown_status_is_blocked_before_workflow() -> None:
    dispatcher = ToolDispatcher(
        {"bad": _ReturningAdapter(AdapterResult("fixture", "banana", {}, []))}
    )

    result = asyncio.run(dispatcher.dispatch(ToolRequest("bad", {}, required=True)))

    assert result.status == "failed"
    assert result.error_type == "InternalAdapterError"
    assert result.evidence_state == "BLOCKED"
    assert result.evidence_state in REQUIRED_TOOL_FAILURE_STATES


@pytest.mark.parametrize(
    "status,expected_state",
    [
        ("partial", "BLOCKED"),
        ("needs-review", "BLOCKED"),
        ("empty", "MISSING"),
        ("invalid_response", "INVALID"),
        ("unauthorized", "BLOCKED"),
    ],
)
def test_required_non_success_statuses_fail_closed(
    status: str, expected_state: str
) -> None:
    dispatcher = ToolDispatcher(
        {"bounded": _ReturningAdapter(AdapterResult("fixture", status, {}, []))}
    )

    result = asyncio.run(
        dispatcher.dispatch(ToolRequest("bounded", {}, required=True))
    )

    assert result.evidence_state == expected_state
    assert result.evidence_state in REQUIRED_TOOL_FAILURE_STATES


@pytest.mark.parametrize(
    "status,expected_state",
    [("partial", "PARTIAL"), ("failed", "INVALID")],
)
def test_optional_known_non_success_statuses_remain_isolated(
    status: str, expected_state: str
) -> None:
    dispatcher = ToolDispatcher(
        {"bounded": _ReturningAdapter(AdapterResult("fixture", status, {}, []))}
    )

    result = asyncio.run(dispatcher.dispatch(ToolRequest("bounded", {}, required=False)))

    assert result.status == status
    assert result.evidence_state == expected_state
    assert result.required is False


def test_optional_unknown_status_isolated_without_erasing_sibling() -> None:
    dispatcher = ToolDispatcher(
        {
            "bad": _ReturningAdapter(AdapterResult("fixture", "banana", {}, [])),
            "good": _ReturningAdapter(AdapterResult("fixture", "ok", {"value": 1}, [])),
        }
    )

    results = asyncio.run(
        dispatcher.dispatch_many(
            [ToolRequest("bad", {}, required=False), ToolRequest("good", {})]
        )
    )

    assert results[0].status == "failed"
    assert results[0].evidence_state == "INVALID"
    assert results[1].status == "ok"
    assert results[1].data == {"value": 1}


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
