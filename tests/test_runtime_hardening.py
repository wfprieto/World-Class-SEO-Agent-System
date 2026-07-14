from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from adapters.base import AdapterResult
from runtime.orchestrator import SEOOrchestrator
from runtime.safe_paths import UnsafeRepositoryPath, resolve_repository_path
from runtime.tools import ToolDispatcher, ToolRequest


class GoodAdapter:
    def fetch(self, **kwargs):
        return AdapterResult(source="good", status="ok", data=kwargs, warnings=[])


class ExplodingAdapter:
    def fetch(self, **kwargs):
        raise KeyError("secret-shaped internal detail")


class SlowAdapter:
    def fetch(self, **kwargs):
        time.sleep(0.25)
        return AdapterResult(source="slow", status="ok", data={}, warnings=[])


class BadResultAdapter:
    def fetch(self, **kwargs):
        return {"status": "ok"}


def test_repository_path_rejects_escape_and_absolute_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "safe.md").write_text("safe", encoding="utf-8")

    assert resolve_repository_path(root, "safe.md") == (root / "safe.md").resolve()
    with pytest.raises(UnsafeRepositoryPath):
        resolve_repository_path(root, "../outside.md", must_exist=False)
    with pytest.raises(UnsafeRepositoryPath):
        resolve_repository_path(root, str((tmp_path / "outside.md").resolve()), must_exist=False)
    with pytest.raises(UnsafeRepositoryPath):
        resolve_repository_path(root, "safe.md", allowed_suffixes={".json"})


def test_orchestrator_load_artifact_is_contained(tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text("ok", encoding="utf-8")
    orchestrator = SEOOrchestrator(tmp_path)
    assert orchestrator.load_artifact("doc.md") == "ok"
    with pytest.raises(UnsafeRepositoryPath):
        orchestrator.load_artifact("../outside.md")


@pytest.mark.asyncio
async def test_dispatch_many_isolates_unexpected_adapter_failure() -> None:
    dispatcher = ToolDispatcher({"good": GoodAdapter(), "bad": ExplodingAdapter()})
    results = await dispatcher.dispatch_many(
        [ToolRequest("bad", {}), ToolRequest("good", {"value": 3})]
    )
    assert results[0].status == "failed"
    assert results[0].error_type == "InternalAdapterError"
    assert results[0].evidence_state == "INVALID"
    assert results[1].status == "ok"
    assert results[1].data == {"value": 3}


@pytest.mark.asyncio
async def test_dispatch_enforces_timeout() -> None:
    dispatcher = ToolDispatcher({"slow": SlowAdapter()}, default_timeout_seconds=0.1)
    result = await dispatcher.dispatch(ToolRequest("slow", {}))
    assert result.status == "failed"
    assert result.error_type == "ToolTimeout"
    assert result.evidence_state == "INVALID"


@pytest.mark.asyncio
async def test_dispatch_rejects_malformed_adapter_result() -> None:
    dispatcher = ToolDispatcher({"bad": BadResultAdapter()})
    result = await dispatcher.dispatch(ToolRequest("bad", {}, required=True))
    assert result.status == "failed"
    assert result.error_type == "InternalAdapterError"
    assert result.evidence_state == "BLOCKED"


@pytest.mark.asyncio
async def test_sync_orchestrator_facade_rejects_running_loop(tmp_path: Path) -> None:
    orchestrator = SEOOrchestrator(tmp_path)
    session = orchestrator.start_session("audit", "audit")
    with pytest.raises(RuntimeError, match="execute_async"):
        orchestrator.execute(session)
    await asyncio.sleep(0)
