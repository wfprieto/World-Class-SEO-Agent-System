"""Primary-source-bound technical audit rules."""

from __future__ import annotations

import json
import re
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

from integrations.product_proof.canonical_rules import canon as apply_canon
from integrations.product_proof.extraction_rules import ai_cwv_facets as apply_ai_cwv_facets
from integrations.product_proof.models import AgentContribution, Finding
from integrations.product_proof.robots_rules import robots as apply_robots
from integrations.product_proof.rule_groups import apply_technical_rule_groups
from integrations.product_proof.rule_types import (
    ClaimEvidence,
    CrawlEvidence,
    PageEvidence,
    RuleEvaluation,
)

SEV = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}
PAGE = {"page", "paged", "pagenum", "page_num", "pg"}
FACET = {
    "color",
    "size",
    "brand",
    "price",
    "sort",
    "order",
    "filter",
    "material",
    "style",
    "category",
    "availability",
}


class ClaimPolicy:
    def __init__(self, path: str | Path) -> None:
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        self.claims: dict[str, ClaimEvidence] = {r["id"]: r for r in raw["claims"]}
        self.allowed = set(raw["recommendation_classes"])
        self.order = [
            "PRIMARY_SOURCE",
            "CONTROLLED_EXPERIMENT",
            "LARGE_SCALE_OBSERVATIONAL",
            "PRACTITIONER_CONSENSUS",
            "EXPERT_HYPOTHESIS",
            "ANALYSIS",
            "UNVERIFIED",
            "DISPUTED",
            "STALE",
            "FALSE",
        ]

    def claim(self, c: str) -> ClaimEvidence:
        if c not in self.claims:
            raise KeyError(f"unknown SEO claim: {c}")
        return self.claims[c]

    def strongest_class(self, ids: list[str]) -> str:
        kinds = {self.claim(c)["evidence_class"] for c in ids}
        return min(kinds, key=self.order.index) if kinds else "ANALYSIS"

    def approved_for_recommendation(self, ids: list[str]) -> bool:
        return all(self.claim(c)["evidence_class"] in self.allowed for c in ids)


def _status_pages(p: list[PageEvidence]) -> tuple[
    list[PageEvidence], list[PageEvidence], list[PageEvidence], list[PageEvidence],
]:
    err = [x for x in p if x["status_code"] == 429 or x["status_code"] >= 500]
    miss = [x for x in p if x["status_code"] in {404, 410}]
    soft = [x for x in p if x.get("soft_404_signal")]
    red = [x for x in p if x["requested_url"] != x["final_url"]]
    return err, miss, soft, red


class TechnicalAuditRules:
    def __init__(self, policy: ClaimPolicy) -> None:
        self.policy = policy
        self.findings: list[Finding] = []
        self.decisions: list[dict[str, str | int]] = []
        self.counts: Counter[str] = Counter()

    def add(
        self,
        i: str,
        t: str,
        s: str,
        cat: str,
        claims: list[str],
        obs: str,
        impact: str,
        action: str,
        verify: str,
        urls: list[str],
        owner: str,
        state: str = "VERIFIED",
        confidence: str = "High",
        missing: list[str] | None = None,
    ) -> None:
        self.counts[i] += 1
        fid = i if self.counts[i] == 1 else f"{i}-{self.counts[i]}"
        if claims and not self.policy.approved_for_recommendation(claims):
            state, confidence = "REQUIRES_VERIFICATION", "Low"
        self.findings.append(
            Finding(
                fid,
                t,
                s,
                cat,
                state,
                self.policy.strongest_class(claims),
                claims,
                obs,
                impact,
                action,
                verify,
                sorted(set(urls))[:200],
                owner,
                confidence,
                missing_evidence=missing or [],
            )
        )

    @staticmethod
    def dirs(p: PageEvidence) -> set[str]:
        v = set(p.get("meta_robots", []))
        v.update(
            x.strip().lower() for x in str(p.get("x_robots_tag") or "").split(",") if x.strip()
        )
        return v

    @staticmethod
    def paged(u: str) -> bool:
        p = urllib.parse.urlsplit(u)
        return any(k.lower() in PAGE for k in urllib.parse.parse_qs(p.query)) or bool(
            re.search(r"/(?:page|p)/\d+/?$", p.path, re.I)
        )

    @staticmethod
    def page1(u: str) -> str:
        p = urllib.parse.urlsplit(u)
        q = [
            (k, v)
            for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
            if k.lower() not in PAGE
        ]
        path = re.sub(r"/(?:page|p)/\d+/?$", "/", p.path, flags=re.I)
        return urllib.parse.urlunsplit(
            (p.scheme, p.netloc, path, urllib.parse.urlencode(q), "")
        ).rstrip("?")

    @staticmethod
    def facet(u: str) -> bool:
        return any(
            k.lower() in FACET for k in urllib.parse.parse_qs(urllib.parse.urlsplit(u).query)
        )

    def robots(self, c: CrawlEvidence) -> None:
        apply_robots(self, c)

    def statuses(self, c: CrawlEvidence) -> None:
        p = c["pages"]
        err, miss, soft, red = _status_pages(p)
        if err:
            self.add(
                "server-errors",
                "Crawled URLs return server-overload or server-error responses",
                "Critical",
                "Availability",
                ["http-429-server-signal"],
                f"{len(err)} URL(s) returned 429/5xx.",
                "Persistent failures can reduce crawling and index retention.",
                "Resolve capacity, application, proxy, or origin failures.",
                "Recrawl and monitor.",
                [x["final_url"] for x in err],
                "SEO Diagnostic Infrastructure Agent",
            )
        if miss:
            self.add(
                "missing-linked-pages",
                "The crawl discovered URLs that return 404 or 410",
                "High",
                "Internal Links",
                ["http-404-410"],
                f"{len(miss)} URL(s) return 404/410.",
                "Important retired URLs can lose traffic/links; internal links create dead ends.",
                "Keep genuine removals, redirect only to equivalents, and update internal links.",
                "Recrawl and verify references.",
                [x["final_url"] for x in miss],
                "SEO Information Architecture Agent",
            )
        if soft:
            self.add(
                "soft-404",
                "Successful responses contain missing or near-empty page signals",
                "High",
                "Index Quality",
                ["soft-404"],
                f"{len(soft)} 2xx page(s) appear missing/empty.",
                "Soft 404s create misleading index states.",
                "Return genuine 404/410 or restore content.",
                "Verify status/content and Search Console.",
                [x["final_url"] for x in soft],
                "SEO Technical Agent",
            )
        if red:
            self.add(
                "internal-redirects",
                "The crawl followed internally discovered redirecting URLs",
                "Medium",
                "Internal Links",
                ["http-redirect-signals"],
                f"{len(red)} URL(s) redirected.",
                "Redirects add latency and obscure preferred URLs.",
                "Update internal links to final destinations.",
                "Recrawl for direct links.",
                [x["requested_url"] for x in red],
                "SEO Information Architecture Agent",
            )

    def canon(self, c: CrawlEvidence) -> None:
        apply_canon(self, c)

    def ai_cwv_facets(self, c: CrawlEvidence) -> None:
        apply_ai_cwv_facets(self, c)

    def evaluate(self, c: CrawlEvidence) -> RuleEvaluation:
        apply_technical_rule_groups(self, c)
        self.findings.sort(key=lambda x: (SEV[x.severity], x.category, x.id))
        g = defaultdict(list)
        for f in self.findings:
            g[f.category].append(f.id)
        return {
            "findings": [f.to_dict() for f in self.findings],
            "decisions": self.decisions,
            "root_cause_groups": [
                {"category": k, "finding_ids": v, "finding_count": len(v)}
                for k, v in sorted(g.items())
            ],
        }


