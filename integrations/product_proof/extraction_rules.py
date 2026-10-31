"""Observed snippet controls, image hints and bounded facet evidence."""
from __future__ import annotations

import urllib.parse
from collections import defaultdict

from integrations.product_proof.rule_types import (
    CrawlEvidence,
    PageEvidence,
    RuleContext,
)


def _snippet_controls(self: RuleContext, p: list[PageEvidence]) -> None:
    no = [x["final_url"] for x in p if "nosnippet" in self.dirs(x)]
    mx = [x["final_url"] for x in p if any(v.startswith("max-snippet") for v in self.dirs(x))]
    if no:
        self.add(
            "nosnippet-tradeoff",
            "Pages use nosnippet, affecting normal snippets and Google AI features",
            "Medium",
            "AI Extraction Controls",
            ["nosnippet-ai-input"],
            f"{len(no)} page(s) use nosnippet.",
            "Normal snippets and Google AI direct input are suppressed.",
            "Confirm the business trade-off; do not remove automatically.",
            "Review directive and search presentation.",
            no,
            "SEO Compliance & Legal Agent",
        )
    if mx:
        self.add(
            "maxsnippet-tradeoff",
            "Pages cap snippet and Google AI direct-input length",
            "Info",
            "AI Extraction Controls",
            ["max-snippet-ai-input"],
            f"{len(mx)} page(s) use max-snippet.",
            "The cap can limit extraction and normal presentation.",
            "Document rationale and test approved changes.",
            "Compare search presentation.",
            mx,
            "SEO Compliance & Legal Agent",
        )


def _image_hints(self: RuleContext, p: list[PageEvidence]) -> None:
    lazy = []
    dims = []
    for x in p:
        for im in x.get("images", [])[:2]:
            if str(im.get("loading") or "").lower() == "lazy":
                lazy.append(x["final_url"])
            if not im.get("width") or not im.get("height"):
                dims.append(x["final_url"])
    if lazy:
        self.add(
            "likely-lcp-lazy",
            "Early page images are lazy-loaded and may include the LCP element",
            "High",
            "Core Web Vitals",
            ["lcp-no-lazy", "lcp-subparts"],
            f"{len(set(lazy))} page(s) lazy-load an early image.",
            "If it is LCP, lazy loading adds resource delay.",
            "Confirm LCP and remove lazy loading only when verified.",
            "Measure LCP subparts.",
            lazy,
            "SEO Diagnostic Infrastructure Agent",
            "STRONGLY_SUPPORTED",
            "Medium",
            ["Actual browser-measured LCP element"],
        )
    if dims:
        self.add(
            "image-dimensions",
            "Early images lack explicit dimensions",
            "Medium",
            "Core Web Vitals",
            ["cwv-thresholds"],
            f"{len(set(dims))} page(s) lack image dimensions.",
            "Missing reserved space can contribute to CLS.",
            "Provide dimensions or aspect-ratio reservation.",
            "Measure CLS.",
            dims,
            "SEO Diagnostic Infrastructure Agent",
        )


def _facet_evidence(self: RuleContext, p: list[PageEvidence]) -> None:
    facets = [x for x in p if self.facet(x["final_url"])]
    empty = [x for x in facets if 200 <= x["status_code"] < 300 and x.get("soft_404_signal")]
    if empty:
        self.add(
            "facet-empty-200",
            "Empty faceted combinations return successful responses",
            "High",
            "Faceted Navigation",
            ["facets-empty-404", "soft-404"],
            f"{len(empty)} empty-looking facets return 2xx.",
            "Low-value URL spaces can expand.",
            "Return genuine 404 for empty combinations.",
            "Test representative combinations.",
            [x["final_url"] for x in empty],
            "SEO E-commerce Agent",
        )
    orders = defaultdict(list)
    for x in facets:
        ks = tuple(
            k.lower()
            for k, _ in urllib.parse.parse_qsl(urllib.parse.urlsplit(x["final_url"]).query)
        )
        orders[tuple(sorted(ks))].append("&".join(ks))
    if any(len(set(v)) > 1 for v in orders.values()):
        self.add(
            "facet-order-inconsistent",
            "Equivalent facet parameters appear in inconsistent orders",
            "Medium",
            "Faceted Navigation",
            ["facets-parameter-separator"],
            "Equivalent parameter sets have multiple orders.",
            "Duplicate URL forms can expand inventory.",
            "Normalize order and duplicate filters.",
            "Regenerate facet inventory.",
            [x["final_url"] for x in facets],
            "SEO E-commerce Agent",
        )


def ai_cwv_facets(self: RuleContext, c: CrawlEvidence) -> None:
    p = c["pages"]
    _snippet_controls(self, p)
    _image_hints(self, p)
    _facet_evidence(self, p)
    n = len(p)
    self.decisions.append(
        {
            "decision": "crawl_budget_materiality",
            "status": "NOT_DEMONSTRATED" if n < 10000 else "REQUIRES_SCALE_REVIEW",
            "observed_crawl_size": n,
            "claim_id": "crawl-budget-scale",
            "interpretation": "This bounded crawl does not establish a material crawl-budget constraint."
            if n < 10000
            else "Separate large-site review is warranted.",
        }
    )
