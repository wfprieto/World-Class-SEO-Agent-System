"""One-command evidence-governed technical SEO product proof."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable

from adapters.base import AdapterResult
from adapters.url_safety import validate_public_url
from integrations.product_proof.crawler import SiteCrawler
from integrations.product_proof.models import CrawlConfig
from integrations.product_proof.report import executive_markdown, technical_markdown, trust_summary, write_csv
from integrations.product_proof.rules import ClaimPolicy, TechnicalAuditRules, build_contributions
from integrations.technical.http import HttpHop
from runtime.assets import resolve_asset_root

ROOT = resolve_asset_root(Path(__file__).resolve().parents[2])


class FixtureHttpClient:
    """Exact-response fixture transport. Fixture success is never called live proof."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.responses = payload.get("responses", payload)
        if not isinstance(self.responses, dict):
            raise ValueError("fixture must contain an object of URL responses")

    def get(self, url: str, **_: Any) -> HttpHop:
        if url not in self.responses:
            raise FileNotFoundError(f"fixture has no response for {url}")
        row = self.responses[url]
        body = row.get("body", "")
        if isinstance(body, str):
            encoded = body.encode("utf-8")
        elif isinstance(body, list):
            encoded = bytes(body)
        else:
            raise TypeError("fixture body must be text or a byte list")
        return HttpHop(
            requested_url=url,
            final_url=str(row.get("final_url") or url),
            status_code=int(row.get("status_code", 200)),
            headers={str(k): str(v) for k, v in row.get("headers", {}).items()},
            body=encoded,
            elapsed_ms=int(row.get("elapsed_ms", 1)),
        )


def _fixture_validator(url: str) -> str:
    from urllib.parse import urlsplit, urlunsplit
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("fixture URL must use http or https and include a host")
    if parsed.username or parsed.password:
        raise ValueError("fixture URL cannot contain credentials")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


class ProductProofTechnicalAudit:
    name = "product_proof_technical_audit"

    def __init__(self, *, claim_registry: str | Path | None = None, crawler_factory: Callable[..., SiteCrawler] = SiteCrawler) -> None:
        self.claim_registry = Path(claim_registry or ROOT / "knowledge" / "seo-claim-registry.json")
        self.crawler_factory = crawler_factory

    @staticmethod
    def _json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def run(self, *, url: str, output_dir: str | Path, fixture_path: str | Path | None = None, max_urls: int = 500, max_depth: int = 6, max_asset_hosts: int = 10) -> AdapterResult:
        config = CrawlConfig(max_urls=max_urls, max_depth=max_depth, max_asset_hosts=max_asset_hosts)
        fixture = Path(fixture_path).resolve() if fixture_path else None
        if fixture:
            http = FixtureHttpClient(self._json(fixture))
            validator = _fixture_validator
            evidence_mode = "FIXTURE"
            safe_url = validator(url)
        else:
            http = None
            validator = validate_public_url
            evidence_mode = "LIVE_BOUNDED"
            safe_url = validator(url)
        crawler = self.crawler_factory(config=config, http=http, url_validator=validator)
        started = time.monotonic()
        crawl = crawler.crawl(safe_url)
        policy = ClaimPolicy(self.claim_registry)
        evaluated = TechnicalAuditRules(policy).evaluate(crawl)
        contributions = build_contributions(crawl, evaluated)
        trust = trust_summary(crawl, evaluated)
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        run_seed = json.dumps({"url": safe_url, "config": config.to_dict(), "evidence_mode": evidence_mode}, sort_keys=True)
        run_id = hashlib.sha256(run_seed.encode("utf-8")).hexdigest()[:16]
        artifacts = {
            "crawl": output / "crawl.json",
            "findings": output / "findings.json",
            "decisions": output / "decisions.json",
            "contributions": output / "agent-contributions.json",
            "trust": output / "trust-summary.json",
            "technical_report": output / "technical-audit.md",
            "executive_report": output / "executive-summary.md",
            "remediation": output / "remediation-plan.csv",
            "verification": output / "verification-plan.json",
            "manifest": output / "run-manifest.json",
        }
        self._write_json(artifacts["crawl"], crawl)
        self._write_json(artifacts["findings"], evaluated["findings"])
        self._write_json(artifacts["decisions"], evaluated["decisions"])
        self._write_json(artifacts["contributions"], contributions)
        self._write_json(artifacts["trust"], trust)
        artifacts["technical_report"].write_text(technical_markdown(safe_url, crawl, evaluated, trust), encoding="utf-8")
        artifacts["executive_report"].write_text(executive_markdown(safe_url, evaluated, trust), encoding="utf-8")
        write_csv(artifacts["remediation"], evaluated["findings"])
        self._write_json(artifacts["verification"], [{"finding_id": row["id"], "verification": row["verification"], "owner": row["owner"], "status": "OPEN"} for row in evaluated["findings"]])
        digests = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in artifacts.items() if name != "manifest" and path.exists()}
        manifest = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "target": safe_url,
            "evidence_mode": evidence_mode,
            "fixture_is_live_proof": False if fixture else None,
            "config": config.to_dict(),
            "claim_registry": str(self.claim_registry),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "artifacts": {name: str(path) for name, path in artifacts.items()},
            "sha256": digests,
            "external_changes_made": False,
            "multi_agent_contribution": {"agents_executed": len(contributions), "agents": [row["agent"] for row in contributions], "handoffs_consumed": max(len(contributions) - 1, 0), "decisions_recorded": len(evaluated["decisions"]), "contribution_records": len(contributions)},
        }
        self._write_json(artifacts["manifest"], manifest)
        warnings = []
        if crawl["truncated"]:
            warnings.append("Crawl reached a configured ceiling; uncrawled URLs remain unknown.")
        if crawl["failed_fetches"]:
            warnings.append(f"{len(crawl['failed_fetches'])} URL fetch(es) failed and remain missing evidence.")
        if fixture:
            warnings.append("Fixture execution verifies contracts only and is not live-site proof.")
        status = "complete" if crawl["pages"] and not crawl["truncated"] else "partial"
        return AdapterResult(source=self.name, status=status, data={
            "state": "AVAILABLE" if crawl["pages"] else "EMPTY",
            "run_id": run_id,
            "target": safe_url,
            "evidence_mode": evidence_mode,
            "pages_crawled": len(crawl["pages"]),
            "findings": len(evaluated["findings"]),
            "critical_findings": sum(row["severity"] == "Critical" for row in evaluated["findings"]),
            "agents_executed": len(contributions),
            "artifacts": {name: str(path) for name, path in artifacts.items()},
            "trust_summary": trust,
            "limitations": [
                "A bounded crawl cannot prove search-engine indexing, rankings, conversions, or complete site coverage.",
                "Static source checks do not replace field Core Web Vitals, browser traces, Search Console, analytics, logs, or expert review.",
                "No external mutation is performed.",
            ],
        }, warnings=warnings)
