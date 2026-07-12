from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


SEVERITY_WEIGHT = {"Critical": 5, "High": 4, "Medium": 3, "Low": 2, "Info": 1}


def trust_summary(crawl: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    findings = result["findings"]
    verified = sum(row["evidence_state"] in {"VERIFIED", "STRONGLY_SUPPORTED"} for row in findings)
    inferred = sum(row["evidence_state"] not in {"VERIFIED", "STRONGLY_SUPPORTED", "REQUIRES_VERIFICATION"} for row in findings)
    unsupported = sum(row["evidence_state"] == "REQUIRES_VERIFICATION" for row in findings)
    attempts = len(crawl["pages"]) + len(crawl["failed_fetches"])
    return {
        "checks_attempted": attempts,
        "pages_completed": len(crawl["pages"]),
        "fetches_failed": len(crawl["failed_fetches"]),
        "robots_hosts_checked": len(crawl["robots"]),
        "verified_or_strongly_supported_findings": verified,
        "inferred_findings": inferred,
        "unsupported_material_findings": unsupported,
        "evidence_integrity": "HASHED_IN_RUN_MANIFEST",
        "external_changes_made": "NONE",
        "crawl_truncated": crawl["truncated"],
    }


def _priority(row: dict[str, Any]) -> int:
    return SEVERITY_WEIGHT.get(row["severity"], 0)


def executive_markdown(target: str, result: dict[str, Any], trust: dict[str, Any]) -> str:
    findings = result["findings"]
    critical = [row for row in findings if row["severity"] == "Critical"]
    high = [row for row in findings if row["severity"] == "High"]
    top = sorted(findings, key=_priority, reverse=True)[:8]
    lines = [
        "# Executive Technical SEO Summary",
        "",
        f"**Target:** {target}",
        "",
        "## Outcome",
        "",
        f"The bounded audit identified **{len(findings)} consolidated finding(s)**, including **{len(critical)} critical** and **{len(high)} high-priority** item(s).",
        "",
        "No external changes were made. Findings labeled as missing or requiring verification were not converted into successful-looking conclusions.",
        "",
        "## Highest-priority actions",
        "",
    ]
    if not top:
        lines.append("No material finding was produced from the available evidence. This is not proof that the site has no SEO issues.")
    for row in top:
        lines.extend([f"### {row['severity']}: {row['title']}", "", row["business_impact"], "", f"**Action:** {row['recommended_action']}", ""])
    lines.extend([
        "## Audit trust summary", "",
        f"- Checks attempted: {trust['checks_attempted']}",
        f"- Pages completed: {trust['pages_completed']}",
        f"- Failed fetches: {trust['fetches_failed']}",
        f"- Robots hostnames checked: {trust['robots_hosts_checked']}",
        f"- Verified or strongly supported findings: {trust['verified_or_strongly_supported_findings']}",
        f"- Unsupported material findings: {trust['unsupported_material_findings']}",
        f"- External changes made: {trust['external_changes_made']}",
    ])
    return "\n".join(lines) + "\n"


def technical_markdown(target: str, crawl: dict[str, Any], result: dict[str, Any], trust: dict[str, Any]) -> str:
    lines = [
        "# Evidence-Governed Technical SEO Audit", "", f"**Target:** {target}",
        f"**Pages crawled:** {len(crawl['pages'])}", f"**Crawl truncated:** {crawl['truncated']}", "",
        "## Evidence contract", "",
        "- Primary-source rules override conflicting secondary guidance.",
        "- A successful HTTP response is not described as proof of indexing or ranking.",
        "- Fixture and static checks do not prove live provider behavior.",
        "- Missing evidence remains missing.",
        "- No external mutation is performed by this audit.", "", "## Findings", "",
    ]
    if not result["findings"]:
        lines.append("No material finding was produced from the bounded evidence. This is not a clean-site certification.")
    for row in result["findings"]:
        lines.extend([
            f"### [{row['severity']}] {row['title']}", "",
            f"- **Finding ID:** `{row['id']}`", f"- **Category:** {row['category']}",
            f"- **Evidence:** {row['evidence_state']} / {row['evidence_class']}",
            f"- **Claim IDs:** {', '.join(row['claim_ids']) or 'None'}", f"- **Owner:** {row['owner']}",
            f"- **Observed:** {row['observed']}", f"- **Business impact:** {row['business_impact']}",
            f"- **Recommended action:** {row['recommended_action']}", f"- **Verification:** {row['verification']}",
            f"- **Affected URL count:** {len(row['affected_urls'])}",
        ])
        if row["missing_evidence"]:
            lines.append(f"- **Missing evidence:** {'; '.join(row['missing_evidence'])}")
        lines.append("")
    lines.extend(["## Decisions", ""])
    for decision in result["decisions"]:
        lines.append(f"- `{decision['decision']}`: {decision.get('interpretation', '')}")
    lines.extend(["", "## Root-cause groups", ""])
    for group in result["root_cause_groups"]:
        lines.append(f"- **{group['category']}**: {group['finding_count']} finding(s) ({', '.join(group['finding_ids'])})")
    lines.extend(["", "## Trust summary", "", "```json", json.dumps(trust, indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["finding_id", "severity", "category", "title", "owner", "recommended_action", "verification", "affected_url_count"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "finding_id": row["id"], "severity": row["severity"], "category": row["category"],
                "title": row["title"], "owner": row["owner"], "recommended_action": row["recommended_action"],
                "verification": row["verification"], "affected_url_count": len(row["affected_urls"]),
            })
