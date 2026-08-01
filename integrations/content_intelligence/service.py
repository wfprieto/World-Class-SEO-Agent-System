"""Deterministic content intelligence with explicit truth boundaries.

The service measures supplied text and supplied review records. It does not
claim Google ranking potential, originality, factual accuracy, expertise,
source existence, user satisfaction, or causal explanations that were not
independently established.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from adapters.base import AdapterResult
from integrations.content_intelligence.analysis import (
    CAPITALIZED,
    FILLER_PATTERNS,
    bounded_records,
    compare_texts,
    diagnostic_check,
    iso_date,
    mean,
    number_or_none,
    parse_period,
    protected_tokens,
    quality_measurements,
    require_unique_ids,
    required_string,
    safe_registry_url,
    validate_text,
)
from scripts.content_brief_evidence import brief_decision

_ALLOWED_RELATIONS = {"supports", "contradicts", "partial", "context_only", "not_checked"}


class ContentIntelligenceService:
    """Analyze and transform supplied content without unsupported claims."""

    name = "content_intelligence"

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
        value = validate_text(text)
        measurements = quality_measurements(value)
        headings = measurements["headings"]
        duplicates = measurements["duplicates"]
        sentence_lengths = measurements["sentence_lengths"]
        paragraph_lengths = measurements["paragraph_lengths"]
        source_rows = bounded_records(sources or [], "sources")
        first_person = measurements["first_person"]
        citation_markers = measurements["citation_markers"]
        metrics = measurements["metrics"]
        checks = [
            diagnostic_check("descriptive_title_supplied", bool(title and 8 <= len(title.strip()) <= 100), 15, {"title": title}),
            diagnostic_check("audience_supplied", bool(audience and audience.strip()), 10, {"audience": audience}),
            diagnostic_check("purpose_supplied", bool(purpose and purpose.strip()), 10, {"purpose": purpose}),
            diagnostic_check("authorship_supplied", bool(author and author.strip()), 10, {"author": author}),
            diagnostic_check("source_register_supplied", bool(source_rows), 10, {"source_count": len(source_rows)}),
            diagnostic_check(
                "sentence_length_bounded",
                not sentence_lengths or (mean(sentence_lengths) or 0) <= 25,
                15,
                {"average_sentence_words": metrics["average_sentence_words"]},
            ),
            diagnostic_check(
                "paragraph_length_bounded",
                not paragraph_lengths or (mean(paragraph_lengths) or 0) <= 120,
                10,
                {"average_paragraph_words": metrics["average_paragraph_words"]},
            ),
            diagnostic_check("duplicate_sentences_absent", not duplicates, 10, {"duplicates": duplicates[:20]}),
            diagnostic_check("heading_structure_present", bool(headings), 10, {"headings": headings[:50]}),
        ]
        available_weight = sum(item["weight"] for item in checks)
        earned_weight = sum(item["weight"] for item in checks if item["state"] == "PASS")
        score = round((earned_weight / available_weight) * 100, 1) if available_weight else 0.0
        warnings: list[str] = []
        if first_person:
            warnings.append(
                "First-person language is present, but first-hand experience requires external evidence before it can be treated as verified."
            )
        if citation_markers and not source_rows:
            warnings.append("Citation markers are present without a supplied source register.")
        if risk_class.lower() in {"ymyl", "medical", "legal", "financial", "safety"}:
            warnings.append(
                "High-stakes content requires qualified human review and current authoritative sources; this diagnostic does not supply that review."
            )
        if score < 70:
            warnings.append("Measured editorial signals fall below the configured diagnostic threshold of 70.")
        return AdapterResult(
            source=self.name,
            status="ok" if score >= 70 else "needs-review",
            data={
                "operation": "quality",
                "data_state": "AVAILABLE",
                "metrics": metrics,
                "headings": headings,
                "duplicate_sentences": duplicates,
                "signals": {
                    "authorship_supplied": bool(author and author.strip()),
                    "reviewer_supplied": bool(reviewed_by and reviewed_by.strip()),
                    "source_count": len(source_rows),
                    "first_person_language_present": first_person,
                    "first_hand_experience_verified": False,
                    "risk_class": risk_class,
                },
                "checks": checks,
                "diagnostic_score": {
                    "value": score,
                    "scope": "measurable_editorial_signals_only",
                    "threshold": 70,
                    "not_a_google_score": True,
                    "not_a_ranking_probability": True,
                },
                "google_ranking_score": None,
                "not_assessed": [
                    "factual_accuracy",
                    "originality",
                    "author_expertise",
                    "first_hand_experience_authenticity",
                    "user_satisfaction",
                    "ranking_potential",
                    "search_demand",
                ],
                "limitations": [
                    "Editorial diagnostics cannot determine whether content is helpful to every user.",
                    "Presence of an author, source, or first-person statement does not verify expertise, accuracy, or experience.",
                ],
            },
            warnings=warnings,
        )

    def verify(
        self,
        *,
        claims: list[dict[str, Any]],
        sources: list[dict[str, Any]],
        **_: Any,
    ) -> AdapterResult:
        claim_rows = bounded_records(claims, "claims")
        source_rows = bounded_records(sources, "sources")
        require_unique_ids(claim_rows, "claim")
        require_unique_ids(source_rows, "source")
        source_map: dict[str, dict[str, Any]] = {}
        normalized_sources: list[dict[str, Any]] = []
        for source in source_rows:
            source_id = required_string(source, "id", "source")
            title = required_string(source, "title", f"source {source_id}")
            url = source.get("url")
            if url is not None:
                safe_registry_url(str(url))
            row = {
                "id": source_id,
                "title": title,
                "url": str(url) if url else None,
                "publisher": source.get("publisher"),
                "primary": bool(source.get("primary", False)),
                "published_at": source.get("published_at"),
                "accessed_at": source.get("accessed_at"),
                "source_quality": "OPERATOR_SUPPLIED",
                "availability": "NOT_CHECKED",
            }
            for key in ("published_at", "accessed_at"):
                if row[key]:
                    iso_date(str(row[key]), f"source {source_id} {key}")
            source_map[source_id] = row
            normalized_sources.append(row)

        normalized_claims: list[dict[str, Any]] = []
        state_counts: Counter[str] = Counter()
        warnings: list[str] = []
        for claim in claim_rows:
            claim_id = required_string(claim, "id", "claim")
            text = required_string(claim, "text", f"claim {claim_id}")
            source_ids = [str(item).strip() for item in claim.get("source_ids", []) if str(item).strip()]
            if len(source_ids) != len(set(source_ids)):
                raise ValueError(f"claim {claim_id} contains duplicate source_ids")
            missing_sources = sorted(source_id for source_id in source_ids if source_id not in source_map)
            assessments = bounded_records(claim.get("source_assessments", []), f"claim {claim_id} source_assessments")
            normalized_assessments: list[dict[str, Any]] = []
            valid_relations: list[str] = []
            assessment_issues: list[str] = []
            for assessment in assessments:
                source_id = required_string(assessment, "source_id", f"claim {claim_id} assessment")
                relation = required_string(assessment, "relation", f"claim {claim_id} assessment").lower()
                if relation not in _ALLOWED_RELATIONS:
                    raise ValueError(
                        f"claim {claim_id} assessment relation must be one of {sorted(_ALLOWED_RELATIONS)}"
                    )
                reviewer = str(assessment.get("reviewer") or "").strip()
                reviewed_at = str(assessment.get("reviewed_at") or "").strip()
                if source_id not in source_ids:
                    assessment_issues.append(f"assessment references undeclared source {source_id}")
                if source_id not in source_map:
                    assessment_issues.append(f"assessment references missing source {source_id}")
                review_complete = bool(reviewer and reviewed_at)
                if reviewed_at:
                    iso_date(reviewed_at, f"claim {claim_id} reviewed_at")
                if not review_complete:
                    assessment_issues.append(
                        f"assessment for source {source_id} lacks reviewer or reviewed_at"
                    )
                if review_complete and source_id in source_map and source_id in source_ids:
                    valid_relations.append(relation)
                normalized_assessments.append(
                    {
                        "source_id": source_id,
                        "relation": relation,
                        "reviewer": reviewer or None,
                        "reviewed_at": reviewed_at or None,
                        "note": assessment.get("note"),
                        "review_complete": review_complete,
                    }
                )
            if missing_sources:
                state = "SOURCE_MISSING"
            elif not source_ids:
                state = "UNSUPPORTED"
            elif "contradicts" in valid_relations:
                state = "CONTRADICTED_BY_SUPPLIED_REVIEW"
            elif "supports" in valid_relations:
                state = "SUPPORTED_BY_SUPPLIED_REVIEW"
            elif "partial" in valid_relations:
                state = "PARTIALLY_SUPPORTED_BY_SUPPLIED_REVIEW"
            else:
                state = "UNVERIFIED"
            state_counts[state] += 1
            normalized_claims.append(
                {
                    "id": claim_id,
                    "text": text,
                    "source_ids": source_ids,
                    "missing_source_ids": missing_sources,
                    "source_assessments": normalized_assessments,
                    "assessment_issues": assessment_issues,
                    "verification_state": state,
                    "verification_basis": "SUPPLIED_HUMAN_REVIEW_RECORDS_ONLY",
                }
            )
            if state != "SUPPORTED_BY_SUPPLIED_REVIEW":
                warnings.append(f"Claim {claim_id} remains {state}.")
            warnings.extend(f"Claim {claim_id}: {issue}." for issue in assessment_issues)
        unresolved_states = {
            "SOURCE_MISSING",
            "UNSUPPORTED",
            "UNVERIFIED",
            "PARTIALLY_SUPPORTED_BY_SUPPLIED_REVIEW",
        }
        unresolved = sum(state_counts[state] for state in unresolved_states)
        contradicted = state_counts["CONTRADICTED_BY_SUPPLIED_REVIEW"]
        status = "ok" if unresolved == 0 and contradicted == 0 else "needs-review"
        return AdapterResult(
            source=self.name,
            status=status,
            data={
                "operation": "verify",
                "data_state": "AVAILABLE" if status == "ok" else "PARTIAL",
                "claims": normalized_claims,
                "sources": normalized_sources,
                "summary": {
                    "claim_count": len(normalized_claims),
                    "source_count": len(normalized_sources),
                    "states": dict(sorted(state_counts.items())),
                    "unsupported_or_unverified": unresolved,
                    "contradicted": contradicted,
                },
                "independent_source_fetch": "NOT_RUN",
                "semantic_source_validation": "SUPPLIED_REVIEW_ONLY",
                "limitations": [
                    "A URL, citation, or source title alone does not verify a claim.",
                    "The service validates supplied review records but does not independently read or authenticate sources.",
                ],
            },
            warnings=warnings,
        )

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
                else ["No entity catalog was supplied; only low-confidence text candidates are available."]
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
        gains = [str(item).strip() for item in information_gains if str(item).strip()]
        source_rows = bounded_records(sources, "sources")
        section_rows = [str(item).strip() for item in (required_sections or []) if str(item).strip()]
        decision = brief_decision(
            relevance,
            serp,
            gains,
            conditions_resolved=conditions_resolved,
            selected_intent=intent or None,
        )
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
        if not isinstance(current, dict) or not isinstance(prior, dict):
            raise TypeError("current and prior snapshots must be objects")
        if not isinstance(decline_threshold, (int, float)) or not 0 < float(decline_threshold) <= 1:
            raise ValueError("decline_threshold must be greater than 0 and at most 1")
        current_range = parse_period(current, "current")
        prior_range = parse_period(prior, "prior")
        if current_range[0] <= prior_range[1]:
            raise ValueError("current period must start after prior period ends")
        current_metrics = current.get("metrics") or {}
        prior_metrics = prior.get("metrics") or {}
        if not isinstance(current_metrics, dict) or not isinstance(prior_metrics, dict):
            raise TypeError("snapshot metrics must be objects")
        metric_names = sorted(set(current_metrics) | set(prior_metrics))
        normalized: dict[str, dict[str, Any]] = {}
        decline_signals: list[str] = []
        warnings: list[str] = []
        for metric in metric_names:
            previous = number_or_none(prior_metrics.get(metric), f"prior metric {metric}")
            present = number_or_none(current_metrics.get(metric), f"current metric {metric}")
            percent_change = None
            absolute_change = None
            direction = "not_comparable"
            if previous is not None and present is not None:
                absolute_change = present - previous
                percent_change = (
                    round(absolute_change / abs(previous), 6) if previous != 0 else None
                )
                lower_is_better = metric.lower() in {
                    "average_position",
                    "avg_position",
                    "bounce_rate",
                    "error_rate",
                    "latency",
                    "lcp_ms",
                    "inp_ms",
                    "cls",
                }
                if math.isclose(present, previous):
                    direction = "stable"
                elif (present < previous and not lower_is_better) or (
                    present > previous and lower_is_better
                ):
                    direction = "worse"
                else:
                    direction = "better"
                if direction == "worse":
                    magnitude = (
                        abs(percent_change)
                        if percent_change is not None
                        else math.inf if previous == 0 and present != 0 else 0
                    )
                    if magnitude >= float(decline_threshold):
                        decline_signals.append(metric)
            else:
                warnings.append(f"Metric {metric} is missing from one comparison period.")
            normalized[metric] = {
                "prior": previous,
                "current": present,
                "absolute_change": absolute_change,
                "percent_change": percent_change,
                "direction": direction,
            }
        signal = "OBSERVED_DECLINE" if decline_signals else "NO_THRESHOLD_DECLINE_OBSERVED"
        if decline_signals:
            warnings.append(
                "Observed decline threshold exceeded for: " + ", ".join(decline_signals)
            )
        return AdapterResult(
            source=self.name,
            status="needs-review" if decline_signals else "ok",
            data={
                "operation": "decay",
                "data_state": "PARTIAL" if warnings else "AVAILABLE",
                "prior_period": {"start": prior_range[0].isoformat(), "end": prior_range[1].isoformat()},
                "current_period": {"start": current_range[0].isoformat(), "end": current_range[1].isoformat()},
                "decline_threshold": float(decline_threshold),
                "metrics": normalized,
                "decline_metrics": decline_signals,
                "decay_signal": signal,
                "cause": "NOT_ASSESSED",
                "recommended_next_evidence": [
                    "Confirm comparable query, page, market, device, and attribution scope.",
                    "Review technical, SERP, competitor, seasonality, and conversion evidence before assigning cause.",
                ],
                "limitations": [
                    "A period-over-period decline is an observation, not proof of content decay or its cause.",
                    "Metric definitions and attribution windows must be equivalent for a valid comparison.",
                ],
            },
            warnings=warnings,
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
