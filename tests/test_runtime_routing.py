from __future__ import annotations

import asyncio
from pathlib import Path

from runtime.memory import InMemoryStore
from runtime.orchestrator import SEOOrchestrator
from runtime.routing import RequestRouter
from runtime.tools import ToolRequest


def test_routes_diagnostic_setup_to_infrastructure_agent():
    result = RequestRouter().route("Set up SEO diagnostic tools and reporting dashboard")
    assert result.lead_agent == "SEO Diagnostic Infrastructure Agent"


def test_routes_plain_language_report_to_output_agent():
    result = RequestRouter().route("Create a non-technical stakeholder summary")
    assert result.lead_agent == "SEO Output Report Agent"


def test_orchestrator_creates_session_and_route():
    orchestrator = SEOOrchestrator(Path(__file__).resolve().parents[1])
    session = orchestrator.start_session(
        request="Run a full SEO audit",
        mode="Audit",
        domain="https://example.com",
        business_type="SaaS",
        markets=["US"],
        goals=["increase demos"],
    )
    result = orchestrator.route(session)
    assert result.lead_agent == "SEO Full Audit/Analyst Agent"
    assert session.agent_outputs


def test_orchestrator_executes_with_echo_llm():
    memory = InMemoryStore()
    orchestrator = SEOOrchestrator(Path(__file__).resolve().parents[1], memory=memory)
    session = orchestrator.start_session(
        request="Run a full SEO audit",
        mode="Audit",
        domain="https://example.com",
        business_type="SaaS",
    )
    route = orchestrator.route(session)
    payload = orchestrator.execute(session, route)
    assert payload["llm"]["provider"] == "echo"
    assert payload["route"]["lead_agent"] == "SEO Full Audit/Analyst Agent"
    assert memory.load(session.session_id)


def test_orchestrator_dispatches_tool_before_llm(tmp_path):
    crawl = tmp_path / "crawl.csv"
    crawl.write_text("Address,Status Code\nhttps://example.com,200\n", encoding="utf-8")
    orchestrator = SEOOrchestrator(Path(__file__).resolve().parents[1])
    session = orchestrator.start_session("Run a technical crawl audit", "Audit", "https://example.com", "SaaS")
    route = orchestrator.route(session)
    payload = orchestrator.execute(session, route, [ToolRequest("crawler_csv", {"path": str(crawl)})])
    assert payload["tool_results"][0]["tool"] == "crawler_csv"
    assert payload["tool_results"][0]["data"]["status_counts"]["200"] == 1


def test_executor_streams_with_echo_llm():
    async def run() -> str:
        orchestrator = SEOOrchestrator(Path(__file__).resolve().parents[1])
        session = orchestrator.start_session("Create a stakeholder summary", "Audit", "https://example.com", "SaaS")
        route = orchestrator.route(session)
        chunks = []
        async for chunk in orchestrator.executor.stream(session, route):
            chunks.append(chunk)
        return "".join(chunks)

    content = asyncio.run(run())
    assert "Echo execution complete" in content
