"""Execution state cannot confer trusted offline provenance on model output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.execution_limits import ExecutionLimits
from runtime.llm import EchoLLMClient, LLMMessage, LLMResponse
from runtime.orchestrator import SEOOrchestrator
from runtime.run_budget import RunBudget
from runtime.structured_output import StructuredOutputService
from runtime.workflow_graph import WorkflowGraph, WorkflowNode
from runtime.workflow_run_support import node_result_state
from scripts.validate_quality_ratchets import measure

ROOT = Path(__file__).resolve().parents[1]
AGENT = "SEO Output Report Agent"


def test_structured_completion_preserves_frozen_quality_limits():
    _, functions = measure(ROOT)
    metrics = functions["runtime.structured_output::StructuredOutputService.complete_agent_output"]
    assert metrics["span"] <= 85
    assert metrics["complexity"] <= 9


def _output(state: str) -> dict:
    return {
        "contract_version": "2.0.0",
        "output_id": "state-security-output",
        "agent": AGENT,
        "summary": "Observed 9000 visits at https://example.test/unbound.",
        "evidence": [{
            "id": "supplied-evidence",
            "source": "supplied-export",
            "type": "test_fixture",
            "date_checked": "2026-10-30",
            "notes": "Supplied evidence identity, not proof of the unbound claim.",
            "state": "CURRENT",
        }],
        "confidence": "Low",
        "findings": [{
            "id": "unbound-finding",
            "severity": "High",
            "finding": "Observed 9000 visits at https://example.test/unbound.",
            "affected_scope": "supplied-site",
            "evidence_refs": ["supplied-evidence"],
        }],
        "recommended_actions": [],
        "impact": "Unbound claims must not become accepted live evidence.",
        "effort": "Low",
        "risks": [],
        "owner": AGENT,
        "dependencies": [],
        "acceptance_criteria": ["Execution state remains truthful."],
        "verification": ["Validate the supplied evidence."],
        "follow_up": "Before implementation.",
        "material_claims": [],
        "execution_state": state,
    }


def _safe_output(state: str) -> dict:
    output = _output(state)
    output["summary"] = "Supplied observations require review."
    output["findings"][0]["finding"] = "A supplied observation requires review."
    return output


class SuppliedModelClient:
    provider = "supplied-model"
    model = "state-security-fixture"

    def __init__(self, outputs: list[dict]) -> None:
        self.outputs = outputs
        self.calls = 0

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        output = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        return LLMResponse(
            provider=self.provider,
            model=self.model,
            content=json.dumps(output),
            raw={"fixture": True},
        )

    async def stream(self, messages: list[LLMMessage]):
        yield (await self.complete(messages)).content


async def _complete(client, *, corrections: int = 0, max_calls: int = 2):
    return await StructuredOutputService(ROOT).complete_agent_output(
        client,
        [],
        agent_name=AGENT,
        request="Review supplied evidence.",
        domain="example.test",
        skills=[],
        knowledge=[],
        prior_outputs=[],
        required_handoffs=[],
        budget=RunBudget(ExecutionLimits(
            max_llm_calls=max_calls,
            max_correction_attempts=corrections,
        )),
    )


@pytest.mark.asyncio
async def test_live_synthetic_with_unbound_claims_is_rejected():
    client = SuppliedModelClient([_output("SYNTHETIC")])
    result = await _complete(client)

    assert result.status == "failed"
    assert result.output is None
    assert result.synthetic is False
    assert any("SYNTHETIC" in error for error in result.errors)
    assert result.response is not None
    assert result.response.provider == client.provider
    assert result.attempts == client.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["COMPLETE", "PARTIAL", "BLOCKED", "FAILED"])
async def test_legitimate_live_states_are_preserved(state):
    client = SuppliedModelClient([_safe_output(state)])
    result = await _complete(client)

    assert result.status == "ok"
    assert result.output is not None
    assert result.output["execution_state"] == state
    assert node_result_state(result.status, result.synthetic, result.output) == state
    assert result.synthetic is False
    assert result.response is not None
    assert result.response.provider == client.provider


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [None, "DONE"])
async def test_invalid_or_missing_live_state_is_not_accepted(state):
    output = _safe_output("COMPLETE")
    if state is None:
        output.pop("execution_state")
    else:
        output["execution_state"] = state
    result = await _complete(SuppliedModelClient([output]))

    assert result.status == "failed"
    assert result.output is None
    assert result.synthetic is False
    assert any("execution_state" in error for error in result.errors)


@pytest.mark.parametrize("declared", [None, "", "DONE", "SYNTHETIC", [], {}, False, 1])
def test_untrusted_or_invalid_node_state_fails_closed(declared):
    assert node_result_state("ok", False, {"execution_state": declared}) == "FAILED"


@pytest.mark.parametrize("output", [None, {}])
@pytest.mark.parametrize("synthetic", [False, True])
def test_missing_node_state_fails_closed(output, synthetic):
    assert node_result_state("ok", synthetic, output) == "FAILED"


def test_synthetic_provenance_must_agree_with_declared_state():
    assert node_result_state("ok", True, {"execution_state": "SYNTHETIC"}) == "SYNTHETIC"
    assert node_result_state("ok", True, {"execution_state": "COMPLETE"}) == "FAILED"
    assert node_result_state("failed", True, {"execution_state": "SYNTHETIC"}) == "FAILED"
    assert node_result_state("blocked", False, {"execution_state": "COMPLETE"}) == "BLOCKED"


@pytest.mark.asyncio
async def test_live_synthetic_rejection_uses_one_bounded_correction():
    client = SuppliedModelClient([_output("SYNTHETIC"), _safe_output("COMPLETE")])
    result = await _complete(client, corrections=1)

    assert result.status == "ok"
    assert result.output is not None
    assert result.output["execution_state"] == "COMPLETE"
    assert "9000" not in json.dumps(result.output)
    assert result.synthetic is False
    assert result.attempts == client.calls == 2


@pytest.mark.asyncio
async def test_repeated_live_synthetic_cannot_exceed_correction_budget():
    client = SuppliedModelClient([_output("SYNTHETIC")])
    result = await _complete(client, corrections=1)

    assert result.status == "failed"
    assert result.output is None
    assert result.synthetic is False
    assert result.attempts == client.calls == 2
    assert any("SYNTHETIC" in error for error in result.errors)


@pytest.mark.asyncio
async def test_live_synthetic_correction_cannot_exceed_call_budget():
    client = SuppliedModelClient([_output("SYNTHETIC")])
    result = await _complete(client, corrections=1, max_calls=1)

    assert result.status == "blocked"
    assert result.output is None
    assert result.synthetic is False
    assert result.attempts == client.calls == 1
    assert any("max_llm_calls" in error for error in result.errors)


@pytest.mark.asyncio
async def test_trusted_echo_preserves_synthetic_provenance_without_model_calls():
    result = await _complete(EchoLLMClient())

    assert result.status == "ok"
    assert result.output is not None
    assert result.output["execution_state"] == "SYNTHETIC"
    assert result.synthetic is True
    assert result.response is None
    assert result.attempts == 0
    assert node_result_state(result.status, result.synthetic, result.output) == "SYNTHETIC"


def _two_node_workflow(monkeypatch, client):
    graph = WorkflowGraph(
        id="state-security-workflow",
        nodes=[
            WorkflowNode(id="source", agent=AGENT),
            WorkflowNode(
                id="deliverable",
                agent="SEO Full Audit/Analyst Agent",
                depends_on=("source",),
            ),
        ],
        deliverable_node_id="deliverable",
    )
    monkeypatch.setattr("runtime.workflow_runner.build_workflow_graph", lambda *_: graph)
    orchestrator = SEOOrchestrator(ROOT, llm_client=client)
    session = orchestrator.start_session(
        request="Review supplied evidence.", mode="Audit", domain="example.test"
    )
    return orchestrator.execute(
        session,
        orchestrator.route(session),
        limits=ExecutionLimits(
            max_nodes=2,
            max_llm_calls=2,
            max_parallel_agents=1,
            max_correction_attempts=0,
            max_workflow_depth=2,
            max_runtime_seconds=60,
        ),
    )


def test_live_synthetic_cannot_unlock_workflow_or_enter_accepted_evidence(monkeypatch):
    client = SuppliedModelClient([_output("SYNTHETIC")])
    result = _two_node_workflow(monkeypatch, client)

    assert client.calls == 1
    assert result["node_states"] == {"source": "FAILED", "deliverable": "BLOCKED"}
    assert result["workflow_status"] == "FAILED"
    assert result["agent_output"] is None
    assert result["agent_outputs"] == []
    assert result["normalized_findings"] == []
    assert result["decisions"] == []
    assert result["llm"]["provider"] == client.provider
    assert result["llm"]["synthetic"] is False
    assert "unbound-finding" not in json.dumps(result)
    assert "9000" not in json.dumps(result)


@pytest.mark.parametrize("state", ["PARTIAL", "BLOCKED", "FAILED"])
def test_noncomplete_live_work_cannot_unlock_dependents(monkeypatch, state):
    client = SuppliedModelClient([_safe_output(state)])
    result = _two_node_workflow(monkeypatch, client)

    assert client.calls == 1
    assert result["node_states"] == {"source": state, "deliverable": "BLOCKED"}
    assert result["workflow_status"] == "FAILED"
    assert result["agent_output"] is None
    assert result["agent_outputs"] == []
    assert result["normalized_findings"] == []
    assert result["decisions"] == []
    assert result["llm"]["synthetic"] is False


def test_trusted_echo_workflow_still_progresses_and_finishes_partial(monkeypatch):
    result = _two_node_workflow(monkeypatch, EchoLLMClient())

    assert result["node_states"] == {"source": "SYNTHETIC", "deliverable": "SYNTHETIC"}
    assert result["workflow_status"] == "PARTIAL"
    assert result["agent_output"]["execution_state"] == "SYNTHETIC"
    assert len(result["agent_outputs"]) == 2
    assert result["llm"]["provider"] == "echo"
    assert result["llm"]["synthetic"] is True
    assert result["llm"]["calls"] == 0
