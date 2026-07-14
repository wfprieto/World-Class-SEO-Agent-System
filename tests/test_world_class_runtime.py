from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from adapters.base import AdapterNotConfigured, AdapterResult
from runtime.capability_resolver import CapabilityResolver
from runtime.execution_limits import ExecutionLimits
from runtime.finding_registry import FindingRegistry
from runtime.llm import LLMMessage, LLMResponse
from runtime.memory import InMemoryStore, JsonlMemoryStore
from runtime.orchestrator import SEOOrchestrator
from runtime.schema_registry import SchemaRegistry
from runtime.tools import ToolDispatcher, ToolRequest
from runtime.workflow_graph import WorkflowGraph, WorkflowGraphError, WorkflowNode
from scripts import content_brief_evidence as cbe
from scripts import consent_mode_diagnostic as cmd
from scripts import seo_pdf_report
from scripts.validate_evidence_binding import validate_output


ROOT = Path(__file__).resolve().parents[1]
FAST_RUNTIME_LIMITS = ExecutionLimits(
    max_nodes=10,
    max_llm_calls=10,
    max_parallel_agents=2,
    max_correction_attempts=0,
    max_workflow_depth=5,
    max_runtime_seconds=60,
)


class ValidStructuredClient:
    provider = "fixture"
    model = "fixture-structured"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        self.calls += 1
        instruction = next(
            message.content for message in reversed(messages)
            if message.role == "system" and message.content.startswith("You are ")
        )
        match = re.search(r"You are '([^']+)'", instruction)
        assert match
        agent = match.group(1)
        slug = re.sub(r"[^a-z0-9]+", "-", agent.lower()).strip("-")
        payload = {
            "output_id": f"fixture-{slug}",
            "agent": agent,
            "summary": "Validated specialist output.",
            "evidence": [{
                "id": "fixture-evidence",
                "source": "fixture-evidence",
                "type": "test_fixture",
                "date_checked": "2026-07-11",
                "notes": "Deterministic fixture evidence.",
            }],
            "confidence": "High",
            "findings": [{
                "id": f"{slug}-finding",
                "severity": "Medium",
                "finding": "A validated specialist observation requires review.",
                "affected_scope": "fixture-template",
                "evidence_refs": ["fixture-evidence"],
            }],
            "recommended_actions": [{
                "action": "Review the validated observation.",
                "priority": "P2",
                "owner": agent,
                "success_metric": "The acceptance criteria are verified.",
            }],
            "impact": "Improves evidence-backed workflow quality.",
            "effort": "Low",
            "risks": ["Fixture output is not production evidence."],
            "owner": agent,
            "dependencies": [],
            "acceptance_criteria": ["Canonical schema validation passes."],
            "verification": ["Run deterministic tests."],
            "follow_up": "Before release.",
            "material_claims": [],
            "skills_used": [],
            "knowledge_used": [],
            "execution_state": "COMPLETE",
        }
        return LLMResponse(
            provider=self.provider,
            model=self.model,
            content=json.dumps(payload),
            raw={"fixture": True},
        )

    async def stream(self, messages: list[LLMMessage]):
        response = await self.complete(messages)
        yield response.content


class InvalidProseClient:
    provider = "fixture-invalid"
    model = "fixture-invalid"

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        return LLMResponse(
            provider=self.provider,
            model=self.model,
            content="This is unstructured prose, not JSON.",
            raw={},
        )

    async def stream(self, messages: list[LLMMessage]):
        yield "invalid"


class InvalidForAgentClient(ValidStructuredClient):
    provider = "fixture-partial-invalid"
    model = "fixture-partial-invalid"

    def __init__(self, invalid_agent: str) -> None:
        super().__init__()
        self.invalid_agent = invalid_agent

    async def complete(self, messages: list[LLMMessage]) -> LLMResponse:
        instruction = next(
            message.content for message in reversed(messages)
            if message.role == "system" and message.content.startswith("You are ")
        )
        match = re.search(r"You are '([^']+)'", instruction)
        assert match
        if match.group(1) == self.invalid_agent:
            self.calls += 1
            return LLMResponse(
                provider=self.provider,
                model=self.model,
                content="This deliverable agent failed to return JSON.",
                raw={"fixture": True},
            )
        return await super().complete(messages)


def _session(orchestrator: SEOOrchestrator, request: str = "Run a complete SEO audit"):
    return orchestrator.start_session(
        request=request,
        mode="Audit",
        domain="https://example.com",
        business_type="ecommerce local-service",
        markets=["US"],
        goals=["Increase qualified organic conversions"],
    )


