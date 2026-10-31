"""Deterministic content intelligence with explicit truth boundaries.

The service measures supplied text and supplied review records. It does not
claim Google ranking potential, originality, factual accuracy, expertise,
source existence, user satisfaction, or causal explanations that were not
independently established.
"""

from __future__ import annotations

from typing import Any

from contracts.adapter import AdapterResult
from integrations.content_intelligence.analysis import (
    bounded_records,
    diagnostic_check,
    mean,
    quality_measurements,
    validate_text,
)


def quality(
    name: str,
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
    checks = _quality_checks(
        title,
        audience,
        purpose,
        author,
        source_rows,
        sentence_lengths,
        paragraph_lengths,
        metrics,
        duplicates,
        headings,
    )
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
        warnings.append(
            "Measured editorial signals fall below the configured diagnostic threshold of 70."
        )
    return AdapterResult(
        source=name,
        status="ok" if score >= 70 else "needs-review",
        data=_quality_data(
            metrics,
            headings,
            duplicates,
            author,
            reviewed_by,
            source_rows,
            first_person,
            risk_class,
            checks,
            score,
        ),
        warnings=warnings,
    )


def _quality_checks(
    title: str | None,
    audience: str | None,
    purpose: str | None,
    author: str | None,
    source_rows: list[dict[str, Any]],
    sentence_lengths: list[int],
    paragraph_lengths: list[int],
    metrics: dict[str, Any],
    duplicates: list[str],
    headings: list[str],
) -> list[dict[str, Any]]:
    return [
        diagnostic_check(
            "descriptive_title_supplied",
            bool(title and 8 <= len(title.strip()) <= 100),
            15,
            {"title": title},
        ),
        diagnostic_check(
            "audience_supplied", bool(audience and audience.strip()), 10, {"audience": audience}
        ),
        diagnostic_check(
            "purpose_supplied", bool(purpose and purpose.strip()), 10, {"purpose": purpose}
        ),
        diagnostic_check(
            "authorship_supplied", bool(author and author.strip()), 10, {"author": author}
        ),
        diagnostic_check(
            "source_register_supplied", bool(source_rows), 10, {"source_count": len(source_rows)}
        ),
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
        diagnostic_check(
            "duplicate_sentences_absent", not duplicates, 10, {"duplicates": duplicates[:20]}
        ),
        diagnostic_check(
            "heading_structure_present", bool(headings), 10, {"headings": headings[:50]}
        ),
    ]


def _quality_data(
    metrics: dict[str, Any],
    headings: list[str],
    duplicates: list[str],
    author: str | None,
    reviewed_by: str | None,
    source_rows: list[dict[str, Any]],
    first_person: bool,
    risk_class: str,
    checks: list[dict[str, Any]],
    score: float,
) -> dict[str, Any]:
    return {
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
    }
