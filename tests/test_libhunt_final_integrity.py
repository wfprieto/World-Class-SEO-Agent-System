from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_libhunt_source_matrix import validate as validate_libhunt_matrix
from scripts.validate_reference_freshness import validate as validate_references


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_framework_pack_is_advisory_and_rendered_output_first():
    body = _read("knowledge/reference-packs/framework-seo-implementation-expanded.md")
    assert "framework implementation notes are advisory" in body
    assert "validate the rendered output" in body
    assert "not a generic ranking lever" in body
    assert "A single tool failure must not erase other evidence" in body


def test_framework_pack_is_registry_connected_to_real_skills():
    assert validate_references() == []
    registry = json.loads(_read("knowledge/reference-registry.json"))
    entries = [
        entry
        for entry in registry["entries"]
        if entry["pack"] == "framework-seo-implementation-expanded"
    ]
    assert {entry["id"] for entry in entries} == {
        "framework-metadata-boundary",
        "structured-data-component-gate",
        "sitemap-generation-patterns",
        "adapter-hardening-patterns",
    }
    for entry in entries:
        assert entry["affected_skills"]
        assert entry["affected_agents"]


def test_libhunt_upgrade_units_all_verified_and_target_existing_files():
    assert validate_libhunt_matrix() == []
    matrix = json.loads(_read("evaluation/libhunt-source-ingestion-matrix.json"))
    assert {unit["status"] for unit in matrix["upgrade_units"]} <= {"verified"}
    for unit in matrix["upgrade_units"]:
        for target in unit["target_files"]:
            assert (ROOT / target).exists(), target


def test_final_upgrade_documents_cross_link_canonical_artifacts():
    report = _read("docs/APIVR-LIBHUNT-UPGRADE-REPORT.md")
    review = _read("docs/20-PASS-LIBHUNT-UPGRADE-REVIEW.md")
    assert "evaluation/libhunt-source-ingestion-matrix.json" in report
    assert "knowledge/reference-registry.json" in report
    assert "20-pass protocol" in review.lower()
    assert "APIVR" in review
