from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_libhunt_source_matrix import MATRIX_PATH, validate


ROOT = Path(__file__).resolve().parents[1]


def test_libhunt_source_matrix_validates():
    assert validate() == []


def test_libhunt_source_matrix_forbids_blind_copying_and_dated_rules():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    forbidden = " ".join(matrix["source_policy"]["forbidden_use"]).lower()
    assert "copy external repo prose verbatim" in forbidden
    assert "copy external source code" in forbidden
    assert "dated checklist advice" in forbidden
    assert "orphan" in forbidden


def test_libhunt_source_matrix_names_expected_repositories():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    repos = {source["repo"] for source in matrix["sources"]}
    assert repos == {
        "joshbuchea/HEAD",
        "danishashko/geo-aeo-tracker",
        "every-app/open-seo",
        "marcobiedermann/search-engine-optimization",
        "bmpi-dev/awesome-seo",
        "garmeeh/next-seo",
        "iamvishnusankar/next-sitemap",
        "kjvarga/sitemap_generator",
        "goenning/google-indexing-script",
        "stevenvachon/broken-link-checker",
    }


def test_libhunt_external_inventory_paths_do_not_need_committed_clones():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert all(source["local_path"].startswith("../repositories/") for source in matrix["sources"])
    assert validate() == []


def test_libhunt_completed_units_target_existing_files():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    completed = [
        unit
        for unit in matrix["upgrade_units"]
        if unit["status"] in {"implemented", "verified"}
    ]
    assert completed
    for unit in completed:
        for target in unit["target_files"]:
            assert (ROOT / target).exists(), f"{unit['id']} target missing: {target}"


def test_libhunt_doc_points_to_canonical_json():
    doc = (ROOT / "docs" / "LIBHUNT-SOURCE-INGESTION-PLAN.md").read_text(
        encoding="utf-8"
    )
    assert "evaluation/libhunt-source-ingestion-matrix.json" in doc
    assert "Source governance and inventory" in doc