def test_capability_registry_covers_every_runtime_agent_and_all_paths_resolve():
    resolver = CapabilityResolver(ROOT)
    report = resolver.validate()
    from runtime.executor import AGENT_FILE_NAMES

    assert report["status"] == "ok"
    assert report["agent_count"] == len(AGENT_FILE_NAMES) == 25
    assert set(resolver.registry) == set(AGENT_FILE_NAMES)


def test_full_audit_executes_specialists_governance_strategy_and_reporting():
    orchestrator = SEOOrchestrator(ROOT)
    session = _session(orchestrator)
    route = orchestrator.route(session)
    result = orchestrator.execute(session, route)

    agents = {output["agent"] for output in result["agent_outputs"]}
    assert result["execution_mode"] == "multi-agent"
    assert result["workflow_status"] == "PARTIAL"  # echo output is explicitly synthetic
    assert len(result["agent_outputs"]) >= 10
    assert "SEO Technical Agent" in agents
    assert "SEO Copywriter/Content Agent" in agents
    assert "SEO E-commerce Agent" in agents
    assert "Local SEO Agent" in agents
    assert "SEO Full Audit/Analyst Agent" in agents
    assert "SEO Scrummaster Agent" in agents
    assert "Senior SEO Strategist Agent" in agents
    assert "SEO Output Report Agent" in agents
    assert result["handoffs_created"] > 0
    assert result["handoffs_consumed"] == result["handoffs_created"]
    assert result["decisions"]
    assert all(output["execution_state"] == "SYNTHETIC" for output in result["agent_outputs"])
    SchemaRegistry(ROOT).validate("session-state", result["session"])


def test_non_audit_route_executes_support_agents_before_lead():
    orchestrator = SEOOrchestrator(ROOT)
    session = _session(orchestrator, "Build an SEO content brief")
    route = orchestrator.route(session)
    result = orchestrator.execute(session, route)

    agents = [output["agent"] for output in result["agent_outputs"]]
    assert "SEO Copywriter/Content Agent" in agents
    assert "SEO Compliance & Legal Agent" in agents
    assert "GEO / AIO Optimization Agent" in agents
    assert "SEO CRO Agent" in agents
    assert result["handoffs_consumed"] == result["handoffs_created"]


def test_dependency_handoff_requires_referenced_evidence_before_consumption():
    orchestrator = SEOOrchestrator(ROOT, llm_client=ValidStructuredClient())
    session = _session(orchestrator, "Build an SEO content brief")
    result = orchestrator.execute(
        session,
        orchestrator.route(session),
        limits=FAST_RUNTIME_LIMITS,
    )
    unconsumed = [
        handoff for handoff in result["handoffs"]
        if handoff["status"] == "CREATED"
    ]
    assert result["handoffs_created"] > 0
    assert result["handoffs_consumed"] < result["handoffs_created"]
    assert unconsumed
    assert all(handoff["evidence_refs"] for handoff in unconsumed)
    assert all(not handoff["receiving_output_id"] for handoff in unconsumed)
    assert result["workflow_status"] == "PARTIAL"


def test_workflow_graph_requires_explicit_deliverable_node():
    graph = WorkflowGraph(
        id="invalid-no-deliverable",
        nodes=[WorkflowNode(id="lead", agent="SEO Technical Agent")],
    )
    with pytest.raises(WorkflowGraphError, match="no explicit deliverable"):
        graph.validate(max_nodes=5, max_depth=5)


def test_workflow_graph_rejects_non_terminal_deliverable_node():
    graph = WorkflowGraph(
        id="invalid-non-terminal-deliverable",
        nodes=[
            WorkflowNode(id="lead", agent="SEO Technical Agent"),
            WorkflowNode(
                id="report",
                agent="SEO Output Report Agent",
                depends_on=("lead",),
            ),
        ],
        deliverable_node_id="lead",
    )
    with pytest.raises(WorkflowGraphError, match="deliverable node must be terminal"):
        graph.validate(max_nodes=5, max_depth=5)


