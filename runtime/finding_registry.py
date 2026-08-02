"""Cross-agent finding normalization, deduplication, conflict detection, and decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

_SEVERITY_ORDER = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
EvidenceState = Literal["VALID", "MISSING", "STALE", "DUPLICATE", "CONTRADICTORY"]
_EVIDENCE_STATE_ORDER: dict[EvidenceState, int] = {
    "VALID": 0,
    "DUPLICATE": 1,
    "STALE": 2,
    "MISSING": 3,
    "CONTRADICTORY": 4,
}


def _norm(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value).lower()))


def _tokens(value: str) -> set[str]:
    return set(_norm(value).split())


def _finding_key(finding: dict[str, Any]) -> tuple[str, str]:
    scope = _norm(finding.get("affected_scope", ""))
    words = _tokens(finding.get("finding", ""))
    root_terms = sorted(
        words
        & {
            "canonical",
            "noindex",
            "robots",
            "redirect",
            "schema",
            "hreflang",
            "indexation",
            "rendering",
            "duplicate",
            "content",
            "claim",
            "consent",
            "availability",
            "price",
            "internal",
            "link",
            "accessibility",
            "security",
        }
    )
    identity = " ".join(root_terms) or " ".join(sorted(words)[:10])
    return scope, identity


def _worse(left: EvidenceState, right: EvidenceState) -> EvidenceState:
    return left if _EVIDENCE_STATE_ORDER[left] >= _EVIDENCE_STATE_ORDER[right] else right


def _evidence_inventory(output: dict[str, Any]) -> dict[str, list[str]]:
    inventory: dict[str, list[str]] = {}
    for item in output.get("evidence", []):
        if not isinstance(item, dict):
            continue
        evidence_status = str(item.get("state", "CURRENT")).upper()
        for key in (item.get("id"), item.get("source")):
            if isinstance(key, str) and key.strip():
                inventory.setdefault(key, []).append(evidence_status)
    return inventory


def _reference_state(reference: str, observed: list[str]) -> tuple[EvidenceState, list[str]]:
    if not observed:
        return "MISSING", [f"unknown evidence reference: {reference}"]
    state: EvidenceState = "VALID"
    issues: list[str] = []
    if len(observed) != 1:
        state = "DUPLICATE"
        issues.append(f"duplicate evidence inventory key: {reference}")
    normalized = set(observed)
    if "CONTRADICTORY" in normalized:
        return "CONTRADICTORY", [*issues, f"contradictory evidence: {reference}"]
    if normalized & {"MISSING", "INVALID"}:
        return _worse(state, "MISSING"), [*issues, f"unavailable evidence: {reference}"]
    if "STALE" in normalized:
        return _worse(state, "STALE"), [*issues, f"stale evidence: {reference}"]
    return state, issues


def _evidence_state(
    output: dict[str, Any], finding: dict[str, Any]
) -> tuple[EvidenceState, list[str]]:
    """Classify evidence refs without converting uncertainty into acceptance."""
    inventory = _evidence_inventory(output)
    raw_refs = finding.get("evidence_refs", [])
    refs = [str(item) for item in raw_refs] if isinstance(raw_refs, list) else []
    issues: list[str] = []
    state: EvidenceState = "VALID"
    if not refs:
        return "MISSING", ["finding has no evidence references"]
    if len(refs) != len(set(refs)):
        state = "DUPLICATE"
        issues.append("finding repeats an evidence reference")
    for reference in sorted(set(refs)):
        observed = inventory.get(reference, [])
        reference_state, reference_issues = _reference_state(reference, observed)
        state = _worse(state, reference_state)
        issues.extend(reference_issues)
    return state, sorted(set(issues))


@dataclass
class FindingRecord:
    key: tuple[str, str]
    finding: dict[str, Any]
    agents: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    state: str = "PROPOSED"
    evidence_state: EvidenceState = "VALID"
    evidence_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = dict(self.finding)
        result["agents"] = list(self.agents)
        result["finding_ids"] = list(self.finding_ids)
        result["state"] = self.state
        result["evidence_state"] = self.evidence_state
        result["evidence_issues"] = list(self.evidence_issues)
        result["root_cause_key"] = "::".join(self.key)
        return result


class FindingRegistry:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], FindingRecord] = {}

    def add_output(self, output: dict[str, Any]) -> None:
        agent = str(output.get("agent", "Unknown Agent"))
        for finding in output.get("findings", []):
            if not isinstance(finding, dict):
                continue
            key = _finding_key(finding)
            evidence_state, evidence_issues = _evidence_state(output, finding)
            finding_id = str(finding.get("id", ""))
            if key not in self._records:
                self._records[key] = FindingRecord(
                    key=key,
                    finding=dict(finding),
                    agents=[agent],
                    finding_ids=[finding_id] if finding_id else [],
                    evidence_state=evidence_state,
                    evidence_issues=evidence_issues,
                )
                continue
            record = self._records[key]
            if agent not in record.agents:
                record.agents.append(agent)
            existing_refs = set(record.finding.get("evidence_refs", []))
            incoming_refs = set(finding.get("evidence_refs", []))
            if existing_refs.intersection(incoming_refs):
                evidence_state = _worse(evidence_state, "DUPLICATE")
                evidence_issues.append("duplicate evidence repeated across findings")
            existing_refs.update(incoming_refs)
            record.finding["evidence_refs"] = sorted(existing_refs)
            if finding_id and finding_id not in record.finding_ids:
                record.finding_ids.append(finding_id)
            record.evidence_state = _worse(record.evidence_state, evidence_state)
            record.evidence_issues = sorted(set(record.evidence_issues).union(evidence_issues))
            current = str(record.finding.get("severity", "Low"))
            incoming = str(finding.get("severity", "Low"))
            if _SEVERITY_ORDER.get(incoming, 0) > _SEVERITY_ORDER.get(current, 0):
                record.finding["severity"] = incoming

    def records(self) -> list[dict[str, Any]]:
        return [self._records[key].to_dict() for key in sorted(self._records)]

    def _mark_contradictory(self, finding_ids: set[str]) -> None:
        for record in self._records.values():
            if finding_ids.intersection(record.finding_ids):
                record.evidence_state = "CONTRADICTORY"
                record.evidence_issues = sorted(
                    set(record.evidence_issues)
                    | {"specialists supplied contradictory evidence or actions"}
                )

    def conflicts(self, outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conflicts: list[dict[str, Any]] = []
        by_scope: dict[str, list[tuple[str, str, set[str]]]] = {}
        for output in outputs:
            agent = str(output.get("agent", "Unknown Agent"))
            for finding in output.get("findings", []):
                if not isinstance(finding, dict):
                    continue
                scope = _norm(finding.get("affected_scope", ""))
                words = _tokens(finding.get("finding", ""))
                by_scope.setdefault(scope, []).append((agent, str(finding.get("id", "")), words))

        opposing = [
            ({"publish", "launch", "index"}, {"noindex", "block", "reject", "remove"}),
            ({"grant", "allow"}, {"deny", "denied", "block"}),
            ({"implement", "generate"}, {"unsupported", "invalid", "prohibited"}),
        ]
        for scope, rows in by_scope.items():
            for index, left in enumerate(rows):
                for right in rows[index + 1 :]:
                    for positive, negative in opposing:
                        left_positive = bool(left[2] & positive)
                        left_negative = bool(left[2] & negative)
                        right_positive = bool(right[2] & positive)
                        right_negative = bool(right[2] & negative)
                        if (left_positive and right_negative) or (left_negative and right_positive):
                            conflicts.append(
                                {
                                    "conflict_id": f"conflict-{len(conflicts) + 1:03d}",
                                    "affected_scope": scope or "unspecified",
                                    "agents": [left[0], right[0]],
                                    "finding_ids": [left[1], right[1]],
                                    "reason": "Agents proposed materially incompatible states or actions.",
                                    "risk": "High",
                                }
                            )
                            self._mark_contradictory({left[1], right[1]})
                            break
        return conflicts

    def accept_all_without_conflict(self, conflicts: list[dict[str, Any]]) -> None:
        conflicted_ids = {
            finding_id for conflict in conflicts for finding_id in conflict.get("finding_ids", [])
        }
        for record in self._records.values():
            if set(record.finding_ids).intersection(conflicted_ids):
                record.state = "CONFLICTED"
                record.evidence_state = "CONTRADICTORY"
            else:
                record.state = "ACCEPTED" if record.evidence_state == "VALID" else "EVIDENCE_REVIEW"


def build_decisions(
    conflicts: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create explicit conservative decisions. Scrummaster output remains supporting evidence."""
    decisions: list[dict[str, Any]] = []
    for conflict in conflicts:
        decisions.append(
            {
                "decision_id": f"decision-{conflict['conflict_id']}",
                "proposal": f"Resolve conflict for {conflict['affected_scope']}",
                "decision": "Revise",
                "evidence": list(conflict.get("finding_ids", [])),
                "counterarguments": [conflict.get("reason", "Conflicting specialist conclusions")],
                "risk": conflict.get("risk", "High"),
                "owner": "SEO Scrummaster Agent",
                "conditions": [
                    "Reconcile the underlying evidence before implementation or publication.",
                    "Record the accepted finding and reject or supersede the conflicting finding.",
                ],
                "verification": "Re-run the affected specialists against the same evidence inventory.",
                "rollback": "Do not implement either conflicting action until the decision is resolved.",
            }
        )

    critical = [
        finding
        for finding in findings
        if finding.get("severity") in {"Critical", "High"} and finding.get("state") == "ACCEPTED"
    ]
    if critical:
        decisions.append(
            {
                "decision_id": "decision-high-risk-review",
                "proposal": "Accept high-risk findings for roadmap planning, not automatic implementation.",
                "decision": "Approve",
                "evidence": [str(item.get("id")) for item in critical],
                "counterarguments": [
                    "High-risk SEO changes may affect indexation, revenue, compliance, or security."
                ],
                "risk": "High",
                "owner": "SEO Scrummaster Agent",
                "conditions": ["Human approval remains required before any gated implementation."],
                "verification": "Confirm owner, acceptance criteria, rollback, and post-change validation.",
                "rollback": "Keep the current production behavior until the approved implementation is verified.",
            }
        )
    return decisions
