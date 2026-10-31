"""Offline-safe SEO intelligence analyzers derived from the governed source corpus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contracts.adapter import AdapterResult
from integrations.product_proof.intelligence_io import _read_json as _read_json
from integrations.product_proof.intelligence_observations import (
    AICitationOpportunityAnalyzer as AICitationOpportunityAnalyzer,
)
from integrations.product_proof.intelligence_timeouts import (
    AI_USER_AGENTS as AI_USER_AGENTS,
)
from integrations.product_proof.intelligence_timeouts import (
    AITimeoutAnalyzer as AITimeoutAnalyzer,
)
from integrations.product_proof.intelligence_timeouts import (
    TimeoutRecord as TimeoutRecord,
)
from integrations.product_proof.intelligence_timeouts import (
    _classify_ua as _classify_ua,
)


class ReviewComplianceAnalyzer:
    name = "review_compliance"

    @staticmethod
    def _append_finding(findings: list[dict[str, Any]], code: str, severity: str, title: str, action: str, evidence: str) -> None:
        findings.append(
            {
                "code": code,
                "severity": severity,
                "title": title,
                "recommended_action": action,
                "observed_evidence": evidence,
                "evidence_class": "SOURCE_GOVERNED_COMPLIANCE_RULE",
            }
        )

    @staticmethod
    def _practice_findings(practices: dict[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        if practices.get("pays_for_reviews"):
            ReviewComplianceAnalyzer._append_finding(findings,
                "PAID_REVIEWS",
                "Critical",
                "Reviews are purchased or compensated",
                "Stop the practice and obtain platform/legal review before further solicitation.",
                "pays_for_reviews=true",
            )
        if practices.get("incentivizes_reviews"):
            ReviewComplianceAnalyzer._append_finding(findings,
                "INCENTIVIZED_REVIEWS",
                "Critical",
                "Customers receive incentives for reviews",
                "Remove incentives and use a neutral request workflow compliant with each platform.",
                "incentivizes_reviews=true",
            )
        if practices.get("employees_review_business"):
            ReviewComplianceAnalyzer._append_finding(findings,
                "SELF_REVIEW",
                "Critical",
                "Employees or owners review the business",
                "Remove prohibited self-review activity and document a staff policy.",
                "employees_review_business=true",
            )
        if practices.get("review_kiosk"):
            ReviewComplianceAnalyzer._append_finding(findings,
                "REVIEW_KIOSK",
                "High",
                "A shared in-location review kiosk is used",
                "Stop shared-IP review collection; send customers to their own devices and accounts.",
                "review_kiosk=true",
            )
        if practices.get("posts_for_customers"):
            ReviewComplianceAnalyzer._append_finding(findings,
                "POSTS_ON_BEHALF",
                "Critical",
                "Staff post reviews for customers",
                "Stop immediately; reviews must be submitted by customers from their own accounts.",
                "posts_for_customers=true",
            )
        if practices.get("cherry_picks_testimonials"):
            ReviewComplianceAnalyzer._append_finding(findings,
                "CHERRY_PICKING",
                "Medium",
                "Website testimonials appear selectively curated",
                "Use a transparent, representative presentation and preserve source attribution.",
                "cherry_picks_testimonials=true",
            )
        return findings

    def analyze(self, *, input_path: str | Path) -> AdapterResult:
        payload = _read_json(input_path)
        if not isinstance(payload, dict):
            raise ValueError("review input must be an object")
        practices = payload.get("practices", payload)
        findings = self._practice_findings(practices)
        request_rate = practices.get("review_request_rate")
        response_rate = practices.get("owner_response_rate")
        if isinstance(request_rate, (int, float)) and request_rate < 0.5:
            ReviewComplianceAnalyzer._append_finding(findings,
                "LOW_REQUEST_RATE",
                "Medium",
                "Eligible customers are rarely asked for reviews",
                "Create a compliant, neutral post-service request workflow with reminders.",
                f"review_request_rate={request_rate}",
            )
        if isinstance(response_rate, (int, float)) and response_rate < 0.8:
            ReviewComplianceAnalyzer._append_finding(findings,
                "LOW_RESPONSE_RATE",
                "Medium",
                "Owner response coverage is incomplete",
                "Respond consistently, prioritize unresolved negatives, and track recovery outcomes.",
                f"owner_response_rate={response_rate}",
            )
        data = {
            "operation": "review_compliance",
            "finding_count": len(findings),
            "findings": findings,
            "status": "BLOCKED"
            if any(item["severity"] == "Critical" for item in findings)
            else "REVIEW",
            "required_human_review": True,
            "limitations": [
                "This is platform-policy and risk screening, not legal advice.",
                "Rules differ by review platform and jurisdiction and must be verified at execution time.",
                "The source corpus does not prove a direct local-ranking effect from review quantity or responses.",
            ],
        }
        return AdapterResult(self.name, "needs-review" if findings else "ok", data, [])


class PerformanceNarrativeAnalyzer:
    name = "performance_narrative"

    def analyze(self, *, input_path: str | Path) -> AdapterResult:
        payload = _read_json(input_path)
        if not isinstance(payload, dict):
            raise ValueError("performance input must be an object")
        metric = str(payload.get("metric", "primary outcome"))
        baseline = float(payload["baseline"])
        target = float(payload["target"])
        actual = float(payload["actual"])
        unit = str(payload.get("unit", ""))
        direction = str(payload.get("better_direction", "higher"))
        lead_value = payload.get("lead_value")
        close_rate = payload.get("close_rate")
        cost = payload.get("cost")
        change = actual - baseline
        pct = (change / baseline * 100) if baseline else None
        target_delta = actual - target
        met = actual >= target if direction == "higher" else actual <= target
        good = f"{metric}: {actual:g}{unit}."
        better = (
            good
            if pct is None
            else f"{metric} changed {pct:+.1f}% from the {baseline:g}{unit} baseline to {actual:g}{unit}."
        )
        best = f"{better} The result {'met' if met else 'did not meet'} the pre-agreed {target:g}{unit} target"
        estimated_value = None
        if lead_value is not None and close_rate is not None:
            estimated_value = max(actual, 0) * float(close_rate) * float(lead_value)
            best += f" and represents an estimated ${estimated_value:,.2f} in expected value"
        best += "."
        roi = (
            (estimated_value - float(cost)) / float(cost)
            if estimated_value is not None and cost not in (None, 0)
            else None
        )
        data = {
            "operation": "performance_narrative",
            "target_set_before_period": bool(payload.get("target_set_before_period", False)),
            "target_met": met,
            "target_delta": target_delta,
            "good": good,
            "better": better,
            "best": best,
            "estimated_value": estimated_value,
            "estimated_roi": roi,
            "evidence_layers": {
                "observed": payload.get("observed", {}),
                "proxy": payload.get("proxy", {}),
                "modeled": payload.get("modeled", {}),
            },
            "limitations": [
                "Modeled value depends on operator-supplied close rate and customer value.",
                "Observed, proxy, and modeled measures remain separate and must not be presented as one factual total.",
            ],
        }
        warnings = (
            []
            if data["target_set_before_period"]
            else [
                "The target was not recorded as pre-agreed; avoid claiming that it was exceeded or missed prospectively."
            ]
        )
        return AdapterResult(self.name, "ok" if not warnings else "needs-review", data, warnings)
