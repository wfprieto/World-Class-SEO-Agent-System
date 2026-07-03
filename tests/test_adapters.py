from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.accessibility_checker import AccessibilityCheckerAdapter
from adapters.ai_citation_monitor import AICitationMonitorAdapter
from adapters.backlinks import BacklinkCSVAdapter
from adapters.crux import CrUXPayloadAdapter
from adapters.crawler_csv import CrawlerCSVAdapter
from adapters.ga4 import GA4ExportAdapter
from adapters.gbp_local import GBPLocalAdapter
from adapters.gsc import GSCExportAdapter
from adapters.gsc_live_example import GSCLiveExampleAdapter
from adapters.hreflang_validator import HreflangValidatorAdapter
from adapters.knowledge_graph import KnowledgeGraphAdapter
from adapters.log_parser import LogParserAdapter
from adapters.pagespeed import PageSpeedPayloadAdapter
from adapters.rank_tracking import RankTrackingCSVAdapter
from adapters.redirect_chain import RedirectChainAdapter
from adapters.registry import default_adapters
from adapters.robots_txt import RobotsTxtAdapter
from adapters.schema_validation import SchemaValidationAdapter
from adapters.sitemap_validator import SitemapValidatorAdapter
from adapters.base import AdapterNotConfigured


def test_schema_validation_adapter_flags_missing_type():
    result = SchemaValidationAdapter().fetch({"@context": "https://schema.org"})
    assert result.status == "needs-review"
    assert "Missing @type." in result.warnings


def test_crawler_csv_adapter_parses_status_counts(tmp_path: Path):
    path = tmp_path / "crawl.csv"
    path.write_text("Address,Status Code\nhttps://example.com,200\nhttps://example.com/missing,404\n", encoding="utf-8")
    result = CrawlerCSVAdapter().fetch(str(path))
    assert result.status == "ok"
    assert result.data["row_count"] == 2
    assert result.data["status_counts"]["200"] == 1
    assert result.data["status_counts"]["404"] == 1


def test_gsc_export_adapter_sums_search_metrics(tmp_path: Path):
    path = tmp_path / "gsc.csv"
    path.write_text("page,query,clicks,impressions\n/a,alpha,3,30\n/b,beta,7,70\n", encoding="utf-8")
    result = GSCExportAdapter().fetch(str(path))
    assert result.data["clicks"] == 10
    assert result.data["impressions"] == 100


def test_ga4_export_adapter_sums_sessions_and_conversions(tmp_path: Path):
    path = tmp_path / "ga4.csv"
    path.write_text("landing_page,sessions,conversions\n/a,10,1\n/b,20,2\n", encoding="utf-8")
    result = GA4ExportAdapter().fetch(str(path))
    assert result.data["sessions"] == 30
    assert result.data["conversions"] == 3


def test_backlink_adapter_counts_domains_and_anchors(tmp_path: Path):
    path = tmp_path / "links.csv"
    path.write_text("referring_domain,anchor\nexample.com,brand\nexample.com,brand\nsite.test,pricing\n", encoding="utf-8")
    result = BacklinkCSVAdapter().fetch(str(path))
    assert result.data["backlink_count"] == 3
    assert result.data["referring_domain_count"] == 2
    assert result.data["top_anchors"]["brand"] == 2


def test_log_parser_counts_search_bots(tmp_path: Path):
    path = tmp_path / "access.log"
    path.write_text("GET / Googlebot\nGET / Bingbot\nGET / human\n", encoding="utf-8")
    result = LogParserAdapter().fetch(str(path))
    assert result.data["bot_hits"]["googlebot"] == 1
    assert result.data["bot_hits"]["bingbot"] == 1


def test_pagespeed_payload_adapter_extracts_scores(tmp_path: Path):
    path = tmp_path / "psi.json"
    payload = {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.91}, "accessibility": {"score": 0.88}, "seo": {"score": 1}},
            "audits": {"largest-contentful-paint": {"displayValue": "1.8 s"}, "cumulative-layout-shift": {"displayValue": "0.01"}},
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = PageSpeedPayloadAdapter().fetch(str(path))
    assert result.data["performance_score"] == 91
    assert result.data["lcp"] == "1.8 s"


def test_rank_tracking_adapter_calculates_average_rank(tmp_path: Path):
    path = tmp_path / "ranks.csv"
    path.write_text("keyword,rank\nalpha,2\nbeta,12\n", encoding="utf-8")
    result = RankTrackingCSVAdapter().fetch(str(path))
    assert result.data["average_rank"] == 7
    assert result.data["top_10_count"] == 1