def test_failed_deliverable_is_not_replaced_by_another_terminal_output(monkeypatch):
    graph = WorkflowGraph(
        id="two-terminal-deliverable-failure",
        nodes=[
            WorkflowNode(id="successful-terminal", agent="SEO Technical Agent"),
            WorkflowNode(id="explicit-deliverable", agent="SEO Output Report Agent"),
        ],
        deliverable_node_id="explicit-deliverable",
    )

    def fixture_graph(route, session):
        return graph

    monkeypatch.setattr("runtime.workflow_runner.build_workflow_graph", fixture_graph)
    orchestrator = SEOOrchestrator(
        ROOT,
        llm_client=InvalidForAgentClient("SEO Output Report Agent"),
    )
    session = _session(orchestrator, "Run a complete SEO audit")
    result = orchestrator.execute(
        session,
        orchestrator.route(session),
        limits=FAST_RUNTIME_LIMITS,
    )
    assert result["node_states"]["successful-terminal"] == "COMPLETE"
    assert result["node_states"]["explicit-deliverable"] == "FAILED"
    assert result["agent_output"] is None
    assert result["workflow_status"] == "FAILED"


def test_invalid_model_prose_is_failed_not_wrapped_as_success():
    orchestrator = SEOOrchestrator(ROOT, llm_client=InvalidProseClient())
    session = _session(orchestrator, "Build an SEO content brief")
    result = orchestrator.execute(
        session,
        orchestrator.route(session),
        limits=ExecutionLimits(
            max_nodes=10,
            max_llm_calls=10,
            max_parallel_agents=2,
            max_correction_attempts=1,
            max_workflow_depth=5,
            max_runtime_seconds=60,
        ),
    )
    assert result["workflow_status"] == "FAILED"
    assert any(state in {"FAILED", "BLOCKED"} for state in result["node_states"].values())
    assert not any(
        output.get("execution_state") == "COMPLETE"
        for output in result["agent_outputs"]
    )


def test_workflow_stops_before_exceeding_llm_call_budget():
    client = ValidStructuredClient()
    orchestrator = SEOOrchestrator(ROOT, llm_client=client)
    session = _session(orchestrator)
    result = orchestrator.execute(
        session,
        orchestrator.route(session),
        limits=ExecutionLimits(
            max_nodes=20,
            max_llm_calls=3,
            max_parallel_agents=3,
            max_correction_attempts=0,
            max_workflow_depth=5,
            max_runtime_seconds=60,
        ),
    )
    assert client.calls == 3
    assert result["budget"]["usage"]["llm_calls"] == 3
    assert result["workflow_status"] == "FAILED"
    assert any("max_llm_calls" in " ".join(errors) for errors in result["node_errors"].values())


class GoodAdapter:
    def fetch(self, **kwargs):
        return AdapterResult(source="good", status="ok", data={"value": "available"}, warnings=[])


class MissingAdapter:
    def fetch(self, **kwargs):
        raise AdapterNotConfigured("fixture source is not connected")


@pytest.mark.asyncio
async def test_one_adapter_failure_preserves_other_results():
    dispatcher = ToolDispatcher({"good": GoodAdapter(), "missing": MissingAdapter()})
    results = await dispatcher.dispatch_many([
        ToolRequest("good", {}),
        ToolRequest("missing", {}, required=False),
    ])
    by_tool = {result.tool: result for result in results}
    assert by_tool["good"].status == "ok"
    assert by_tool["good"].data == {"value": "available"}
    assert by_tool["missing"].status == "unavailable"
    assert by_tool["missing"].evidence_state == "MISSING"


def test_memory_recursively_redacts_secrets_and_supports_deletion(tmp_path: Path):
    store = JsonlMemoryStore(tmp_path / "memory.jsonl")
    store.append("s1", {
        "authorization": "Bearer top-secret-token",
        "nested": {"api_key": "sk-secret-value", "safe": "keep"},
        "text": "credential ghp_abcdefghijklmnopqrstuvwxyz",
    })
    blob = (tmp_path / "memory.jsonl").read_text(encoding="utf-8")
    assert "top-secret-token" not in blob
    assert "sk-secret-value" not in blob
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in blob
    assert store.load("s1")[0]["nested"]["safe"] == "keep"
    assert store.delete_session("s1") == 1
    assert store.load("s1") == []


def test_evidence_binding_rejects_unbound_numeric_and_unknown_evidence():
    output = {
        "execution_state": "COMPLETE",
        "summary": "Clicks declined 32%.",
        "impact": "",
        "follow_up": "",
        "findings": [],
        "recommended_actions": [],
        "evidence": [{"id": "gsc-1", "source": "gsc.csv"}],
        "material_claims": [],
    }
    errors = validate_output(output)
    assert any("32%" in error for error in errors)

    output["material_claims"] = [{
        "claim_id": "claim-1",
        "claim_type": "numeric",
        "statement": "Clicks declined 32%.",
        "evidence_refs": ["missing-id"],
        "evidence_state": "AVAILABLE",
        "inference": False,
    }]
    errors = validate_output(output)
    assert any("unknown evidence" in error for error in errors)


