from __future__ import annotations

from pathlib import Path

from runtime.orchestrator import SEOOrchestrator
from runtime.routing import RequestRouter


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

