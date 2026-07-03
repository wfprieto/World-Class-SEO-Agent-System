from __future__ import annotations

from pathlib import Path

from adapters.crawler_csv import CrawlerCSVAdapter
from runtime.orchestrator import SEOOrchestrator


def test_mock_end_to_end_diagnostic_flow(tmp_path: Path):
    crawl = tmp_path / "crawl.csv"
    crawl.write_text("Address,Status Code\nhttps://example.com,200\nhttps://example.com/old,301\n", encoding="utf-8")

    orchestrator = SEOOrchestrator(Path(__file__).resolve().parents[1])
    session = orchestrator.start_session(
        request="Set up SEO diagnostic tools and reporting dashboard",
        mode="Audit",
        domain="https://example.com",
        business_type="Local business",
        markets=["US"],
        goals=["improve local leads"],
    )
    route = orchestrator.route(session)
    crawl_result = CrawlerCSVAdapter().fetch(str(crawl))

    assert route.lead_agent == "SEO Diagnostic Infrastructure Agent"
    assert crawl_result.data["status_counts"]["301"] == 1
    assert session.business_context.domain == "https://example.com"

