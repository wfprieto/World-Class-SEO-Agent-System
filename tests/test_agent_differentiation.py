from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_agent_differentiation import (
    MATRIX_PATH,
    REGISTRY_PATH,
    run_mutation_suite,
    validate_documents,
    validate_repository,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_retained_agent_has_a_distinct_responsibility_contract() -> None:
    assert validate_repository(ROOT) == []


def test_fixed_overlap_mutation_suite_kills_every_known_case() -> None:
    result = run_mutation_suite(ROOT)
    assert result["status"] == "PASS"
    assert result["mutants"] == result["killed"] == 11


def test_persona_rename_cannot_rescue_a_duplicated_functional_bundle() -> None:
    registry = _load(ROOT / REGISTRY_PATH)
    matrix = _load(ROOT / MATRIX_PATH)
    registry = copy.deepcopy(registry)
    matrix = copy.deepcopy(matrix)
    source = "SEO Technical Agent"
    clone = "Renamed Technical Expert Persona"
    registry["agents"][clone] = copy.deepcopy(registry["agents"][source])
    matrix["agents"][clone] = {
        "primary_responsibility": "Use a different persona label while doing the same declared work.",
        "evidence_anchor": "domain_or_urls",
        "responsibility_id": "renamed-technical-report",
        "output_binding": "templates/audit-report.md",
        "execution_class": "executable",
        "contributors": ["SEO Diagnostic Infrastructure Agent"],
        "consulted": ["Senior SEO Engineer Agent"],
        "handoff_to": "Senior SEO Engineer Agent",
    }

    errors = validate_documents(ROOT, registry, matrix)

    assert any("persona-only capability duplication" in error for error in errors)


def test_evidence_anchor_must_be_declared_and_globally_exclusive() -> None:
    registry = _load(ROOT / REGISTRY_PATH)
    matrix = _load(ROOT / MATRIX_PATH)
    matrix = copy.deepcopy(matrix)
    matrix["agents"]["Voice Search & Conversational Agent"]["evidence_anchor"] = "audience"

    errors = validate_documents(ROOT, registry, matrix)

    assert any("evidence anchor is not globally exclusive" in error for error in errors)


def test_deterministic_output_must_have_one_owner() -> None:
    registry = _load(ROOT / REGISTRY_PATH)
    matrix = _load(ROOT / MATRIX_PATH)
    matrix = copy.deepcopy(matrix)
    matrix["agents"]["SEO Accessibility Agent"]["responsibility_id"] = (
        matrix["agents"]["SEO Technical Agent"]["responsibility_id"]
    )

    errors = validate_documents(ROOT, registry, matrix)

    assert any("duplicate deterministic output responsibility" in error for error in errors)


def test_matrix_and_retained_agent_inventory_must_match_exactly() -> None:
    registry = _load(ROOT / REGISTRY_PATH)
    matrix = _load(ROOT / MATRIX_PATH)
    matrix = copy.deepcopy(matrix)
    matrix["agents"].pop("SEO E-commerce Agent")

    errors = validate_documents(ROOT, registry, matrix)

    assert any("retained agent has no responsibility contract" in error for error in errors)
