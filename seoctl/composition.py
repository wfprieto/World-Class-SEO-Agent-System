"""Public outer construction root: cross-layer dependencies are injected here."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from adapters import mcp_extensions
from adapters.accessibility_checker import AccessibilityCheckerAdapter
from adapters.ai_citation_monitor import AICitationMonitorAdapter
from adapters.backlinks import BacklinkCSVAdapter
from adapters.crawler_csv import CrawlerCSVAdapter
from adapters.crux import CrUXPayloadAdapter
from adapters.evidence_store import canonicalize_url
from adapters.ga4 import GA4ExportAdapter
from adapters.gbp_local import GBPLocalAdapter
from adapters.google_pagespeed_live import GooglePageSpeedLiveAdapter
from adapters.gsc import GSCExportAdapter
from adapters.gsc_live_example import GSCLiveExampleAdapter
from adapters.hreflang_validator import HreflangValidatorAdapter
from adapters.knowledge_graph import KnowledgeGraphAdapter
from adapters.llm_transport import build_llm_opener
from adapters.log_parser import LogParserAdapter
from adapters.page_drift import PageDrift
from adapters.pagespeed import PageSpeedPayloadAdapter
from adapters.rank_tracking import RankTrackingCSVAdapter
from adapters.redirect_chain import RedirectChainAdapter
from adapters.rendered_page import RenderedPageAdapter, _raw_fetch
from adapters.robots_txt import RobotsTxtAdapter
from adapters.schema_validation import SchemaValidationAdapter
from adapters.sitemap_validator import SitemapValidatorAdapter
from integrations.authority_media.adapters import AuthorityMediaAdapter, DriftExecutionAdapter
from integrations.authority_media.services import CommonCrawlService, DriftService
from integrations.content_intelligence.adapters import ContentIntelligenceAdapter
from integrations.content_intelligence.service import ContentIntelligenceService
from integrations.extensions import ExtensionAdapter, IndexNowAdapter
from integrations.extensions.providers import ProviderService
from integrations.google.client import GoogleJsonClient, GoogleOAuthConfig, GoogleOAuthProvider
from integrations.google.crux import CrUXCurrentAdapter, CrUXHistoryAdapter
from integrations.google.ga4 import GoogleAnalyticsDataAdapter
from integrations.google.gsc import GoogleSearchConsoleAdapter
from integrations.google.sitemaps import GoogleSitemapsAdapter
from integrations.product_proof.adapters import (
    ProductProofIntelligenceAdapter,
    ProductProofTechnicalAuditAdapter,
)
from integrations.product_proof.service import ProductProofTechnicalAudit
from integrations.technical.adapters import (
    RenderedPageExecutionAdapter,
    TechnicalExecutionAdapter,
)
from integrations.technical.http import BoundedHttpClient
from integrations.technical.inspection import TechnicalInspectionService
from runtime.assets import resolve_asset_root
from runtime.llm import LLMClient
from runtime.llm import build_llm_client as _build_llm_client
from runtime.memory import MemoryStore
from runtime.orchestrator import SEOOrchestrator
from runtime.tools import ToolDispatcher


def default_adapters(repo_root: Path | None = None) -> dict[str, object]:
    authority = AuthorityMediaAdapter(build_commoncrawl_service())
    drift = DriftExecutionAdapter(build_drift_service())
    extensions = ExtensionAdapter(build_provider_service())
    indexnow = IndexNowAdapter()
    product_proof = ProductProofTechnicalAuditAdapter(build_product_proof_service(repo_root))
    product_intelligence = ProductProofIntelligenceAdapter()
    return {
        "accessibility_checker": AccessibilityCheckerAdapter(),
        "ai_citation_monitor": AICitationMonitorAdapter(),
        "authority_media": authority,
        "drift_execution": drift,
        "optional_extensions": extensions,
        "indexnow": indexnow,
        "product_proof_technical_audit": product_proof,
        "product_proof_intelligence": product_intelligence,
        "backlinks": BacklinkCSVAdapter(),
        "backlink_csv": BacklinkCSVAdapter(),
        "content_intelligence": ContentIntelligenceAdapter(build_content_service()),
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
        "rendered_page": RenderedPageAdapter(build_raw_fetch()),
        "robots_txt": RobotsTxtAdapter(),
        "schema_validation": SchemaValidationAdapter(),
        "sitemap_validator": SitemapValidatorAdapter(),
        "google_pagespeed_live": build_pagespeed_adapter(),
        "pagespeed_live": build_pagespeed_adapter(),
        "google_crux_current": CrUXCurrentAdapter(),
        "crux_current": CrUXCurrentAdapter(),
        "google_crux_history": CrUXHistoryAdapter(),
        "crux_history": CrUXHistoryAdapter(),
        "rendered_page_execution": RenderedPageExecutionAdapter(),
        "playwright_render": RenderedPageExecutionAdapter(),
        "technical_execution": TechnicalExecutionAdapter(build_technical_service()),
        "technical_inspection": TechnicalExecutionAdapter(build_technical_service()),
    }


class CanonicalProviderControls:
    """Concrete wrapper bound once at the outer construction boundary."""

    capability_report = staticmethod(mcp_extensions.capability_report)
    preflight = staticmethod(mcp_extensions.preflight)
    render_config = staticmethod(mcp_extensions.render_config)
    estimate_cost = staticmethod(mcp_extensions.estimate_cost)


def build_provider_service() -> ProviderService:
    return ProviderService(CanonicalProviderControls())


def build_content_service() -> ContentIntelligenceService:
    return ContentIntelligenceService(build_provider_service())


def build_drift_service() -> DriftService:
    return DriftService(PageDrift, canonicalize_url)


def build_commoncrawl_service() -> CommonCrawlService:
    return CommonCrawlService(canonicalize_url)


def build_product_proof_service(repo_root: Path | None = None) -> ProductProofTechnicalAudit:
    root = resolve_asset_root(repo_root)
    return ProductProofTechnicalAudit(claim_registry=root / "knowledge" / "seo-claim-registry.json")


def build_pagespeed_adapter(
    api_key: str | None = None,
    *,
    crux_api_key: str | None = None,
    timeout: float = 60,
    max_retries: int = 2,
    max_response_bytes: int = 12_000_000,
    sleep: Callable[[float], None] | None = None,
) -> GooglePageSpeedLiveAdapter:
    options: dict[str, Any] = {
        "allowed_hosts": {"pagespeedonline.googleapis.com", "chromeuxreport.googleapis.com"},
        "timeout": timeout,
        "max_retries": max_retries,
        "max_response_bytes": max_response_bytes,
    }
    if sleep is not None:
        options["sleep"] = sleep
    return GooglePageSpeedLiveAdapter(
        api_key,
        crux_api_key=crux_api_key,
        client=GoogleJsonClient(**options),
    )


def build_gsc_example_adapter() -> GSCLiveExampleAdapter:
    return GSCLiveExampleAdapter(
        oauth=GoogleOAuthProvider(GoogleOAuthConfig.from_env("GSC")),
        client=GoogleJsonClient(allowed_hosts={"www.googleapis.com"}),
    )


def build_raw_fetch() -> Callable[[str], tuple[str, int | None, dict[str, str]]]:
    client = BoundedHttpClient(
        timeout=30,
        max_response_bytes=12_000_000,
        max_redirects=10,
        user_agent="Mozilla/5.0 (compatible; SEO-Kit-Render/1.0)",
    )

    def fetch(url: str) -> tuple[str, int | None, dict[str, str]]:
        return _raw_fetch(url, client)

    return fetch


def build_technical_service() -> TechnicalInspectionService:
    return TechnicalInspectionService(pagespeed=build_pagespeed_adapter())


def build_llm_client(provider: str = "echo", model: str | None = None) -> LLMClient:
    return _build_llm_client(provider, model, opener=build_llm_opener())


def build_orchestrator(
    repo_root: Path,
    *,
    provider: str = "echo",
    model: str | None = None,
    llm_client: LLMClient | None = None,
    tool_dispatcher: ToolDispatcher | None = None,
    memory: MemoryStore | None = None,
) -> SEOOrchestrator:
    dispatcher = (
        tool_dispatcher
        if tool_dispatcher is not None
        else ToolDispatcher(default_adapters(repo_root))
    )
    client = llm_client if llm_client is not None else build_llm_client(provider, model)
    return SEOOrchestrator(repo_root, llm_client=client, tool_dispatcher=dispatcher, memory=memory)
