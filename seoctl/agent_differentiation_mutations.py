from __future__ import annotations

import copy
from typing import Any

Mutation = tuple[str, dict[str, Any], dict[str, Any], str]
EvaluationMutation = tuple[str, dict[str, Any], str]


def _clone_mutants(registry: dict[str, Any], matrix: dict[str, Any]) -> list[Mutation]:
    source = "SEO Technical Agent"
    cloned_registry, cloned_matrix = copy.deepcopy(registry), copy.deepcopy(matrix)
    clone = "Technical SEO Expert Persona"
    cloned_registry["agents"][clone] = copy.deepcopy(registry["agents"][source])
    cloned_matrix["agents"][clone] = copy.deepcopy(matrix["agents"][source])
    cloned_matrix["agents"][clone]["primary_responsibility"] = (
        "Provide an alternate expert persona for the same technical capability bundle."
    )
    cloned_matrix["agents"][clone]["responsibility_id"] = "alternate-technical-report"

    near_registry, near_matrix = copy.deepcopy(registry), copy.deepcopy(matrix)
    near = "Decorated Technical Persona"
    near_registry["agents"][near] = copy.deepcopy(registry["agents"][source])
    near_registry["agents"][near]["skills"].append("decorative-persona-skill")
    near_matrix["agents"][near] = copy.deepcopy(matrix["agents"][source])
    near_matrix["agents"][near]["primary_responsibility"] = (
        "Restate technical work with a decorative capability and alternate persona."
    )
    near_matrix["agents"][near]["responsibility_id"] = "decorated-technical-report"
    return [
        ("persona-only-clone", cloned_registry, cloned_matrix, "persona-only"),
        ("near-clone-decoration", near_registry, near_matrix, "near-clone"),
    ]


def _matrix_mutants(registry: dict[str, Any], matrix: dict[str, Any]) -> list[Mutation]:
    source = "SEO Technical Agent"
    duplicate = copy.deepcopy(matrix)
    duplicate["agents"]["SEO Accessibility Agent"]["responsibility_id"] = (
        matrix["agents"][source]["responsibility_id"]
    )
    shared = copy.deepcopy(matrix)
    shared["agents"]["Voice Search & Conversational Agent"]["evidence_anchor"] = "audience"
    missing = copy.deepcopy(matrix)
    missing["agents"].pop("SEO E-commerce Agent")
    contributor = copy.deepcopy(matrix)
    contributor["agents"][source]["contributors"] = ["Unknown Agent Persona"]
    template = copy.deepcopy(matrix)
    template["agents"][source]["output_binding"] = "templates/content-brief.md"
    advisory = copy.deepcopy(matrix)
    advisory["agents"]["SEO Accessibility Agent"]["execution_class"] = "executable"
    handoff = copy.deepcopy(matrix)
    handoff["agents"][source]["handoff_to"] = "SEO Output Report Agent"
    swapped = copy.deepcopy(matrix)
    left, right = swapped["agents"][source], swapped["agents"]["SEO Copywriter/Content Agent"]
    left["responsibility_id"], right["responsibility_id"] = (
        right["responsibility_id"],
        left["responsibility_id"],
    )
    return [
        ("duplicate-output-owner", registry, duplicate, "duplicate deterministic output"),
        ("shared-evidence-anchor", registry, shared, "not globally exclusive"),
        ("unmapped-retained-agent", registry, missing, "no responsibility contract"),
        ("undeclared-contributor", registry, contributor, "undeclared agent"),
        ("wrong-template-binding", registry, template, "not bound"),
        ("advisory-class-mismatch", registry, advisory, "execution class"),
        ("handoff-target-substitution", registry, handoff, "evaluation expected_handoff_to"),
        ("responsibility-owner-swap", registry, swapped, "evaluation responsibility_id"),
    ]


def build_contract_mutants(registry: dict[str, Any], matrix: dict[str, Any]) -> list[Mutation]:
    return [*_clone_mutants(registry, matrix), *_matrix_mutants(registry, matrix)]


def build_evaluation_mutants(evaluation: dict[str, Any]) -> list[EvaluationMutation]:
    missing = copy.deepcopy(evaluation)
    missing["cases"].pop()
    duplicate = copy.deepcopy(evaluation)
    duplicate["cases"].append(copy.deepcopy(duplicate["cases"][0]))
    return [
        ("missing-agent-evaluation", missing, "exactly one differentiation evaluation"),
        ("duplicate-agent-evaluation", duplicate, "case ids must be unique"),
    ]
