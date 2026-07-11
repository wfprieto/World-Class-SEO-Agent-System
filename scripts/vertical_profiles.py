"""Six SEO vertical architecture profiles, and routing over them.

Data companion to `knowledge/seo-vertical-profiles.md`.

This is NOT a second router. `runtime/routing.py` remains the only request router, and
`docs/plugin-packaging.md` section 9 remains the single business-type detection authority.
This module only resolves *which profile(s)* apply once signals are supplied, and it refuses
to classify on weak evidence.

Rules:
- Low confidence never silently routes; it returns UNCONFIRMED and asks or stops.
- Two or more strongly-evidenced business models produce a declared HYBRID route.
- Detection is a routing aid, not a factual claim about the business.
"""

from __future__ import annotations

from typing import Any

# Strong signals per profile. A profile is "strongly evidenced" at >= MIN_STRONG matches.
STRONG_SIGNALS: dict[str, set[str]] = {
    "ecommerce": {"cart", "checkout", "product_schema", "add_to_cart", "merchant_feed"},
    "local-service": {"nap_block", "store_locator", "local_business_schema", "service_area",
                      "google_business_profile"},
    "saas": {"pricing_tiers", "free_trial", "software_application_schema", "docs_site",
             "changelog"},
    "publisher": {"article_schema", "author_bylines", "high_article_volume", "ad_slots",
                  "subscription_wall"},
    "agency": {"case_studies", "contact_sales", "services_pages", "client_logos"},
}
MIN_STRONG = 2

_BASE_AGENTS = ["SEO Technical Agent", "SEO Copywriter/Content Agent"]

