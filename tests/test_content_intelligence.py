from __future__ import annotations

from datetime import date

import pytest

from integrations.content_intelligence.service import ContentIntelligenceService


@pytest.fixture()
def service() -> ContentIntelligenceService:
    return ContentIntelligenceService()


def test_quality_scores_only_measurable_editorial_signals(service):
    text = """# Choosing an SEO Platform

By Bill Example

A useful platform should solve a defined workflow problem. It should also show where its evidence came from [1].

## What to evaluate

Teams should compare data coverage, failure handling, and implementation cost. A platform cannot prove business impact before it is tested against the team's actual objectives.
"""
    result = service.quality(
        text=text,
        title="Choosing an SEO Platform",
        audience="SEO leaders",
        purpose="Help a team evaluate software",
        author="Bill Example",
        sources=[{"id": "1", "title": "Evaluation standard"}],
    )
    assert result.status == "ok"
    assert result.data["diagnostic_score"]["scope"] == "measurable_editorial_signals_only"
    assert 0 <= result.data["diagnostic_score"]["value"] <= 100
    assert result.data["metrics"]["word_count"] > 30
    assert result.data["metrics"]["heading_count"] == 2
    assert result.data["signals"]["authorship_supplied"] is True
    assert result.data["signals"]["source_count"] == 1
    assert set(result.data["not_assessed"]) >= {
        "factual_accuracy",
        "originality",
        "author_expertise",
        "user_satisfaction",
        "ranking_potential",
    }
    assert result.data["google_ranking_score"] is None


def test_quality_does_not_invent_experience_or_expertise(service):
    result = service.quality(
        text="I tested three tools and preferred one. This is only a statement in the supplied text.",
        title="Tool test",
    )
    assert result.data["signals"]["first_person_language_present"] is True
    assert result.data["signals"]["first_hand_experience_verified"] is False
    assert "first-hand experience requires external evidence" in " ".join(result.warnings).lower()


def test_claim_verification_requires_reviewed_source_relationships(service):
    claims = [
        {
            "id": "c1",
            "text": "The product reduced processing time by 30%.",
            "source_ids": ["s1"],
        },
        {
            "id": "c2",
            "text": "The policy took effect in 2026.",
            "source_ids": ["s2"],
            "source_assessments": [
                {
                    "source_id": "s2",
                    "relation": "supports",
                    "reviewer": "analyst@example.com",
                    "reviewed_at": "2026-07-11",
                    "note": "Effective-date clause reviewed.",
                }
            ],
        },
    ]
    sources = [
        {"id": "s1", "title": "Vendor page", "url": "https://example.com/vendor"},
        {"id": "s2", "title": "Official policy", "url": "https://example.gov/policy", "primary": True},
    ]
    result = service.verify(claims=claims, sources=sources)
    states = {item["id"]: item["verification_state"] for item in result.data["claims"]}
    assert states["c1"] == "UNVERIFIED"
    assert states["c2"] == "SUPPORTED_BY_SUPPLIED_REVIEW"
    assert result.data["summary"]["unsupported_or_unverified"] == 1
    assert result.data["independent_source_fetch"] == "NOT_RUN"


def test_claim_verification_preserves_contradiction_and_missing_sources(service):
    claims = [
        {
            "id": "c1",
            "text": "A disputed claim.",
            "source_ids": ["missing"],
        },
        {
            "id": "c2",
            "text": "Another disputed claim.",
            "source_ids": ["s1"],
            "source_assessments": [
                {
                    "source_id": "s1",
                    "relation": "contradicts",
                    "reviewer": "reviewer",
                    "reviewed_at": "2026-07-11",
                }
            ],
        },
    ]
    result = service.verify(
        claims=claims,
        sources=[{"id": "s1", "title": "Primary record", "url": "https://example.org/record"}],
    )
    states = {item["id"]: item["verification_state"] for item in result.data["claims"]}
    assert states == {"c1": "SOURCE_MISSING", "c2": "CONTRADICTED_BY_SUPPLIED_REVIEW"}
    assert result.status == "needs-review"


