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
        (("technical", "crawl", "index", "schema", "canonical", "robots", "sitemap", "core web vitals"), "SEO Technical Agent", "workflows/technical-deployment-workflow.md"),
        (("content", "brief", "copy", "metadata", "refresh", "article"), "SEO Copywriter/Content Agent", "workflows/content-production-workflow.md"),
        (("local", "gbp", "nap", "citation", "reviews"), "Local SEO Agent", "workflows/request-routing.md"),
        (("international", "hreflang", "multilingual", "locale"), "International & Multilingual SEO Agent", "workflows/request-routing.md"),
        (("geo", "aio", "ai overview", "ai search", "citation"), "GEO / AIO Optimization Agent", "workflows/request-routing.md"),
        (("security", "negative seo", "malware", "hacked", "toxic"), "Negative SEO & Security Agent", "workflows/monitoring-workflow.md"),
        (("strategy", "roadmap", "plan", "prioritize"), "Senior SEO Strategist Agent", "workflows/request-routing.md"),
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
        }.get(lead_agent, ["SEO Scrummaster Agent"])
        return RouteResult(
            lead_agent=lead_agent,
            supporting_agents=support,
            workflow=workflow,
            required_evidence=["business_context", "target_domain_or_urls", "available_first_party_data", "technical_or_content_artifacts"],
            escalation="Escalate to SEO Scrummaster Agent for high-risk changes or missing evidence.",
            confidence=confidence,
        )

