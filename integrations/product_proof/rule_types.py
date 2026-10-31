"""Typed evidence shapes consumed by deterministic product-proof rules."""
from __future__ import annotations

from typing import NotRequired, Protocol, TypedDict

ImageEvidence = dict[str, str | int | None]


class PageEvidence(TypedDict):
    requested_url: str
    final_url: str
    status_code: int
    internal_links: list[str]
    meta_robots: list[str]
    x_robots_tag: str | None
    canonical: NotRequired[str | None]
    asset_urls: NotRequired[list[str]]
    images: NotRequired[list[ImageEvidence]]
    soft_404_signal: NotRequired[bool]
    rel_next: NotRequired[list[str]]
    rel_prev: NotRequired[list[str]]
    depth: NotRequired[int]
    elapsed_ms: NotRequired[int]
    content_type: NotRequired[str | None]
    title: NotRequired[str | None]
    h1: NotRequired[list[str]]
    jsonld_types: NotRequired[list[str]]
    external_links: NotRequired[list[str]]
    data_nosnippet_count: NotRequired[int]
    text_length: NotRequired[int]
    content_hash: NotRequired[str]
    raw_html_available: NotRequired[bool]
    meta_description: NotRequired[str | None]
    viewport: NotRequired[str | None]
    charset: NotRequired[str | None]
    open_graph_tags: NotRequired[list[str]]
    twitter_tags: NotRequired[list[str]]
    deprecated_meta: NotRequired[list[str]]
    errors: NotRequired[list[str]]


class RobotsEvidence(TypedDict):
    host: str
    robots_url: str
    status_code: int
    size_bytes: int
    groups: list[dict[str, object]]
    unknown_directives: list[str]
    errors: list[str]
    elapsed_ms: int
    sitemaps: list[str]


class CrawlLimits(TypedDict):
    max_urls: int
    max_depth: int
    max_asset_hosts: int
    max_redirects: int
    timeout_seconds: float
    max_response_bytes: int


class CrawlFailure(TypedDict):
    url: str
    error: str


class CrawlEvidence(TypedDict):
    start_url: str
    pages: list[PageEvidence]
    robots: list[RobotsEvidence]
    root_host: str
    failed_fetches: list[CrawlFailure]
    queued_but_not_crawled: int
    limits: CrawlLimits
    truncated: bool
    data_state: str


class ClaimEvidence(TypedDict):
    evidence_class: str


class FindingEvidence(TypedDict):
    id: str
    title: str
    severity: str
    category: str
    owner: str
    evidence_state: str
    evidence_class: str
    claim_ids: list[str]
    observed: str
    business_impact: str
    recommended_action: str
    verification: str
    affected_urls: list[str]
    confidence: str
    contradictory_evidence: list[str]
    missing_evidence: list[str]


class RootCauseGroup(TypedDict):
    category: str
    finding_ids: list[str]
    finding_count: int


class RuleEvaluation(TypedDict):
    findings: list[FindingEvidence]
    decisions: list[dict[str, str | int]]
    root_cause_groups: list[RootCauseGroup]


class TrustSummary(TypedDict):
    checks_attempted: int
    pages_completed: int
    fetches_failed: int
    robots_hosts_checked: int
    verified_or_strongly_supported_findings: int
    inferred_findings: int
    unsupported_material_findings: int
    evidence_integrity: str
    external_changes_made: str
    crawl_truncated: bool


class RuleContext(Protocol):
    decisions: list[dict[str, str | int]]

    def add(
        self, i: str, t: str, s: str, cat: str, claims: list[str], obs: str,
        impact: str, action: str, verify: str, urls: list[str], owner: str,
        state: str = "VERIFIED", confidence: str = "High", missing: list[str] | None = None,
    ) -> None: ...

    @staticmethod
    def dirs(p: PageEvidence) -> set[str]: ...
    def paged(self, u: str) -> bool: ...
    def page1(self, u: str) -> str: ...
    def facet(self, u: str) -> bool: ...
    def robots(self, c: CrawlEvidence) -> None: ...
    def statuses(self, c: CrawlEvidence) -> None: ...
    def canon(self, c: CrawlEvidence) -> None: ...
    def ai_cwv_facets(self, c: CrawlEvidence) -> None: ...