def test_entities_separate_catalog_matches_from_heuristic_candidates(service):
    text = "OpenAI and Townsquare Media announced a project in Buffalo. The Buffalo team met Monday."
    catalog = [
        {"id": "openai", "name": "OpenAI", "aliases": []},
        {"id": "tsm", "name": "Townsquare Media", "aliases": ["Townsquare"]},
        {"id": "buffalo", "name": "Buffalo", "aliases": ["Buffalo, NY"]},
    ]
    result = service.entities(text=text, catalog=catalog)
    matched = {item["id"] for item in result.data["catalog_matches"]}
    assert matched == {"openai", "tsm", "buffalo"}
    assert all(item["evidence_state"] == "TEXT_MATCH_ONLY" for item in result.data["catalog_matches"])
    assert all(item["confidence"] == "LOW" for item in result.data["heuristic_candidates"])
    assert result.data["knowledge_graph_verification"] == "NOT_RUN"


def test_brief_requires_relevance_serp_information_gain_and_sources(service):
    relevance = {"verdict": "RELEVANT", "reasons": ["Audience fit"]}
    serp = {"status": "SUFFICIENT", "primary_intent": "commercial investigation"}
    result = service.brief(
        relevance=relevance,
        serp=serp,
        information_gains=["Original implementation benchmark"],
        sources=[{"id": "s1", "title": "Benchmark protocol", "primary": True}],
        audience="SEO leaders",
        intent="commercial investigation",
        primary_question="Which platform fits a governed SEO team?",
        required_sections=["Decision criteria", "Tradeoffs"],
    )
    assert result.status == "ok"
    assert result.data["publish_decision"] == "READY_FOR_DRAFT"
    assert result.data["source_register"][0]["id"] == "s1"
    assert result.data["information_gains"] == ["Original implementation benchmark"]

    blocked = service.brief(
        relevance={"verdict": "NOT_RELEVANT"},
        serp={"status": "SUFFICIENT"},
        information_gains=[],
        sources=[],
        audience="SEO leaders",
        intent="informational",
        primary_question="What is SEO?",
        required_sections=[],
    )
    assert blocked.status == "blocked"
    assert blocked.data["publish_decision"] == "BLOCKED"
    assert blocked.data["blocking_reasons"]


def test_decay_reports_observed_change_without_assigning_cause(service):
    prior = {
        "period_start": "2026-05-01",
        "period_end": "2026-05-31",
        "metrics": {"clicks": 1000, "impressions": 10000, "conversions": 40, "average_position": 4.0},
    }
    current = {
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
        "metrics": {"clicks": 650, "impressions": 9000, "conversions": 20, "average_position": 7.0},
    }
    result = service.decay(current=current, prior=prior, decline_threshold=0.2)
    assert result.status == "needs-review"
    assert result.data["metrics"]["clicks"]["percent_change"] == pytest.approx(-0.35)
    assert result.data["metrics"]["average_position"]["direction"] == "worse"
    assert result.data["decay_signal"] == "OBSERVED_DECLINE"
    assert result.data["cause"] == "NOT_ASSESSED"


def test_compare_reports_evidence_without_declaring_a_winner(service):
    left = "# Guide\n\nUse verified sources. Explain the tradeoffs."
    right = "# Guide\n\nUse verified sources. Include implementation examples."
    result = service.compare(left_text=left, right_text=right, left_label="current", right_label="competitor")
    assert result.status == "ok"
    assert result.data["winner"] is None
    assert result.data["exact_sentence_overlap"]
    assert "implementation" in result.data["right_unique_terms"]
    assert result.data["quality_superiority"] == "NOT_ASSESSED"


def test_humanize_is_clarity_only_and_preserves_numbers_urls_and_citations(service):
    text = (
        "In today's fast-paced digital landscape, it is important to note that the campaign delivered 42 leads. "
        "The full evidence is at https://example.com/report [1].  In conclusion, the next step is testing."
    )
    result = service.humanize(text=text)
    transformed = result.data["transformed_text"]
    assert "42" in transformed
    assert "https://example.com/report" in transformed
    assert "[1]" in transformed
    assert "fast-paced digital landscape" not in transformed.lower()
    assert result.data["purpose"] == "clarity_and_readability"
    assert result.data["ai_detector_evasion"] == "NOT_SUPPORTED"
    assert result.data["facts_verified"] is False
    assert result.data["changes"]


def test_duplicate_ids_and_invalid_dates_are_rejected(service):
    with pytest.raises(ValueError, match="duplicate claim id"):
        service.verify(
            claims=[{"id": "c1", "text": "A"}, {"id": "c1", "text": "B"}],
            sources=[],
        )
    with pytest.raises(ValueError, match="period"):
        service.decay(
            current={"period_start": "bad", "period_end": date.today().isoformat(), "metrics": {}},
            prior={"period_start": "2026-01-01", "period_end": "2026-01-31", "metrics": {}},
        )
