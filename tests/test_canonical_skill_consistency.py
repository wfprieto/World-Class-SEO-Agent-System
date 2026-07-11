from __future__ import annotations

from scripts.validate_canonical_skill_consistency import indexed_skills, procedure_sections, validate


def test_every_indexed_skill_heading_survives_source_convergence():
    sections, headings = procedure_sections()
    assert set(sections) == indexed_skills()
    assert len(headings) == len(set(headings)) == len(indexed_skills())


def test_existing_repository_semantic_deep_procedure_gate_still_passes():
    sections, _ = procedure_sections()
    assert not (indexed_skills() - set(sections))


def test_local_deep_procedures_do_not_restore_removed_rules():
    sections, _ = procedure_sections()
    blob = "\n".join(
        sections[name]
        for name in ("geo-grid-rank-scan", "gbp-profile-audit", "cross-platform-nap-verify")
    ).lower()
    assert "haversine offset" not in blob
    assert "25 ranking-relevant fields" not in blob
    assert "name mismatch critical" not in blob


def test_comparison_procedure_has_no_fixed_word_count_or_default_schema():
    sections, _ = procedure_sections()
    blob = sections["competitor-comparison-page-build"].lower()
    assert "1,500 words" not in blob
    assert "generate product/softwareapplication/itemlist schema" not in blob
    assert "skills/competitor-comparison-pages.md" in blob


def test_programmatic_procedure_does_not_turn_internal_thresholds_into_policy():
    sections, _ = procedure_sections()
    blob = sections["programmatic-seo-governance"].lower()
    for forbidden in ("warn at 30", "hard stop at 50", "below 60%", "below 40%"):
        assert forbidden not in blob
    assert "skills/programmatic-seo-governance.md" in blob


def test_canonical_consistency_validator_passes():
    assert validate() == []