def test_crux_payload_adapter_extracts_cwv_metrics(tmp_path: Path):
    path = tmp_path / "crux.json"
    payload = {"record": {"metrics": {"largest_contentful_paint": {"percentiles": {"p75": 2200}}, "interaction_to_next_paint": {"percentiles": {"p75": 180}}, "cumulative_layout_shift": {"percentiles": {"p75": 0.04}}}}}
    path.write_text(json.dumps(payload), encoding="utf-8")
    result = CrUXPayloadAdapter().fetch(path=str(path))
    assert result.data["lcp"] == 2200
    assert result.data["inp"] == 180
    assert result.data["cls"] == 0.04


def test_hreflang_validator_flags_missing_return(tmp_path: Path):
    path = tmp_path / "hreflang.csv"
    path.write_text("source,target,hreflang\n/en,/es,es\n/en,/fr,fr\n/es,/en,en\n", encoding="utf-8")
    result = HreflangValidatorAdapter().fetch(str(path))
    assert result.status == "needs-review"
    assert len(result.data["missing_return"]) == 1


def test_sitemap_validator_counts_urls_and_duplicates(tmp_path: Path):
    path = tmp_path / "sitemap.xml"
    path.write_text("<urlset><url><loc>https://example.com/a</loc></url><url><loc>https://example.com/a</loc></url></urlset>", encoding="utf-8")
    result = SitemapValidatorAdapter().fetch(path=str(path))
    assert result.data["url_count"] == 2
    assert result.status == "needs-review"


def test_accessibility_checker_flags_missing_alt():
    html = "<html><body><h1>Title</h1><img src='a.jpg'><img src='b.jpg' alt='Product'></body></html>"
    result = AccessibilityCheckerAdapter().fetch(html=html)
    assert result.data["missing_alt_count"] == 1
    assert result.status == "needs-review"


def test_gbp_local_adapter_flags_missing_nap(tmp_path: Path):
    path = tmp_path / "gbp.csv"
    path.write_text("name,address,phone\nMain Location,1 Main St,555-0100\nSecond Location,,555-0101\n", encoding="utf-8")
    result = GBPLocalAdapter().fetch(str(path))
    assert result.data["missing_nap_count"] == 1


def test_redirect_chain_adapter_flags_chains_and_loops(tmp_path: Path):
    path = tmp_path / "redirects.csv"
    path.write_text("source,target,hops\n/a,/b,2\n/c,/c,1\n", encoding="utf-8")
    result = RedirectChainAdapter().fetch(str(path))
    assert result.data["chain_count"] == 1
    assert result.data["loop_count"] == 1


def test_ai_citation_monitor_counts_citations(tmp_path: Path):
    path = tmp_path / "ai.csv"
    path.write_text("prompt,brand,cited\nbest provider,Example,true\ncomparison,Competitor,false\n", encoding="utf-8")
    result = AICitationMonitorAdapter().fetch(str(path))
    assert result.data["citation_count"] == 1
    assert result.data["cited_brands"] == ["Example"]


def test_knowledge_graph_adapter_flags_missing_sameas():
    result = KnowledgeGraphAdapter().fetch(entity={"name": "Example", "url": "https://example.com"})
    assert result.status == "needs-review"
    assert "Missing entity field: sameAs" in result.warnings


def test_robots_txt_adapter_flags_disallow_all_without_sitemap():
    result = RobotsTxtAdapter().fetch(text="User-agent: *\nDisallow: /\n")
    assert result.data["disallow_all"] is True
    assert result.status == "needs-review"


def test_gsc_live_example_requires_oauth_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GSC_CLIENT_ID", raising=False)
    monkeypatch.delenv("GSC_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("GSC_REFRESH_TOKEN", raising=False)
    with pytest.raises(AdapterNotConfigured):
        GSCLiveExampleAdapter().fetch("https://example.com/")


def test_default_registry_includes_all_adapter_keys():
    adapters = default_adapters()
    expected = {
        "accessibility_checker",
        "ai_citation_monitor",
        "backlink_csv",
        "crux_payload",
        "crawler_csv",
        "ga4_export",
        "gbp_local",
        "gsc_export",
        "hreflang_validator",
        "knowledge_graph",
        "log_parser",
        "pagespeed_payload",
        "rank_tracking_csv",
        "redirect_chain",
        "robots_txt",
        "schema_validation",
        "sitemap_validator",
    }
    assert expected.issubset(adapters.keys())
