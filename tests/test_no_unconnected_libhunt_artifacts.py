from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_libhunt_source_matrix import validate as validate_libhunt_matrix


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _json(path: str) -> dict:
    return json.loads(_read(path))


def test_no_source_matrix_entry_lacks_targets_or_validation():
    assert validate_libhunt_matrix() == []
    matrix = _json("evaluation/libhunt-source-ingestion-matrix.json")
    for unit in matrix["upgrade_units"]:
        assert unit["target_files"], unit["id"]
        assert unit["verification_commands"], unit["id"]
        for target in unit["target_files"]:
            assert (ROOT / target).exists(), f"{unit['id']} target missing: {target}"


def test_libhunt_target_files_are_connected_to_tests_docs_or_validators():
    matrix_text = _read("evaluation/libhunt-source-ingestion-matrix.json")
    docs_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "docs").glob("*.md"))
    tests_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py"))
    for unit in _json("evaluation/libhunt-source-ingestion-matrix.json")["upgrade_units"]:
        haystack = "\n".join(unit["verification_commands"]) + "\n" + matrix_text + "\n" + docs_text + "\n" + tests_text
        for target in unit["target_files"]:
            assert target in haystack or Path(target).name in haystack, target


def test_no_bad_seo_fixture_is_orphaned():
    docs_and_tests = "\n".join(
        path.read_text(encoding="utf-8")
        for folder in ("docs", "tests", "evaluation")
        for path in (ROOT / folder).rglob("*")
        if path.is_file() and path.suffix in {".md", ".py", ".json"}
    )
    for fixture in (ROOT / "examples" / "bad-seo-fixtures").glob("*.json"):
        relative = fixture.relative_to(ROOT).as_posix()
        assert relative in docs_and_tests or fixture.name in docs_and_tests, relative
