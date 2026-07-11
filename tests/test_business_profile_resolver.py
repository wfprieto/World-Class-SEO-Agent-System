from __future__ import annotations

from pathlib import Path

from runtime.business_profile_resolver import resolve_business_profile
from runtime.orchestrator import SEOOrchestrator
from runtime.workflow_graph import build_workflow_graph


ROOT = Path(__file__).resolve().parents[1]


def test_explicit_hybrid_profile_override_wins():
    result = resolve_business_profile(
        explicit_business_type="ecommerce local-service",
        signals=["no_purchase_path", "no_verifiable_presence"],
    )
    assert result.route == "HYBRID"
    assert result.confidence == "High"
    assert result.profiles == ("ecommerce", "local-service")
    assert result.user_override == result.profiles


def test_strong_and_supporting_signals_use_documented_scoring_model():
    result = resolve_business_profile(
        signals=["cart", "checkout", "shipping_returns"],
    )
    assert result.scores["ecommerce"] == 7
    assert result.profiles == ("ecommerce",)
    assert result.route == "SINGLE"


def test_two_qualified_profiles_produce_declared_hybrid():
    result = resolve_business_profile(
        signals=["cart", "checkout", "verified_nap", "service_area"],
    )
    assert result.route == "HYBRID"
    assert set(result.profiles) == {"ecommerce", "local-service"}


def test_low_confidence_evidence_returns_generic_and_clarification_action():
    result = resolve_business_profile(signals=["blog", "map_embed"])
    assert result.route == "UNCONFIRMED"
    assert result.profiles == ("generic",)
    assert result.confidence == "Low"
    assert result.missing_evidence


def test_profile_signal_resolution_changes_full_audit_specialist_graph():
    orchestrator = SEOOrchestrator(ROOT)
    session = orchestrator.start_session(
        request="Run a complete SEO audit",
        mode="Audit",
        domain="https://example.com",
        business_type="unknown",
        profile_signals=["cart", "checkout", "verified_nap", "service_area"],
    )
    graph = build_workflow_graph(orchestrator.route(session), session)
    agents = {node.agent for node in graph.nodes}
    assert session.business_profile_resolution["route"] == "HYBRID"
    assert "SEO E-commerce Agent" in agents
    assert "Local SEO Agent" in agents
