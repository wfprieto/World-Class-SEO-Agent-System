"""Deterministic request routing for lead and supporting SEO agents."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class RouteResult:
    lead_agent: str
    supporting_agents: list[str]
    workflow: str
    required_evidence: list[str]
    escalation: str
    confidence: str

    def to_dict(self) -> dict:
        return asdict(self)


class RequestRouter:
    """Keyword-driven routing layer that mirrors workflows/request-routing.md.

    This is intentionally simple and deterministic. LLM runtimes can replace the
    classifier while preserving the same output contract.
    """

    ROUTES = [
        (("plain-language", "stakeholder", "client report", "non-technical", "summary"), "SEO Output Report Agent", "workflows/request-routing.md"),
        (("diagnostic", "tool stack", "dashboard", "reporting setup", "seo tools", "grading"), "SEO Diagnostic Infrastructure Agent", "workflows/request-routing.md"),
        (("engineer", "implementation", "code fix", "regression test", "deploy"), "Senior SEO Engineer Agent", "workflows/technical-deployment-workflow.md"),
        (("technical", "crawl", "index", "schema", "canonical", "robots", "sitemap", "core web vitals"), "SEO Technical Agent", "workflows/technical-deployment-workflow.md"),
        (("information architecture", "taxonomy", "navigation", "url structure", "internal link"), "SEO Information Architecture Agent", "workflows/request-routing.md"),
        (("accessibility", "wcag", "alt text", "screen reader", "keyboard"), "SEO Accessibility Agent", "workflows/request-routing.md"),
        (("cro", "conversion", "cta", "landing page", "a/b test"), "SEO CRO Agent", "workflows/request-routing.md"),
        (("content", "brief", "copy", "metadata", "refresh", "article"), "SEO Copywriter/Content Agent", "workflows/content-production-workflow.md"),
        (("local", "gbp", "nap", "citation", "reviews"), "Local SEO Agent", "workflows/request-routing.md"),
        (("international", "hreflang", "multilingual", "locale"), "International & Multilingual SEO Agent", "workflows/request-routing.md"),
        (("image", "video", "youtube", "transcript", "visual search"), "Visual & Video Search Agent", "workflows/request-routing.md"),
        (("voice", "spoken", "conversational", "faq", "q&a"), "Voice Search & Conversational Agent", "workflows/request-routing.md"),
        (("geo", "aio", "ai overview", "ai search", "citation"), "GEO / AIO Optimization Agent", "workflows/request-routing.md"),
        (("compliance", "legal", "disclosure", "claims", "privacy", "regulated"), "SEO Compliance & Legal Agent", "workflows/request-routing.md"),
        (("security", "negative seo", "malware", "hacked", "toxic"), "Negative SEO & Security Agent", "workflows/monitoring-workflow.md"),
        (("digital pr", "outreach", "unlinked mention", "linkable asset", "backlink gap"), "Digital PR & Programmatic Link Outreach Agent", "workflows/request-routing.md"),
        (("trend", "forecast", "seasonality", "emerging topic"), "Predictive SEO Trend Agent", "workflows/request-routing.md"),
        (("competitor", "competitive", "serp movement", "content gap"), "Competitive Intelligence Agent", "workflows/request-routing.md"),
        (("experiment", "hypothesis", "research design", "seo test"), "SEO Research and Development Agent", "workflows/request-routing.md"),
        (("knowledge graph", "entity", "sameas", "brand serp"), "SEO Knowledge Graph Sync Agent", "workflows/request-routing.md"),
        (("algorithm", "knowledge sync", "rule update", "official source"), "AI Principal SEO Scientist", "workflows/continuous-learning-workflow.md"),
        (("strategy", "roadmap", "plan", "prioritize"), "Senior SEO Strategist Agent", "workflows/request-routing.md"),
        (("scrum", "sprint", "debate", "decision"), "SEO Scrummaster Agent", "workflows/request-routing.md"),
        (("audit", "analyze", "health", "score"), "SEO Full Audit/Analyst Agent", "workflows/full-audit-workflow.md"),
    ]

    def route(self, request: str) -> RouteResult:
        normalized = request.lower()
        for keywords, lead_agent, workflow in self.ROUTES:
            if any(keyword in normalized for keyword in keywords):
                return self._result(lead_agent, workflow)
        return self._result("SEO Scrummaster Agent", "workflows/request-routing.md", confidence="Low")

    def _result(self, lead_agent: str, workflow: str, confidence: str = "Medium") -> RouteResult:
        support = {
            "SEO Full Audit/Analyst Agent": ["SEO Technical Agent", "SEO Copywriter/Content Agent", "SEO Diagnostic Infrastructure Agent", "SEO Output Report Agent"],
            "SEO Diagnostic Infrastructure Agent": ["SEO Full Audit/Analyst Agent", "SEO Output Report Agent", "SEO Technical Agent"],
            "SEO Output Report Agent": ["SEO Full Audit/Analyst Agent", "SEO Scrummaster Agent", "Senior SEO Strategist Agent"],
            "SEO Technical Agent": ["Senior SEO Engineer Agent", "SEO Scrummaster Agent"],
            "SEO Copywriter/Content Agent": ["SEO Compliance & Legal Agent", "GEO / AIO Optimization Agent", "SEO CRO Agent"],
            "Senior SEO Engineer Agent": ["SEO Technical Agent", "SEO Scrummaster Agent"],
            "SEO Information Architecture Agent": ["SEO Technical Agent", "SEO Copywriter/Content Agent"],
            "SEO Accessibility Agent": ["Senior SEO Engineer Agent", "SEO CRO Agent"],
            "SEO CRO Agent": ["SEO Copywriter/Content Agent", "Senior SEO Strategist Agent"],
            "Local SEO Agent": ["SEO Copywriter/Content Agent", "SEO Knowledge Graph Sync Agent"],
            "International & Multilingual SEO Agent": ["SEO Technical Agent", "SEO Copywriter/Content Agent"],
            "Visual & Video Search Agent": ["SEO Technical Agent", "SEO Copywriter/Content Agent"],
            "Voice Search & Conversational Agent": ["SEO Copywriter/Content Agent", "GEO / AIO Optimization Agent"],
            "GEO / AIO Optimization Agent": ["SEO Knowledge Graph Sync Agent", "SEO Copywriter/Content Agent"],
            "SEO Compliance & Legal Agent": ["SEO Copywriter/Content Agent", "SEO Scrummaster Agent"],
            "Negative SEO & Security Agent": ["SEO Technical Agent", "Senior SEO Engineer Agent"],
            "Digital PR & Programmatic Link Outreach Agent": ["Competitive Intelligence Agent", "SEO Compliance & Legal Agent"],
            "Predictive SEO Trend Agent": ["SEO Copywriter/Content Agent", "Senior SEO Strategist Agent"],
            "Competitive Intelligence Agent": ["SEO Full Audit/Analyst Agent", "Digital PR & Programmatic Link Outreach Agent"],
            "SEO Research and Development Agent": ["SEO Full Audit/Analyst Agent", "SEO Scrummaster Agent"],
            "SEO Knowledge Graph Sync Agent": ["GEO / AIO Optimization Agent", "SEO Technical Agent"],
            "AI Principal SEO Scientist": ["SEO Scrummaster Agent", "SEO Research and Development Agent"],
            "Senior SEO Strategist Agent": ["SEO Full Audit/Analyst Agent", "SEO Scrummaster Agent"],
        }.get(lead_agent, ["SEO Scrummaster Agent"])
        return RouteResult(
            lead_agent=lead_agent,
            supporting_agents=support,
            workflow=workflow,
            required_evidence=["business_context", "target_domain_or_urls", "available_first_party_data", "technical_or_content_artifacts"],
            escalation="Escalate to SEO Scrummaster Agent for high-risk changes or missing evidence.",
            confidence=confidence,
        )
