from __future__ import annotations

from datetime import date

import pytest

from integrations.content_intelligence.analysis import (
    bounded_records,
    compare_texts,
    meaningful_terms,
    normalize_sentence,
    parse_period,
    protected_tokens,
    safe_registry_url,
    sentences,
    validate_text,
)


def test_text_analysis_boundary_preserves_expected_token_semantics():
    text = "# Heading\n\nVerified sources help teams.  The teams compare tradeoffs!"

    assert sentences(text) == ["Verified sources help teams.", "The teams compare tradeoffs!"]
    assert normalize_sentence("  Mixed   CASE. ") == "mixed case."
    assert meaningful_terms(text) == {
        "heading",
        "verified",
        "sources",
        "help",
        "teams",
        "compare",
        "tradeoffs",
    }


def test_validation_boundary_rejects_unsafe_or_malformed_inputs():
    with pytest.raises(ValueError, match="embedded credentials"):
        safe_registry_url("https://user:secret@example.com/source")
    with pytest.raises(ValueError, match=r"HTTP\(S\)"):
        safe_registry_url("file:///tmp/source")
    with pytest.raises(TypeError, match="records must be a list"):
        bounded_records({}, "records")
    with pytest.raises(TypeError, match="every records item must be an object"):
        bounded_records([{"id": "valid"}, "invalid"], "records")
    with pytest.raises(ValueError, match="text cannot be empty"):
        validate_text("   ")


def test_period_and_protected_token_boundaries_are_deterministic():
    assert parse_period(
        {"period_start": "2026-01-01", "period_end": "2026-01-31"},
        "sample",
    ) == (date(2026, 1, 1), date(2026, 1, 31))
    with pytest.raises(ValueError, match="on or before"):
        parse_period(
            {"period_start": "2026-02-01", "period_end": "2026-01-31"},
            "sample",
        )

    assert protected_tokens("42% https://example.com/report [1]") == {
        "1",
        "42%",
        "https://example.com/report",
        "[1]",
    }


def test_comparison_boundary_reports_measurements_without_a_quality_judgment():
    comparison = compare_texts(
        "# Current\n\nUse verified sources. Explain tradeoffs.",
        "# Candidate\n\nUse verified sources. Include examples.",
        "current",
        "candidate",
    )

    assert comparison["left"]["label"] == "current"
    assert comparison["right"]["label"] == "candidate"
    assert comparison["exact_sentence_overlap"] == ["use verified sources."]
    assert "tradeoffs" in comparison["left_unique_terms"]
    assert "examples" in comparison["right_unique_terms"]
    assert "winner" not in comparison
