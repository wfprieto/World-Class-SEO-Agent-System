"""Robots response diagnostics and blocked-resource evidence."""
from __future__ import annotations

import urllib.parse

from integrations.product_proof.crawler import RobotsPolicy
from integrations.product_proof.rule_types import (
    CrawlEvidence,
    RobotsEvidence,
    RuleContext,
)


def _response_findings(self: RuleContext, r: RobotsEvidence) -> None:
    if r["errors"]:
        self.add(
            "robots-fetch-failed",
            "robots.txt could not be evaluated",
            "High",
            "Crawl Access",
            ["robots-scope", "robots-5xx"],
            "; ".join(r["errors"]),
            "Crawler controls are unknown.",
            "Restore a deterministic response.",
            f"Fetch {r['robots_url']} and record status/body.",
            [r["robots_url"]],
            "SEO Diagnostic Infrastructure Agent",
            "MISSING",
            "Low",
            ["robots.txt response"],
        )
        return
    st = int(r["status_code"])
    if st == 429 or st >= 500:
        self.add(
            "robots-server-error",
            "robots.txt returns a server-error response",
            "Critical",
            "Crawl Access",
            ["robots-5xx"],
            f"{r['robots_url']} returned HTTP {st}.",
            "Google can pause crawling or use cached/fallback behavior; asset resources can become ineligible.",
            "Return stable 200 rules or genuine 404.",
            "Confirm stable 200/404.",
            [r["robots_url"]],
            "SEO Technical Agent",
        )
    elif 400 <= st < 500 and st != 429:
        self.decisions.append(
            {
                "decision": "robots_4xx_no_restrictions",
                "host": r["host"],
                "status_code": st,
                "claim_id": "robots-4xx",
                "interpretation": "Google treats this as no robots restrictions.",
            }
        )
    if r["size_bytes"] > 500 * 1024:
        self.add(
            "robots-too-large",
            "robots.txt exceeds Google's processing ceiling",
            "High",
            "Crawl Access",
            ["robots-file-limit"],
            f"{r['size_bytes']} bytes.",
            "Rules after the ceiling can be ignored.",
            "Reduce below 500 KiB.",
            "Refetch and verify size.",
            [r["robots_url"]],
            "SEO Technical Agent",
        )


def _unsupported_directives(self: RuleContext, r: RobotsEvidence) -> None:
    for u in r["unknown_directives"]:
        f = u.split(":", 1)[0].strip().lower()
        if f == "crawl-delay":
            self.add(
                "robots-crawl-delay",
                "robots.txt uses crawl-delay for Google",
                "Medium",
                "Crawl Access",
                ["robots-crawl-delay-unsupported"],
                u,
                "The directive does not control Googlebot.",
                "Remove reliance on crawl-delay.",
                "Reparse robots.txt.",
                [r["robots_url"]],
                "SEO Technical Agent",
            )
        if f == "noindex":
            self.add(
                "robots-noindex",
                "robots.txt contains an unsupported noindex directive",
                "High",
                "Indexability",
                ["robots-disallow-not-noindex"],
                u,
                "The index-control instruction is inert.",
                "Use crawlable meta robots or X-Robots-Tag.",
                "Inspect crawl access and page response.",
                [r["robots_url"]],
                "SEO Technical Agent",
            )


def _blocked_evidence(self: RuleContext, c: CrawlEvidence, root: urllib.parse.SplitResult, rr: RobotsEvidence | None) -> None:
    pages = c["pages"]
    if not rr or rr["status_code"] >= 400:
        return
    pol = RobotsPolicy(rr["groups"])
    blocked = [p for p in pages if not pol.allowed(p["final_url"])]
    ni = [p for p in blocked if "noindex" in self.dirs(p)]
    if ni:
        self.add(
            "noindex-blocked-by-robots",
            "Pages carry noindex instructions that Google may be unable to read",
            "Critical",
            "Indexability",
            ["robots-disallow-not-noindex"],
            f"{len(ni)} disallowed page(s) carry noindex.",
            "Blocking can make deindexing instructions unreadable.",
            "Allow crawl access when noindex is intended.",
            "Test robots and page directives.",
            [p["final_url"] for p in ni],
            "SEO Technical Agent",
        )
    assets = [
        a
        for p in pages
        for a in p.get("asset_urls", [])
        if urllib.parse.urlsplit(a).netloc == root.netloc and not pol.allowed(a)
    ]
    if assets:
        self.add(
            "blocked-render-assets",
            "robots.txt blocks same-host rendering assets",
            "High",
            "Rendering",
            ["robots-disallow-not-noindex"],
            f"{len(set(assets))} asset URL(s) blocked.",
            "Pages may render incompletely.",
            "Allow required rendering resources.",
            "Render representative pages.",
            assets,
            "SEO Diagnostic Infrastructure Agent",
        )


def robots(self: RuleContext, c: CrawlEvidence) -> None:
    root = urllib.parse.urlsplit(c["start_url"])
    rr = None
    for r in c["robots"]:
        if r["host"] == root.netloc:
            rr = r
        _response_findings(self, r)
        if not r["errors"]:
            _unsupported_directives(self, r)
    _blocked_evidence(self, c, root, rr)
