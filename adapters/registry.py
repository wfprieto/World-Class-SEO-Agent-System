"""Adapter registry for runtime usage."""

from __future__ import annotations

from adapters.accessibility_checker import AccessibilityCheckerAdapter
from adapters.ai_citation_monitor import AICitationMonitorAdapter
from adapters.backlinks import BacklinkCSVAdapter
from adapters.crux import CrUXPayloadAdapter
from adapters.crawler_csv import CrawlerCSVAdapter
from adapters.ga4 import GA4ExportAdapter
from adapters.gsc import GSCExportAdapter
from adapters.gbp_local import GBPLocalAdapter
from adapters.hreflang_validator import HreflangValidatorAdapter
from adapters.knowledge_graph import KnowledgeGraphAdapter
from adapters.log_parser import LogParserAdapter
from adapters.pagespeed import PageSpeedPayloadAdapter
from adapters.rank_tracking import RankTrackingCSVAdapter
from adapters.redirect_chain import RedirectChainAdapter
from adapters.robots_txt import RobotsTxtAdapter
from adapters.schema_validation import SchemaValidationAdapter
from adapters.sitemap_validator import SitemapValidatorAdapter


def default_adapters() -> dict[str, object]:
    return {
        "accessibility_checker": AccessibilityCheckerAdapter(),
        "ai_citation_monitor": AICitationMonitorAdapter(),
        "backlink_csv": BacklinkCSVAdapter(),
        "crux_payload": CrUXPayloadAdapter(),
        "crawler_csv": CrawlerCSVAdapter(),
        "ga4_export": GA4ExportAdapter(),
        "gbp_local": GBPLocalAdapter(),
        "gsc_export": GSCExportAdapter(),
        "hreflang_validator": HreflangValidatorAdapter(),
        "knowledge_graph": KnowledgeGraphAdapter(),
        "log_parser": LogParserAdapter(),
        "pagespeed_payload": PageSpeedPayloadAdapter(),
        "rank_tracking_csv": RankTrackingCSVAdapter(),
        "redirect_chain": RedirectChainAdapter(),
        "robots_txt": RobotsTxtAdapter(),
        "schema_validation": SchemaValidationAdapter(),
        "sitemap_validator": SitemapValidatorAdapter(),
    }
