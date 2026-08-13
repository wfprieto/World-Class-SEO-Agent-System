"""Deterministic specialist decision mapping and known-answer control artifacts.

This module does not diagnose a site. It maps explicit fixture or operator-supplied
signals to the decision vocabulary used by priority specialist playbooks and checks
that the runtime context contains each specialist's critical safety rules.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


class SpecialistDecisionError(ValueError):
    """Raised when specialist context or decision output violates the contract."""


SPECIALIST_AGENTS = frozenset(
    {
        "Competitive Intelligence Agent",
        "International & Multilingual SEO Agent",
        "Local SEO Agent",
        "Negative SEO & Security Agent",
        "Predictive SEO Trend Agent",
        "SEO Accessibility Agent",
        "SEO Compliance & Legal Agent",
        "Visual & Video Search Agent",
    }
)

DECISION_TO_EXECUTION = {
    "READY": "COMPLETE",
    "PARTIAL": "PARTIAL",
    "BLOCKED": "BLOCKED",
    "ABSTAIN": "PARTIAL",
    "ESCALATE": "BLOCKED",
}

INTEGRITY_PATH = "governance/specialist-playbook-integrity.json"
STANDARD_PATH = "skills/specialist-decision-standard.md"
PLAYBOOK_PATH = "skills/specialist-depth-playbooks.md"

# These are narrow safety invariants, not keyword-based SEO conclusions. Their
# presence ensures token-complete nonsense cannot replace the canonical playbooks.
SEMANTIC_RULE_MARKERS: dict[str, tuple[str, ...]] = {
    "Negative SEO & Security Agent": (
        "never submit a disavow automatically",
        "ABSTAIN` from attacker identity or causation",
    ),
    "SEO Accessibility Agent": (
        "Full-conformance claims are outside agent authority",
        "never claim rendered behavior or WCAG conformance",
    ),
    "International & Multilingual SEO Agent": (
        "ABSTAIN` from translation quality without market expertise",
        "Escalate sitewide URL migrations",
    ),
    "Local SEO Agent": (
        "protect hidden addresses",
        "ABSTAIN` from rank-cause and market-share claims",
    ),
    "Competitive Intelligence Agent": (
        "avoid reactive copying",
        "ABSTAIN` from causal attribution and competitor intent",
    ),
    "Predictive SEO Trend Agent": (
        "at least two independent signal classes",
        "ABSTAIN` from point forecasts and durability claims",
    ),
    "Visual & Video Search Agent": (
        "Search eligibility is not indexing or ranking proof",
        "do not generate supposedly accurate replacements from inference",
    ),
    "SEO Compliance & Legal Agent": (
        "never makes final legal determinations",
        "ABSTAIN` from legal advice or compliance certification",
    ),
}


def _context_text(skill_context: Sequence[Mapping[str, Any]]) -> str:
    return "\n".join(
        str(row.get("content", ""))
        for row in skill_context
        if isinstance(row, Mapping)
    )


def _context_by_path(
    skill_context: Sequence[Mapping[str, Any]], path: str
) -> str | None:
    matches = [
        str(row.get("content", ""))
        for row in skill_context
        if isinstance(row, Mapping) and row.get("path") == path
    ]
    return matches[0] if len(matches) == 1 else None


def _sha256_normalized(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def runtime_integrity_errors(
    agent: str, skill_context: Sequence[Mapping[str, Any]]
) -> list[str]:
    """Validate exact reviewed context using the shared version/digest registry."""
    raw_contract = _context_by_path(skill_context, INTEGRITY_PATH)
    standard = _context_by_path(skill_context, STANDARD_PATH)
    playbook = _context_by_path(skill_context, f"{PLAYBOOK_PATH}#{agent}")
    if raw_contract is None or standard is None or playbook is None:
        return [f"specialist integrity context is incomplete: {agent}"]
    try:
        contract = json.loads(raw_contract)
        standard_row = contract["standard"]
        agent_row = contract["playbook"]["agents"][agent]
    except (KeyError, TypeError, json.JSONDecodeError):
        return [f"specialist integrity registry is invalid: {agent}"]
    errors: list[str] = []
    identity = (contract.get("schema_version"), contract.get("hash_algorithm"))
    if identity != ("1.0.0", "sha256-normalized-utf8"):
        errors.append("specialist integrity registry identity is invalid")
    if standard_row.get("path") != STANDARD_PATH or standard_row.get("version") != 1:
        errors.append("specialist standard version binding is invalid")
    if standard_row.get("sha256") != _sha256_normalized(standard):
        errors.append("specialist standard digest mismatch")
    if agent_row.get("version") != 1:
        errors.append(f"specialist playbook version binding is invalid: {agent}")
    if agent_row.get("sha256") != _sha256_normalized(playbook):
        errors.append(f"specialist playbook digest mismatch: {agent}")
    return errors


def missing_semantic_rules(agent: str, context: str) -> list[str]:
    """Return critical rules absent from one priority specialist's context."""
    return [
        marker
        for marker in SEMANTIC_RULE_MARKERS.get(agent, ())
        if marker not in context
    ]


