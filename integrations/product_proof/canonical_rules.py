"""Canonical graph and pagination rules over collected page evidence."""
from __future__ import annotations

from integrations.product_proof.rule_types import (
    CrawlEvidence,
    PageEvidence,
    RuleContext,
)


def _broken_targets(self: RuleContext, p: list[PageEvidence], by: dict[str, PageEvidence], ns: list[PageEvidence]) -> None:
    broken = [
        x
        for x in ns
        if x["canonical"] in by and not 200 <= by[x["canonical"]]["status_code"] < 300
    ]
    if broken:
        self.add(
            "canonical-broken-target",
            "Canonical targets return non-success responses",
            "Critical",
            "Canonicalization",
            ["canonical-strength"],
            f"{len(broken)} page(s) target non-2xx canonicals.",
            "Invalid targets prevent reliable consolidation.",
            "Point to stable indexable 2xx URLs.",
            "Recrawl source and target.",
            [x["final_url"] for x in broken],
            "SEO Technical Agent",
        )


def _canonical_paths(ns: list[PageEvidence], by: dict[str, PageEvidence]) -> tuple[list[str], list[str]]:
    chains = []
    cycles = []
    for x in ns:
        origin = x["final_url"]
        cur = x["canonical"]
        seen = {origin}
        depth = 0
        while cur in by and by[cur].get("canonical"):
            depth += 1
            if cur in seen:
                cycles.append(origin)
                break
            seen.add(cur)
            nxt = by[cur]["canonical"]
            if nxt == cur:
                break
            cur = nxt
            if depth >= 20:
                break
        if depth > 1 and origin not in cycles:
            chains.append(origin)
    return chains, cycles


def _path_findings(self: RuleContext, chains: list[str], cycles: list[str]) -> None:
    if cycles:
        self.add(
            "canonical-cycle",
            "Canonical signals form a cycle",
            "Critical",
            "Canonicalization",
            ["canonical-strength"],
            f"{len(set(cycles))} cycle origin(s).",
            "Conflicting consolidation instructions.",
            "Choose one preferred URL and point duplicates directly.",
            "Confirm an acyclic graph.",
            cycles,
            "SEO Technical Agent",
        )
    if chains:
        self.add(
            "canonical-chain",
            "Canonical annotations form multi-hop chains",
            "High",
            "Canonicalization",
            ["canonical-strength"],
            f"{len(set(chains))} chain origin(s).",
            "Indirect signals add ambiguity.",
            "Point duplicates directly to final canonical.",
            "Confirm one-hop targets.",
            chains,
            "SEO Technical Agent",
        )


def _pagination(self: RuleContext, p: list[PageEvidence]) -> None:
    bad = [
        x["final_url"]
        for x in p
        if self.paged(x["final_url"]) and x.get("canonical") == self.page1(x["final_url"])
    ]
    if bad:
        self.add(
            "pagination-canonical-page-one",
            "Paginated pages canonicalize to page one",
            "Critical",
            "Pagination",
            ["pagination-self-canonical"],
            f"{len(bad)} paginated page(s) target page one.",
            "Deep content can be excluded from discovery/indexing.",
            "Use unique URLs, self-canonicals, and anchor links.",
            "Crawl the full sequence.",
            bad,
            "SEO Information Architecture Agent",
        )
    legacy = [x["final_url"] for x in p if x.get("rel_next") or x.get("rel_prev")]
    if legacy:
        self.add(
            "pagination-legacy-rel",
            "Pages depend on legacy rel=next/prev annotations",
            "Low",
            "Pagination",
            ["rel-next-prev-dead", "pagination-real-links"],
            f"{len(legacy)} page(s) include legacy annotations.",
            "They are not a current Google pagination signal.",
            "Ensure real anchor pagination and self-canonicals.",
            "Crawl without relying on annotations.",
            legacy,
            "SEO Information Architecture Agent",
        )


def canon(self: RuleContext, c: CrawlEvidence) -> None:
    p = c["pages"]
    by = {x["final_url"]: x for x in p}
    ns = [x for x in p if x.get("canonical") and x["canonical"] != x["final_url"]]
    _broken_targets(self, p, by, ns)
    chains, cycles = _canonical_paths(ns, by)
    _path_findings(self, chains, cycles)
    _pagination(self, p)
    dup = {x["final_url"] for x in ns}
    links = [t for x in p for t in x["internal_links"] if t in dup]
    if links:
        self.add(
            "links-to-noncanonical",
            "Internal links point to noncanonical URL variants",
            "High",
            "Internal Links",
            ["canonical-link-consistency"],
            f"{len(set(links))} noncanonical targets receive links.",
            "The graph contradicts canonical preferences.",
            "Link to preferred canonicals.",
            "Recrawl and verify targets.",
            links,
            "SEO Information Architecture Agent",
        )
