from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        return asdict(self)
