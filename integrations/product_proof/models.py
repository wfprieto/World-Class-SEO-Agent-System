from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from integrations.product_proof.rule_types import (
    CrawlLimits,
    FindingEvidence,
    PageEvidence,
    RobotsEvidence,
)


@dataclass(frozen=True)
class CrawlConfig:
    max_urls: int = 500
    max_depth: int = 6
    max_asset_hosts: int = 10
    max_redirects: int = 10
    timeout_seconds: float = 30.0
    max_response_bytes: int = 12_000_000

    def __post_init__(self) -> None:
        if not 1 <= self.max_urls <= 10_000:
            raise ValueError("max_urls must be from 1 to 10000")
        if not 0 <= self.max_depth <= 20:
            raise ValueError("max_depth must be from 0 to 20")
        if not 0 <= self.max_asset_hosts <= 50:
            raise ValueError("max_asset_hosts must be from 0 to 50")
        if not 0 <= self.max_redirects <= 20:
            raise ValueError("max_redirects must be from 0 to 20")
        if not 1 <= self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be from 1 to 120")
        if not 1 <= self.max_response_bytes <= 50_000_000:
            raise ValueError("max_response_bytes must be from 1 to 50000000")

    def to_dict(self) -> CrawlLimits:
        values = asdict(self)
        return CrawlLimits(
            max_urls=values["max_urls"],
            max_depth=values["max_depth"],
            max_asset_hosts=values["max_asset_hosts"],
            max_redirects=values["max_redirects"],
            timeout_seconds=values["timeout_seconds"],
            max_response_bytes=values["max_response_bytes"],
        )


@dataclass
class PageRecord:
    requested_url: str
    final_url: str
    depth: int
    status_code: int
    elapsed_ms: int
    content_type: str | None
    title: str | None
    h1: list[str]
    canonical: str | None
    meta_robots: list[str]
    x_robots_tag: str | None
    internal_links: list[str]
    external_links: list[str]
    asset_urls: list[str]
    images: list[dict[str, Any]]
    jsonld_types: list[str]
    rel_next: list[str]
    rel_prev: list[str]
    data_nosnippet_count: int
    text_length: int
    content_hash: str
    soft_404_signal: bool
    raw_html_available: bool
    meta_description: str | None = None
    viewport: str | None = None
    charset: str | None = None
    open_graph_tags: list[str] = field(default_factory=list)
    twitter_tags: list[str] = field(default_factory=list)
    deprecated_meta: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> PageEvidence:
        values = asdict(self)
        return PageEvidence(
            requested_url=values["requested_url"],
            final_url=values["final_url"],
            depth=values["depth"],
            status_code=values["status_code"],
            elapsed_ms=values["elapsed_ms"],
            content_type=values["content_type"],
            title=values["title"],
            h1=values["h1"],
            canonical=values["canonical"],
            meta_robots=values["meta_robots"],
            x_robots_tag=values["x_robots_tag"],
            internal_links=values["internal_links"],
            external_links=values["external_links"],
            asset_urls=values["asset_urls"],
            images=values["images"],
            jsonld_types=values["jsonld_types"],
            rel_next=values["rel_next"],
            rel_prev=values["rel_prev"],
            data_nosnippet_count=values["data_nosnippet_count"],
            text_length=values["text_length"],
            content_hash=values["content_hash"],
            soft_404_signal=values["soft_404_signal"],
            raw_html_available=values["raw_html_available"],
            meta_description=values["meta_description"],
            viewport=values["viewport"],
            charset=values["charset"],
            open_graph_tags=values["open_graph_tags"],
            twitter_tags=values["twitter_tags"],
            deprecated_meta=values["deprecated_meta"],
            errors=values["errors"],
        )


@dataclass
class RobotsRecord:
    host: str
    robots_url: str
    status_code: int
    elapsed_ms: int
    size_bytes: int
    groups: list[dict[str, Any]]
    sitemaps: list[str]
    unknown_directives: list[str]
    errors: list[str]

    def to_dict(self) -> RobotsEvidence:
        values = asdict(self)
        return RobotsEvidence(
            host=values["host"],
            robots_url=values["robots_url"],
            status_code=values["status_code"],
            elapsed_ms=values["elapsed_ms"],
            size_bytes=values["size_bytes"],
            groups=values["groups"],
            sitemaps=values["sitemaps"],
            unknown_directives=values["unknown_directives"],
            errors=values["errors"],
        )


@dataclass
class Finding:
    id: str
    title: str
    severity: str
    category: str
    evidence_state: str
    evidence_class: str
    claim_ids: list[str]
    observed: str
    business_impact: str
    recommended_action: str
    verification: str
    affected_urls: list[str]
    owner: str
    confidence: str = "High"
    contradictory_evidence: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> FindingEvidence:
        values = asdict(self)
        return FindingEvidence(
            id=values["id"], title=values["title"], severity=values["severity"], category=values["category"],
            evidence_state=values["evidence_state"], evidence_class=values["evidence_class"],
            claim_ids=values["claim_ids"], observed=values["observed"],
            business_impact=values["business_impact"], recommended_action=values["recommended_action"],
            verification=values["verification"], affected_urls=values["affected_urls"],
            owner=values["owner"], confidence=values["confidence"],
            contradictory_evidence=values["contradictory_evidence"],
            missing_evidence=values["missing_evidence"],
        )


@dataclass
class AgentContribution:
    agent: str
    stage: str
    evidence_added: int
    findings_proposed: int
    findings_accepted: int
    findings_merged: int
    findings_rejected: int
    decisions_recorded: int
    unique_contribution: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["contribution_type"] = "DETERMINISTIC_RULE_ATTRIBUTION"
        payload["execution_evidence"] = []
        return payload
