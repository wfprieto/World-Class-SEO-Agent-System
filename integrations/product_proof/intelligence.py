"""Offline-safe SEO intelligence analyzers derived from the governed source corpus."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from adapters.base import AdapterResult

_COMMON_LOG = re.compile(r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[[^\]]+\]\s+"(?P<method>\S+)\s+(?P<path>\S+)\s+[^\"]+"\s+(?P<status>\d{3})\s+(?P<bytes>\S+)(?:\s+"[^\"]*"\s+"(?P<ua>[^\"]*)")?')
_RESPONSE_TIME = re.compile(r'(?:request_time|rt|response_time)[=:](?P<seconds>\d+(?:\.\d+)?)')
AI_USER_AGENTS = {
    "OpenAI on-demand retrieval": ("chatgpt-user", "oai-searchbot"),
    "OpenAI training": ("gptbot",),
    "Anthropic": ("claudebot",),
    "Perplexity": ("perplexitybot", "perplexity-user"),
    "Google extended use control": ("google-extended",),
    "Apple extended": ("applebot-extended",),
    "Common Crawl": ("ccbot",),
    "Meta external": ("meta-externalagent",),
}


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _classify_ua(user_agent: str) -> str | None:
    lowered = user_agent.lower()
    for label, tokens in AI_USER_AGENTS.items():
        if any(token in lowered for token in tokens):
            return label
    return None


@dataclass(frozen=True)
class TimeoutRecord:
    line: int
    bot_family: str
    status: int
    path: str
    response_seconds: float | None


class AITimeoutAnalyzer:
    name = "ai_timeout_analysis"

    def analyze(self, *, log_path: str | Path, server_stack: str) -> AdapterResult:
        stack = server_stack.strip().lower()
        if not stack:
            raise ValueError("server_stack is required because 499 is server-specific evidence")
        records: list[TimeoutRecord] = []
        ai_requests: Counter[str] = Counter()
        statuses: Counter[tuple[str, int]] = Counter()
        path_counts: Counter[str] = Counter()
        response_samples: dict[str, list[float]] = defaultdict(list)
        malformed = 0
        text = Path(log_path).read_text(encoding="utf-8-sig", errors="replace")
        for line_number, raw in enumerate(text.splitlines(), 1):
            match = _COMMON_LOG.search(raw)
            if not match:
                malformed += 1; continue
            family = _classify_ua(match.group("ua") or "")
            if not family: continue
            status = int(match.group("status")); path = match.group("path")
            time_match = _RESPONSE_TIME.search(raw); seconds = float(time_match.group("seconds")) if time_match else None
            ai_requests[family] += 1; statuses[(family, status)] += 1; path_counts[path] += 1
            if seconds is not None: response_samples[family].append(seconds)
            if status == 499: records.append(TimeoutRecord(line_number, family, status, path, seconds))
        total_ai = sum(ai_requests.values()); timeout_count = len(records); warnings: list[str] = []
        if stack not in {"nginx", "openresty", "ingress-nginx", "unknown-nginx-compatible"}:
            warnings.append("HTTP 499 is an nginx-family convention. Confirm the server or proxy's status semantics before interpreting it as a client-closed request.")
        if total_ai == 0: warnings.append("No recognized AI crawler or user-triggered fetcher requests were found in the supplied log.")
        medians: dict[str, float] = {}
        for family, samples in response_samples.items():
            ordered = sorted(samples); mid = len(ordered) // 2
            medians[family] = round(ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2, 4)
        data = {
            "operation": "ai_timeouts", "server_stack": server_stack, "ai_requests": total_ai,
            "timeout_499_count": timeout_count, "timeout_rate": round(timeout_count / total_ai, 4) if total_ai else None,
            "by_bot_family": dict(sorted(ai_requests.items())),
            "status_counts": [{"bot_family": family, "status": status, "count": count} for (family, status), count in sorted(statuses.items())],
            "median_response_seconds": medians,
            "top_paths": [{"path": path, "count": count} for path, count in path_counts.most_common(20)],
            "timeouts": [asdict(record) for record in records[:1000]], "truncated": timeout_count > 1000,
            "malformed_lines": malformed, "evidence_class": "OBSERVED_OPERATOR_SUPPLIED",
            "limitations": [
                "A 499 is not part of the HTTP standard and must be interpreted in the context of the actual server or proxy.",
                "User-agent strings can be spoofed. This analysis does not verify source IP ownership.",
                "A timeout correlation does not prove that a search or AI system excluded the URL from an answer.",
            ],
        }
        return AdapterResult(source=self.name, status="ok" if total_ai else "empty", data=data, warnings=warnings)


class AICitationOpportunityAnalyzer:
    name = "ai_citation_opportunity"
    REQUIRED = {"observed_at", "platform", "prompt", "aio_present", "organic_position", "cited"}

    def analyze(self, *, observations_path: str | Path) -> AdapterResult:
        payload = _read_json(observations_path); rows = payload.get("observations", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list): raise ValueError("observations must be a list or an object containing observations")
        normalized: list[dict[str, Any]] = []; errors: list[str] = []
        for index, raw in enumerate(rows):
            if not isinstance(raw, dict): errors.append(f"observation {index} must be an object"); continue
            missing = sorted(self.REQUIRED - set(raw))
            if missing: errors.append(f"observation {index} missing: {', '.join(missing)}"); continue
            try: position = float(raw["organic_position"]) if raw["organic_position"] is not None else None
            except (TypeError, ValueError): errors.append(f"observation {index} organic_position must be numeric or null"); continue
            normalized.append({
                "observed_at": str(raw["observed_at"]), "platform": str(raw["platform"]), "prompt": str(raw["prompt"]),
                "aio_present": bool(raw["aio_present"]), "organic_position": position, "cited": bool(raw["cited"]),
                "citation_order": raw.get("citation_order"), "recommendation_state": str(raw.get("recommendation_state", "UNKNOWN")),
                "linked": bool(raw.get("linked", False)), "destination_url": raw.get("destination_url"),
                "narrative_accuracy": str(raw.get("narrative_accuracy", "NOT_REVIEWED")), "source_mix": str(raw.get("source_mix", "UNKNOWN")),
                "competitors_cited": [str(item) for item in raw.get("competitors_cited", [])],
                "evidence_source": str(raw.get("evidence_source", "operator_observation")),
            })
        if errors: raise ValueError("; ".join(errors[:20]))
        opportunities = [row for row in normalized if row["aio_present"] and row["organic_position"] is not None and row["organic_position"] <= 10 and not row["cited"]]
        inaccurate = [row for row in normalized if row["narrative_accuracy"] in {"INACCURATE", "MISLEADING"}]
        cited = [row for row in normalized if row["cited"]]; recommended = [row for row in cited if row["recommendation_state"] == "RECOMMENDED"]; linked = [row for row in cited if row["linked"]]
        data = {
            "operation": "ai_citation_opportunities", "observation_count": len(normalized),
            "platforms": dict(sorted(Counter(row["platform"] for row in normalized).items())),
            "prompt_coverage": round(len(cited) / len(normalized), 4) if normalized else None,
            "recommendation_rate": round(len(recommended) / len(normalized), 4) if normalized else None,
            "linked_citation_rate": round(len(linked) / len(cited), 4) if cited else None,
            "unowned_ai_overview_opportunities": opportunities, "unowned_count": len(opportunities),
            "representation_risks": inaccurate, "representation_risk_count": len(inaccurate), "observed": normalized,
            "evidence_layer": "OBSERVED",
            "limitations": [
                "Results are dated snapshots and can vary by account, location, device, prompt wording, and platform state.",
                "Organic position and AI citation are separate observations; one does not prove the cause of the other.",
                "No modeled reach or revenue is blended into these observed metrics.",
            ],
        }
        return AdapterResult(self.name, "ok" if normalized else "empty", data, [] if normalized else ["No dated observations were supplied."])


class ReviewComplianceAnalyzer:
    name = "review_compliance"

    def analyze(self, *, input_path: str | Path) -> AdapterResult:
        payload = _read_json(input_path)
        if not isinstance(payload, dict): raise ValueError("review input must be an object")
        practices = payload.get("practices", payload); findings: list[dict[str, Any]] = []
        def add(code: str, severity: str, title: str, action: str, evidence: str) -> None:
            findings.append({"code": code, "severity": severity, "title": title, "recommended_action": action, "observed_evidence": evidence, "evidence_class": "SOURCE_GOVERNED_COMPLIANCE_RULE"})
        if practices.get("pays_for_reviews"): add("PAID_REVIEWS", "Critical", "Reviews are purchased or compensated", "Stop the practice and obtain platform/legal review before further solicitation.", "pays_for_reviews=true")
        if practices.get("incentivizes_reviews"): add("INCENTIVIZED_REVIEWS", "Critical", "Customers receive incentives for reviews", "Remove incentives and use a neutral request workflow compliant with each platform.", "incentivizes_reviews=true")
        if practices.get("employees_review_business"): add("SELF_REVIEW", "Critical", "Employees or owners review the business", "Remove prohibited self-review activity and document a staff policy.", "employees_review_business=true")
        if practices.get("review_kiosk"): add("REVIEW_KIOSK", "High", "A shared in-location review kiosk is used", "Stop shared-IP review collection; send customers to their own devices and accounts.", "review_kiosk=true")
        if practices.get("posts_for_customers"): add("POSTS_ON_BEHALF", "Critical", "Staff post reviews for customers", "Stop immediately; reviews must be submitted by customers from their own accounts.", "posts_for_customers=true")
        if practices.get("cherry_picks_testimonials"): add("CHERRY_PICKING", "Medium", "Website testimonials appear selectively curated", "Use a transparent, representative presentation and preserve source attribution.", "cherry_picks_testimonials=true")
        request_rate = practices.get("review_request_rate"); response_rate = practices.get("owner_response_rate")
        if isinstance(request_rate, (int, float)) and request_rate < 0.5: add("LOW_REQUEST_RATE", "Medium", "Eligible customers are rarely asked for reviews", "Create a compliant, neutral post-service request workflow with reminders.", f"review_request_rate={request_rate}")
        if isinstance(response_rate, (int, float)) and response_rate < 0.8: add("LOW_RESPONSE_RATE", "Medium", "Owner response coverage is incomplete", "Respond consistently, prioritize unresolved negatives, and track recovery outcomes.", f"owner_response_rate={response_rate}")
        data = {"operation": "review_compliance", "finding_count": len(findings), "findings": findings, "status": "BLOCKED" if any(item["severity"] == "Critical" for item in findings) else "REVIEW", "required_human_review": True, "limitations": ["This is platform-policy and risk screening, not legal advice.", "Rules differ by review platform and jurisdiction and must be verified at execution time.", "The source corpus does not prove a direct local-ranking effect from review quantity or responses."]}
        return AdapterResult(self.name, "needs-review" if findings else "ok", data, [])


class PerformanceNarrativeAnalyzer:
    name = "performance_narrative"

    def analyze(self, *, input_path: str | Path) -> AdapterResult:
        payload = _read_json(input_path)
        if not isinstance(payload, dict): raise ValueError("performance input must be an object")
        metric = str(payload.get("metric", "primary outcome")); baseline = float(payload["baseline"]); target = float(payload["target"]); actual = float(payload["actual"]); unit = str(payload.get("unit", "")); direction = str(payload.get("better_direction", "higher")); lead_value = payload.get("lead_value"); close_rate = payload.get("close_rate"); cost = payload.get("cost")
        change = actual - baseline; pct = (change / baseline * 100) if baseline else None; target_delta = actual - target; met = actual >= target if direction == "higher" else actual <= target
        good = f"{metric}: {actual:g}{unit}."; better = good if pct is None else f"{metric} changed {pct:+.1f}% from the {baseline:g}{unit} baseline to {actual:g}{unit}."
        best = f"{better} The result {'met' if met else 'did not meet'} the pre-agreed {target:g}{unit} target"; estimated_value = None
        if lead_value is not None and close_rate is not None:
            estimated_value = max(actual, 0) * float(close_rate) * float(lead_value); best += f" and represents an estimated ${estimated_value:,.2f} in expected value"
        best += "."; roi = (estimated_value - float(cost)) / float(cost) if estimated_value is not None and cost not in (None, 0) else None
        data = {"operation": "performance_narrative", "target_set_before_period": bool(payload.get("target_set_before_period", False)), "target_met": met, "target_delta": target_delta, "good": good, "better": better, "best": best, "estimated_value": estimated_value, "estimated_roi": roi, "evidence_layers": {"observed": payload.get("observed", {}), "proxy": payload.get("proxy", {}), "modeled": payload.get("modeled", {})}, "limitations": ["Modeled value depends on operator-supplied close rate and customer value.", "Observed, proxy, and modeled measures remain separate and must not be presented as one factual total."]}
        warnings = [] if data["target_set_before_period"] else ["The target was not recorded as pre-agreed; avoid claiming that it was exceeded or missed prospectively."]
        return AdapterResult(self.name, "ok" if not warnings else "needs-review", data, warnings)