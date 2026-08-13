from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_upgrade_source_matrix import MATRIX_PATH, validate


ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_source_matrix_validates():
    assert validate() == []


def test_upgrade_source_matrix_forbids_blind_copying():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    forbidden = " ".join(matrix["source_policy"]["forbidden_use"]).lower()
    assert "copy external repo prose verbatim" in forbidden
    assert "copy external source code" in forbidden
    assert "orphan imports" in forbidden


def test_upgrade_source_matrix_names_all_inventoried_repositories():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    repos = {source["repo"] for source in matrix["sources"]}
    assert repos == {
        "AgriciDaniel/claude-seo",
        "every-app/open-seo",
        "stefankirkegaard/open-seo-github",
        "TahaHachana/OpenSEO",
    }


def test_completed_upgrade_units_target_existing_files():
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


def test_source_matrix_doc_points_to_canonical_json():
    doc = (ROOT / "docs" / "SOURCE-INSPIRED-UPGRADE-MATRIX.md").read_text(
        encoding="utf-8"
    )
    assert "evaluation/upgrade-source-matrix.json" in doc
    assert "Phase 1 is verified" in doc