PROFILES: dict[str, dict[str, Any]] = {
    "generic": {
        "detection_signals": ["no strong signals from any other profile"],
        "required_agents": _BASE_AGENTS + ["SEO Full Audit/Analyst Agent"],
        "required_skills": ["full-site-audit", "technical-audit", "content-audit",
                            "content-brief", "core-web-vitals-triage"],
        "default_modules": ["technical", "content", "indexation", "cwv", "schema"],
        "excluded_modules": [],
        "evidence_requirements": ["crawl export", "GSC export", "analytics export"],
        "architecture": "Flat topic hubs; no assumed commerce or local layer.",
        "keyword_architecture": "Intent-clustered hubs; no vertical-specific assumptions.",
        "technical_priorities": ["indexation", "canonicals", "CWV"],
        "conversion_model": "Undeclared; require the owner to state the primary action.",
        "schema": ["Organization", "BreadcrumbList", "WebPage"],
        "geo_aio": ["entity clarity", "self-contained answers"],
        "measurement": ["organic entrances", "engaged sessions", "owner-declared conversion"],
        "risks": ["misrouting if the business model was never declared"],
        "handoffs": ["Senior SEO Strategist Agent"],
        "outputs": ["templates/audit-report.md"],
        "stop_conditions": ["business model undeclared and unresolvable"],
    },
    "ecommerce": {
        "detection_signals": sorted(STRONG_SIGNALS["ecommerce"]),
        "required_agents": _BASE_AGENTS + ["SEO E-commerce Agent"],
        "required_skills": ["product-page-seo-audit", "product-schema-validate-generate",
                            "faceted-navigation-governance", "merchant-data-consistency-audit",
                            "content-brief"],
        "default_modules": ["product", "category", "faceted-nav", "feed", "schema", "cwv"],
        "excluded_modules": ["local-pack"],
        "evidence_requirements": ["product/category URL sample", "structured data", "feed status"],
        "architecture": "Category -> subcategory -> product; governed facets; canonical variants.",
        "keyword_architecture": "Category head terms; product long-tail; buying-intent modifiers.",
        "technical_priorities": ["faceted crawl control", "variant canonicals", "hero-image LCP"],
        "conversion_model": "Add-to-cart and checkout completion.",
        "schema": ["Product", "Offer", "ProductGroup", "BreadcrumbList"],
        "geo_aio": ["product entity clarity", "honest specs and availability"],
        "marketplace": "Optional; only with a connected, cost-approved source.",
        "measurement": ["product impressions", "add-to-cart", "revenue per session"],
        "risks": ["index bloat from facets", "thin variant pages", "feed/page mismatch"],
        "handoffs": ["SEO Compliance & Legal Agent for pricing and claims"],
        "outputs": ["templates/ecommerce-seo-report.md"],
        "stop_conditions": ["no product data source of truth"],
    },
    "local-service": {
        "detection_signals": sorted(STRONG_SIGNALS["local-service"]),
        "required_agents": _BASE_AGENTS + ["Local SEO Agent"],
        "required_skills": ["local-seo-audit", "citation-audit", "gbp-profile-audit",
                            "cross-platform-nap-verify", "content-brief"],
        "default_modules": ["gbp", "nap", "local-pages", "reviews", "local-schema"],
        "excluded_modules": ["faceted-nav"],
        "evidence_requirements": ["NAP", "service list", "location list", "GBP data"],
        "architecture": "Service x location pages only where a real service area exists.",
        "keyword_architecture": "Service + city intent; no doorway city pages.",
        "technical_priorities": ["LocalBusiness schema", "NAP consistency", "mobile UX"],
        "conversion_model": "Call, booking, direction request, quote form.",
        "schema": ["LocalBusiness", "Service", "BreadcrumbList"],
        "geo_aio": ["entity consistency across maps and web"],
        "local": "Geo-grid rank and GBP audit require a connected, cost-approved source.",
        "measurement": ["local pack visibility", "calls", "direction requests"],
        "risks": ["fake locations", "fake reviews", "doorway city pages"],
        "handoffs": ["SEO Compliance & Legal Agent for review authenticity"],
        "outputs": ["templates/local-seo-report.md"],
        "stop_conditions": ["no verifiable physical or service-area presence"],
    },
    "saas": {
        "detection_signals": sorted(STRONG_SIGNALS["saas"]),
        "required_agents": _BASE_AGENTS + ["SEO CRO Agent"],
        "required_skills": ["content-brief", "competitor-comparison-page-build",
                            "serp-overlap-cluster", "content-audit", "landing-page-cro-audit"],
        "default_modules": ["content", "comparison", "docs", "cwv", "schema"],
        "excluded_modules": ["local-pack"],
        "evidence_requirements": ["pricing model", "ICP", "feature matrix", "docs structure"],
        "architecture": "Product -> use case -> integration -> comparison -> docs.",
        "keyword_architecture": "Jobs-to-be-done, alternatives, integrations, glossary.",
        "technical_priorities": ["SSR of primary content", "docs indexation", "CWV"],
        "conversion_model": "Trial start, demo request, signup.",
        "schema": ["SoftwareApplication", "Organization", "BreadcrumbList"],
        "geo_aio": ["citable feature and pricing facts", "honest comparisons"],
        "measurement": ["trial starts", "demo requests", "assisted pipeline"],
        "risks": ["client-side-rendered content invisible to crawlers",
                  "unfair or unverifiable competitor claims"],
        "handoffs": ["SEO Compliance & Legal Agent for comparative claims"],
        "outputs": ["templates/content-brief.md"],
        "stop_conditions": ["comparison claims cannot be substantiated"],
    },
    "publisher": {
        "detection_signals": sorted(STRONG_SIGNALS["publisher"]),
        "required_agents": _BASE_AGENTS + ["SEO Full Audit/Analyst Agent"],
        "required_skills": ["content-audit", "content-decay", "content-brief",
                            "internal-link-map", "geo-aio-citation-audit"],
        "default_modules": ["content", "decay", "archive", "schema", "cwv"],
        "excluded_modules": ["faceted-nav", "local-pack"],
        "evidence_requirements": ["article inventory", "author data", "traffic decay data"],
        "architecture": "Topic hubs with authored articles; clean archive and pagination.",
        "keyword_architecture": "Topical authority clusters; evergreen plus news.",
        "technical_priorities": ["indexation of archives", "CWV with ad slots", "pagination"],
        "conversion_model": "Subscription, newsletter signup, ad revenue per session.",
        "schema": ["Article", "NewsArticle", "Person", "BreadcrumbList"],
        "geo_aio": ["author credibility", "sourced claims", "freshness"],
        "measurement": ["engaged sessions", "subscriptions", "returning readers"],
        "risks": ["content decay", "ad-driven CWV regressions", "thin syndicated content"],
        "handoffs": ["SEO Compliance & Legal Agent for sponsored disclosure"],
        "outputs": ["templates/content-refresh-plan.md"],
        "stop_conditions": ["no author accountability for YMYL topics"],
    },
    "agency": {
        "detection_signals": sorted(STRONG_SIGNALS["agency"]),
        "required_agents": _BASE_AGENTS + ["Senior SEO Strategist Agent"],
        "required_skills": ["content-brief", "competitive-gap", "landing-page-cro-audit",
                            "content-audit", "seo-roadmap"],
        "default_modules": ["services", "case-studies", "content", "schema", "cwv"],
        "excluded_modules": ["faceted-nav"],
        "evidence_requirements": ["service list", "case studies", "target account profile"],
        "architecture": "Service pages -> proof (case studies) -> contact path.",
        "keyword_architecture": "Service + industry + outcome; bottom-funnel first.",
        "technical_priorities": ["indexable service pages", "CWV", "clear contact routes"],
        "conversion_model": "Contact-sales, proposal request, booked call.",
        "schema": ["Organization", "Service", "BreadcrumbList"],
        "geo_aio": ["verifiable expertise and named outcomes"],
        "measurement": ["qualified enquiries", "booked calls", "proposal rate"],
        "risks": ["unverifiable results claims", "thin service-x-city pages"],
        "handoffs": ["SEO Compliance & Legal Agent for outcome claims"],
        "outputs": ["templates/seo-roadmap.md"],
        "stop_conditions": ["claimed results cannot be evidenced"],
    },
}


def route(context: dict[str, Any]) -> dict[str, Any]:
    """Resolve profiles from supplied signals. Never classify silently on weak evidence."""
    signals = {str(s).lower() for s in (context.get("signals") or [])}
    matched = {
        name: sorted(signals & sig)
        for name, sig in STRONG_SIGNALS.items()
        if len(signals & sig) >= MIN_STRONG
    }

    if not matched:
        return {
            "route": "UNCONFIRMED",
            "confidence": "low",
            "profiles": [],
            "matched_signals": {},
            "action": "ask_or_stop",
            "note": (
                "Business-type detection is a routing aid, not a factual classification. "
                "Low confidence must not silently route an audit. Ask the owner or stop. "
                "Detection authority: docs/plugin-packaging.md section 9."
            ),
        }

    if len(matched) >= 2:
        return {
            "route": "HYBRID",
            "confidence": "high",
            "declared": True,
            "profiles": sorted(matched),
            "matched_signals": matched,
            "action": "run_declared_hybrid",
            "note": "Two or more business models are strongly evidenced. The hybrid route is declared, not silent.",
        }

    name = next(iter(matched))
    return {
        "route": "SINGLE",
        "confidence": "high",
        "declared": True,
        "profiles": [name],
        "matched_signals": matched,
        "action": "run_profile",
        "note": "User override always wins over auto-detection.",
    }


def profile(name: str) -> dict[str, Any]:
    if name not in PROFILES:
        raise KeyError(f"unknown vertical profile: {name}")
    return PROFILES[name]
