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
from adapters.google_pagespeed_live import GooglePageSpeedLiveAdapter
from adapters.hreflang_validator import HreflangValidatorAdapter
from adapters.knowledge_graph import KnowledgeGraphAdapter
from adapters.log_parser import LogParserAdapter
from adapters.pagespeed import PageSpeedPayloadAdapter
from adapters.rank_tracking import RankTrackingCSVAdapter
from adapters.redirect_chain import RedirectChainAdapter
from adapters.rendered_page import RenderedPageAdapter
from adapters.robots_txt import RobotsTxtAdapter
from adapters.schema_validation import SchemaValidationAdapter
from adapters.sitemap_validator import SitemapValidatorAdapter
from integrations.google.crux import CrUXCurrentAdapter, CrUXHistoryAdapter
from integrations.google.ga4 import GoogleAnalyticsDataAdapter
from integrations.google.gsc import GoogleSearchConsoleAdapter
from integrations.google.sitemaps import GoogleSitemapsAdapter


def default_adapters() -> dict[str, object]:
    return {
        "accessibility_checker": AccessibilityCheckerAdapter(),
        "ai_citation_monitor": AICitationMonitorAdapter(),
        "backlinks": BacklinkCSVAdapter(),
        "backlink_csv": BacklinkCSVAdapter(),
        "crux": CrUXPayloadAdapter(),
        "crux_payload": CrUXPayloadAdapter(),
        "crawler_csv": CrawlerCSVAdapter(),
        "ga4": GA4ExportAdapter(),
        "ga4_export": GA4ExportAdapter(),
        "ga4_live": GoogleAnalyticsDataAdapter(),
        "google_analytics_data": GoogleAnalyticsDataAdapter(),
        "gbp_local": GBPLocalAdapter(),
        "gsc": GSCExportAdapter(),
        "gsc_export": GSCExportAdapter(),
        "gsc_live": GoogleSearchConsoleAdapter(),
        "google_search_console": GoogleSearchConsoleAdapter(),
        "google_search_console_sitemaps": GoogleSitemapsAdapter(),
        "gsc_sitemaps": GoogleSitemapsAdapter(),
        "hreflang_validator": HreflangValidatorAdapter(),
        "knowledge_graph": KnowledgeGraphAdapter(),
        "log_parser": LogParserAdapter(),
        "pagespeed": PageSpeedPayloadAdapter(),
        "pagespeed_payload": PageSpeedPayloadAdapter(),
        "rank_tracking": RankTrackingCSVAdapter(),
        "rank_tracking_csv": RankTrackingCSVAdapter(),
        "redirect_chain": RedirectChainAdapter(),
        "rendered_page": RenderedPageAdapter(),
        "robots_txt": RobotsTxtAdapter(),
        "schema_validation": SchemaValidationAdapter(),
        "sitemap_validator": SitemapValidatorAdapter(),
        "google_pagespeed_live": GooglePageSpeedLiveAdapter(),
        "pagespeed_live": GooglePageSpeedLiveAdapter(),
        "google_crux_current": CrUXCurrentAdapter(),
        "crux_current": CrUXCurrentAdapter(),
        "google_crux_history": CrUXHistoryAdapter(),
        "crux_history": CrUXHistoryAdapter(),
    }