def decision_artifact(
    *,
    agent: str,
    skill_context: Sequence[Mapping[str, Any]],
    required_evidence_available: bool,
    material_harm: bool,
    evidence_ambiguous: bool = False,
    coverage_limited: bool = False,
    evidence_refs: Sequence[str] = (),
) -> dict[str, Any]:
    """Resolve a bounded known-answer decision from explicit non-SEO signals."""
    if agent not in SPECIALIST_AGENTS:
        raise SpecialistDecisionError(f"agent is not a priority specialist: {agent}")
    integrity_errors = runtime_integrity_errors(agent, skill_context)
    if integrity_errors:
        raise SpecialistDecisionError("; ".join(integrity_errors))
    missing = missing_semantic_rules(agent, _context_text(skill_context))
    if missing:
        raise SpecialistDecisionError(
            f"specialist runtime context missing semantic rules: {agent} -> {missing}"
        )
    refs = [str(item) for item in evidence_refs]
    if len(refs) != len(set(refs)) or any(not item.strip() for item in refs):
        raise SpecialistDecisionError("evidence references must be unique non-empty strings")

    if material_harm:
        state, rationale = "ESCALATE", "MATERIAL_HARM_REQUIRES_HUMAN_OWNER"
    elif not required_evidence_available:
        state, rationale = "BLOCKED", "REQUIRED_EVIDENCE_UNAVAILABLE"
    elif evidence_ambiguous:
        state, rationale = "ABSTAIN", "EVIDENCE_CANNOT_DISTINGUISH_EXPLANATIONS"
    elif coverage_limited:
        state, rationale = "PARTIAL", "COVERAGE_LIMITS_DECISION"
    else:
        state, rationale = "READY", "SUFFICIENT_BOUNDED_EVIDENCE"
    return {
        "state": state,
        "mapped_execution_state": DECISION_TO_EXECUTION[state],
        "rationale_code": rationale,
        "evidence_refs": refs,
        "human_action_required": state == "ESCALATE",
    }


def _mapping_errors(
    output: Mapping[str, Any], decision: Mapping[str, Any]
) -> list[str]:
    state = decision.get("state")
    expected = DECISION_TO_EXECUTION.get(str(state))
    mapped = decision.get("mapped_execution_state")
    errors: list[str] = []
    if expected is None:
        errors.append(f"unknown specialist decision state: {state!r}")
    elif mapped != expected:
        errors.append(
            f"specialist decision {state} must map to execution state {expected}"
        )
    actual = output.get("execution_state")
    synthetic_partial = actual == "SYNTHETIC" and state == "PARTIAL"
    if expected is not None and actual != expected and not synthetic_partial:
        errors.append(
            f"specialist decision {state} conflicts with output execution_state {actual!r}"
        )
    human_action = decision.get("human_action_required")
    if human_action is not (state == "ESCALATE"):
        errors.append("human_action_required must be true exactly for ESCALATE")
    return errors


def _evidence_errors(
    output: Mapping[str, Any], decision: Mapping[str, Any]
) -> list[str]:
    refs = decision.get("evidence_refs")
    evidence = output.get("evidence", [])
    evidence_ids = {
        str(item.get("id"))
        for item in evidence
        if isinstance(item, Mapping) and item.get("id")
    } if isinstance(evidence, list) else set()
    if not isinstance(refs, list):
        return ["specialist_decision evidence_refs must be a list"]
    errors: list[str] = []
    unknown = sorted({str(item) for item in refs} - evidence_ids)
    if unknown:
        errors.append(f"specialist_decision references unknown evidence: {unknown}")
    if decision.get("state") != "BLOCKED" and not refs:
        errors.append(f"specialist decision {decision.get('state')} requires evidence_refs")
    return errors


def specialist_output_errors(output: Mapping[str, Any]) -> list[str]:
    """Validate specialist decision mapping against the top-level execution state."""
    agent = output.get("agent")
    if agent not in SPECIALIST_AGENTS:
        return []
    decision = output.get("specialist_decision")
    if not isinstance(decision, Mapping):
        return ["priority specialist output requires specialist_decision"]
    return [*_mapping_errors(output, decision), *_evidence_errors(output, decision)]
