"""Deterministic content intelligence with explicit truth boundaries.

The service measures supplied text and supplied review records. It does not
claim Google ranking potential, originality, factual accuracy, expertise,
source existence, user satisfaction, or causal explanations that were not
independently established.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from contracts.adapter import AdapterResult
from integrations.content_intelligence.analysis import (
    CAPITALIZED,
    FILLER_PATTERNS,
    bounded_records,
    compare_texts,
    protected_tokens,
    require_unique_ids,
    required_string,
    validate_text,
)
from integrations.content_intelligence.decay_service import decay
from integrations.content_intelligence.quality_service import quality
from integrations.content_intelligence.verify_service import verify
from integrations.extensions.providers import ProviderService, normalize_entity_analysis
from scripts.content_brief_evidence import brief_decision


class ContentIntelligenceService:
    """Analyze and transform supplied content without unsupported claims."""

    name = "content_intelligence"

    def __init__(self, providers: ProviderService) -> None:
        self.providers = providers

    def quality(
        self,
        *,
        text: str,
        title: str | None = None,
        audience: str | None = None,
        purpose: str | None = None,
        author: str | None = None,
        reviewed_by: str | None = None,
        sources: list[dict[str, Any]] | None = None,
        risk_class: str = "general",
        **_: Any,
    ) -> AdapterResult:
        return quality(
            self.name,
            text=text,
            title=title,
            audience=audience,
            purpose=purpose,
            author=author,
            reviewed_by=reviewed_by,
            sources=sources,
            risk_class=risk_class,
            **_,
        )

    def verify(
        self,
        *,
        claims: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        **_: Any,
    ) -> AdapterResult:
        return verify(self.name, claims=claims, sources=sources, **_)

    def entities(
        self,
        *,
        text: str,
        catalog: list[dict[str, Any]] | None = None,
        **_: Any,
    ) -> AdapterResult:
        value = validate_text(text)
        catalog_rows = bounded_records(catalog or [], "catalog")
        require_unique_ids(catalog_rows, "entity")
        matches, known_terms = _catalog_matches(catalog_rows, value)
        candidates: list[dict[str, Any]] = []
        candidate_counts = Counter(match.group(0).strip() for match in CAPITALIZED.finditer(value))
        for candidate, count in sorted(candidate_counts.items()):
            if candidate.casefold() in known_terms:
                continue
            if len(candidate) < 2 or candidate.lower() in {"the", "this", "a", "an"}:
                continue
            candidates.append(
                {
                    "text": candidate,
                    "mentions": count,
                    "confidence": "LOW",
                    "evidence_state": "HEURISTIC_TEXT_CANDIDATE",
                }
            )
        return AdapterResult(
            source=self.name,
            status="ok",
            data={
                "operation": "entities",
                "data_state": "AVAILABLE",
                "catalog_matches": matches,
                "catalog_match_count": len(matches),
                "heuristic_candidates": candidates[:500],
                "provider_analysis": normalize_entity_analysis(
                    _.get("provider_analysis"), providers=self.providers
                ),
                "knowledge_graph_verification": "NOT_RUN",
                "entity_identity_verification": "NOT_RUN",
                "limitations": [
                    "Catalog matches prove string occurrence only, not identity, relationship, salience, or factual correctness.",
                    "Capitalized phrases are low-confidence candidates and can include sentence starts, dates, or non-entities.",
                ],
            },
            warnings=(
                []
                if catalog_rows
                else [
                    "No entity catalog was supplied; only low-confidence text candidates are available."
                ]
            ),
        )

    def brief(
        self,
        *,
        relevance: dict[str, Any],
        serp: dict[str, Any],
        information_gains: list[str],
        sources: list[dict[str, Any]],
        audience: str,
        intent: str,
        primary_question: str,
        required_sections: list[str] | None = None,
        conditions_resolved: bool = False,
        **_: Any,
    ) -> AdapterResult:
        if not isinstance(relevance, dict) or not isinstance(serp, dict):
            raise TypeError("relevance and serp must be objects")
        gains = [item.strip() if isinstance(item, str) else item for item in information_gains]
        source_rows = bounded_records(sources, "sources")
        section_rows = [
            str(item).strip() for item in (required_sections or []) if str(item).strip()
        ]
        decision = brief_decision(
            relevance,
            serp,
            gains,
            conditions_resolved=conditions_resolved,
            selected_intent=intent or None,
        )
        blocking = _brief_blockers(
            decision, source_rows, audience, intent, primary_question, section_rows
        )
        ready = not blocking
        warnings = list(blocking)
        return AdapterResult(
            source=self.name,
            status="ok" if ready else "blocked",
            data={
                "operation": "brief",
                "data_state": "AVAILABLE" if ready else "BLOCKED",
                "publish_decision": "READY_FOR_DRAFT" if ready else "BLOCKED",
                "canonical_brief_gate": decision,
                "audience": audience,
                "intent": intent,
                "primary_question": primary_question,
                "required_sections": section_rows,
                "information_gains": gains,
                "source_register": source_rows,
                "blocking_reasons": blocking,
                "limitations": [
                    "A passed brief gate authorizes drafting, not publishing.",
                    "Sources and information-gain statements still require claim-level verification during drafting and review.",
                ],
            },
            warnings=warnings,
        )

    def decay(
        self,
        *,
        current: dict[str, Any],
        prior: dict[str, Any],
        decline_threshold: float = 0.2,
        **_: Any,
    ) -> AdapterResult:
        return decay(
            self.name, current=current, prior=prior, decline_threshold=decline_threshold, **_
        )

    def compare(
        self,
        *,
        left_text: str,
        right_text: str,
        left_label: str = "left",
        right_label: str = "right",
        **_: Any,
    ) -> AdapterResult:
        left = validate_text(left_text)
        right = validate_text(right_text)
        comparison = compare_texts(left, right, left_label, right_label)
        return AdapterResult(
            source=self.name,
            status="ok",
            data={
                "operation": "compare",
                "data_state": "AVAILABLE",
                **comparison,
                "winner": None,
                "quality_superiority": "NOT_ASSESSED",
                "factual_accuracy_comparison": "NOT_RUN",
                "limitations": [
                    "Lexical and structural differences do not establish usefulness, originality, accuracy, or ranking superiority.",
                    "Exact overlap does not determine copyright status or improper copying.",
                ],
            },
            warnings=[],
        )

    def humanize(self, *, text: str, **_: Any) -> AdapterResult:
        original = validate_text(text)
        transformed = original
        changes: list[dict[str, Any]] = []
        for pattern, replacement, change_id in FILLER_PATTERNS:
            transformed, count = pattern.subn(replacement, transformed)
            if count:
                changes.append({"change": change_id, "count": count})
        normalized = re.sub(r"[ \t]+", " ", transformed)
        normalized = re.sub(r" *\n *", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
        normalized = re.sub(r"([.!?])(?=[A-Z])", r"\1 ", normalized)
        normalized = normalized.strip()
        if normalized != transformed.strip():
            changes.append({"change": "normalized_whitespace_and_punctuation", "count": 1})
        protected_before = protected_tokens(original)
        protected_after = protected_tokens(normalized)
        protected_preserved = protected_before == protected_after
        warnings: list[str] = []
        if not protected_preserved:
            warnings.append(
                "A protected number, URL, or citation token changed; review the transformed text before use."
            )
        if not changes:
            warnings.append("No configured clarity-only transformations were applicable.")
        return AdapterResult(
            source=self.name,
            status="ok" if protected_preserved else "needs-review",
            data={
                "operation": "humanize",
                "data_state": "AVAILABLE" if protected_preserved else "PARTIAL",
                "transformed_text": normalized,
                "changes": changes,
                "purpose": "clarity_and_readability",
                "ai_detector_evasion": "NOT_SUPPORTED",
                "authorship_concealment": "NOT_SUPPORTED",
                "facts_verified": False,
                "protected_tokens_preserved": protected_preserved,
                "protected_tokens": sorted(protected_after),
                "limitations": [
                    "The transformation removes a small allowlist of filler patterns and normalizes formatting only.",
                    "It does not verify facts, improve expertise, prove originality, or determine whether text was written by a person or model.",
                ],
            },
            warnings=warnings,
        )


def _catalog_matches(
    catalog_rows: list[dict[str, Any]], value: str
) -> tuple[list[dict[str, Any]], set[str]]:
    known_terms: set[str] = set()
    matches: list[dict[str, Any]] = []
    for entity in catalog_rows:
        entity_id = required_string(entity, "id", "entity")
        name = required_string(entity, "name", f"entity {entity_id}")
        aliases = [str(item).strip() for item in entity.get("aliases", []) if str(item).strip()]
        terms = list(dict.fromkeys([name, *aliases]))
        occurrences: list[dict[str, Any]] = []
        for term in terms:
            known_terms.add(term.casefold())
            pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
            count = len(pattern.findall(value))
            if count:
                occurrences.append({"term": term, "count": count})
        if occurrences:
            matches.append(
                {
                    "id": entity_id,
                    "name": name,
                    "matched_terms": occurrences,
                    "total_mentions": sum(item["count"] for item in occurrences),
                    "evidence_state": "TEXT_MATCH_ONLY",
                    "confidence": "HIGH_FOR_STRING_MATCH_ONLY",
                }
            )

    return matches, known_terms


def _brief_blockers(
    decision: dict[str, Any],
    source_rows: list[dict[str, Any]],
    audience: str,
    intent: str,
    primary_question: str,
    section_rows: list[str],
) -> list[str]:
    blocking: list[str] = []
    if not decision.get("publish"):
        blocking.append(str(decision.get("reason") or "Canonical brief gate did not pass."))
    if not source_rows:
        blocking.append("No source register was supplied.")
    if not audience.strip():
        blocking.append("Audience is required.")
    if not intent.strip():
        blocking.append("Target intent is required.")
    if not primary_question.strip():
        blocking.append("Primary question is required.")
    if not section_rows:
        blocking.append("At least one required section is needed for a complete brief.")

    return blocking