def test_finding_registry_deduplicates_same_root_cause_and_combines_evidence():
    registry = FindingRegistry()
    registry.add_output({
        "agent": "SEO Technical Agent",
        "findings": [{
            "id": "tech-1",
            "severity": "High",
            "finding": "Product pages emit an incorrect canonical.",
            "affected_scope": "product template",
            "evidence_refs": ["crawl-1"],
        }],
    })
    registry.add_output({
        "agent": "SEO E-commerce Agent",
        "findings": [{
            "id": "commerce-1",
            "severity": "Medium",
            "finding": "The product template has a canonical mismatch.",
            "affected_scope": "product template",
            "evidence_refs": ["schema-1"],
        }],
    })
    records = registry.records()
    assert len(records) == 1
    assert set(records[0]["agents"]) == {"SEO Technical Agent", "SEO E-commerce Agent"}
    assert set(records[0]["evidence_refs"]) == {"crawl-1", "schema-1"}
    assert records[0]["severity"] == "High"


def test_report_preserves_canonical_finding_scope_evidence_and_actions():
    data = {
        "agent": "SEO Technical Agent",
        "summary": "Canonical summary.",
        "evidence": [{
            "id": "crawl-1",
            "source": "crawl.csv",
            "type": "crawl_export",
            "date_checked": "2026-07-11",
            "notes": "Verified crawl evidence.",
        }],
        "confidence": "High",
        "findings": [{
            "id": "tech-1",
            "severity": "High",
            "finding": "Canonical conflict on the product template.",
            "affected_scope": "product template",
            "evidence_refs": ["crawl-1"],
        }],
        "recommended_actions": [{
            "action": "Correct canonical generation.",
            "priority": "P1",
            "owner": "Senior SEO Engineer Agent",
            "success_metric": "Rendered samples self-canonicalize.",
        }],
        "impact": "Reduces incorrect consolidation risk.",
        "effort": "Medium",
        "risks": ["Template change affects many URLs."],
        "owner": "Senior SEO Engineer Agent",
        "dependencies": ["Template access"],
        "acceptance_criteria": ["Samples self-canonicalize"],
        "verification": ["Re-crawl samples"],
        "follow_up": "After deployment.",
    }
    markup = seo_pdf_report.build_html(data)
    for expected in (
        "Canonical conflict on the product template",
        "product template",
        "crawl-1",
        "Correct canonical generation",
        "Senior SEO Engineer Agent",
        "Rendered samples self-canonicalize",
    ):
        assert expected in markup


def test_content_brief_excludes_own_domain_validates_weights_and_blocks_stale_evidence():
    capture = {
        "query": "example",
        "locale": "en-US",
        "device": "mobile",
        "date": "2026-07-11",
        "source": "fixture",
    }
    rows = [
        {"url": "https://www.example.com/own", "intent": "informational"},
        {"url": "https://competitor.example/page", "intent": "informational"},
    ]
    result = cbe.assess_serp(
        rows,
        capture,
        own_domain="example.com",
        as_of="2026-07-11",
        target_intent="informational",
    )
    assert result["own_results_excluded"] == 1
    assert result["result_count"] == 1
    with pytest.raises(ValueError, match="missing"):
        cbe.assess_serp(rows, capture, "example.com", weights={"intent_fit": 1.0})

    stale = dict(result, status="STALE_EVIDENCE", stale=True)
    decision = cbe.brief_decision(
        {"verdict": "RELEVANT"},
        stale,
        ["Original field evidence"],
    )
    assert decision["publish"] is False


def test_consent_diagnostic_uses_recursive_redaction_and_avoids_topology_false_passes():
    config = {
        "region": "ES",
        "cmp": "fixture-cmp",
        "mode": "advanced",
        "default_set": True,
        "default_before_tags": True,
        "defaults": {signal: "denied" for signal in cmd.SIGNALS},
        "update_present": True,
        "update_after_default": True,
        "environment": "production",
        "nested": {"authorization": "Bearer secret-value"},
        "spa": True,
        "server_side_tagging": True,
        "cross_domain": True,
    }
    result = cmd.diagnose(config)
    assert result["implementation_topology"]["consent_required_region"] is True
    assert "secret-value" not in json.dumps(result)
    assert result["status"] == "PARTIAL"
    assert all(
        item["classification"] == "verification_required"
        for item in result["findings"]
        if item["area"] in {"spa", "server-side", "cross-domain"}
    )