def _collection_contributions(c: CrawlEvidence, r: RuleEvaluation, o: Counter[str], e: int) -> list[AgentContribution]:
    return [
        AgentContribution(
            "SEO Diagnostic Infrastructure Agent",
            "bounded collection and performance evidence",
            e,
            o["SEO Diagnostic Infrastructure Agent"],
            o["SEO Diagnostic Infrastructure Agent"],
            0,
            0,
            0,
            "Created the canonical crawl dataset and isolated transport failures.",
        ),
        AgentContribution(
            "SEO Technical Agent",
            "crawl, status, canonical and robots rules",
            len(c["pages"]),
            o["SEO Technical Agent"],
            o["SEO Technical Agent"],
            0,
            0,
            len(r["decisions"]),
            "Applied primary-source rules without index or ranking assumptions.",
        ),
        AgentContribution(
            "SEO Information Architecture Agent",
            "internal graph and pagination",
            sum(len(x["internal_links"]) for x in c["pages"]),
            o["SEO Information Architecture Agent"],
            o["SEO Information Architecture Agent"],
            0,
            0,
            0,
            "Connected URL symptoms into graph and pagination root causes.",
        ),
        AgentContribution(
            "SEO Compliance & Legal Agent",
            "AI extraction trade-off review",
            sum(1 for x in c["pages"] if x["meta_robots"] or x["x_robots_tag"]),
            o["SEO Compliance & Legal Agent"],
            o["SEO Compliance & Legal Agent"],
            0,
            0,
            0,
            "Kept extraction controls approval-gated.",
        ),
    ]


def _decision_contributions(r: RuleEvaluation) -> list[AgentContribution]:
    f = r["findings"]
    return [
        AgentContribution(
            "SEO Full Audit/Analyst Agent",
            "root-cause consolidation",
            len(f),
            len(f),
            len(f),
            max(len(f) - len(r["root_cause_groups"]), 0),
            0,
            len(r["decisions"]),
            "Consolidated symptoms into client-actionable root causes.",
        ),
        AgentContribution(
            "SEO Scrummaster Agent",
            "evidence challenge gate",
            0,
            0,
            sum(x["evidence_state"] != "REQUIRES_VERIFICATION" for x in f),
            0,
            sum(x["evidence_state"] == "REQUIRES_VERIFICATION" for x in f),
            len(r["decisions"]),
            "Blocked unsupported claims and retained open evidence gaps.",
        ),
        AgentContribution(
            "SEO Output Report Agent",
            "client and engineering deliverables",
            len(f),
            0,
            len(f),
            0,
            0,
            0,
            "Translated evidence into impact, ownership, and verification instructions.",
        ),
    ]


def build_contributions(c: CrawlEvidence, r: RuleEvaluation) -> list[dict[str, object]]:
    f = r["findings"]
    o = Counter(x["owner"] for x in f)
    e = len(c["pages"]) + len(c["robots"])
    rows = _collection_contributions(c, r, o, e) + _decision_contributions(r)

    return [x.to_dict() for x in rows]
