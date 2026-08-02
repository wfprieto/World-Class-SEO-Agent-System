from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seoctl.agent_differentiation_mutations import (  # noqa: E402
    build_contract_mutants,
    build_evaluation_mutants,
)
from seoctl.registry import load_registry as load_command_registry  # noqa: E402

MATRIX_PATH = Path("governance/agent-responsibility-matrix.json")
REGISTRY_PATH = Path("orchestration/capability-registry.json")
CAPABILITY_OVERLAY_PATH = Path("orchestration/product-proof-capability-overlay.json")
EVALUATION_PATH = Path("evaluation/agent-differentiation/cases.json")
RESPONSIBILITY_KEYS = {
    "primary_responsibility",
    "evidence_anchor",
    "responsibility_id",
    "output_binding",
    "execution_class",
    "contributors",
    "consulted",
    "handoff_to",
}
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _effective_capabilities(
    registry: dict[str, Any], overlay: dict[str, Any]
) -> dict[str, Any]:
    active = copy.deepcopy(registry)
    merge_fields = ("skills", "skill_files", "knowledge_files", "templates", "required_evidence")
    for agent, override in overlay.get("agent_overrides", {}).items():
        if agent not in active.get("agents", {}):
            continue
        for field in merge_fields:
            values = active["agents"][agent].setdefault(field, [])
            for value in override.get(field, []):
                if value not in values:
                    values.append(value)
    return active


def _functional_signature(bundle: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(sorted(str(item) for item in bundle.get(field, [])))
        for field in ("skills", "required_evidence", "knowledge_files", "templates")
    )
def _functional_tokens(bundle: dict[str, Any]) -> set[str]:
    return {
        f"{field}:{item}"
        for field in ("skills", "required_evidence", "knowledge_files", "templates")
        for item in bundle.get(field, [])
    }
def _matrix_metadata_errors(matrix: dict[str, Any]) -> list[str]:
    errors = []
    if matrix.get("version") != "1.0.0":
        errors.append("responsibility matrix version must be 1.0.0")
    boundary = matrix.get("claim_boundary")
    if not isinstance(boundary, str) or "Bounded static differentiation" not in boundary:
        errors.append("responsibility matrix must declare its bounded static claim")
    return errors
def _inventory_errors(registry_names: set[str], matrix_names: set[str]) -> list[str]:
    missing = [
        f"retained agent has no responsibility contract: {name}"
        for name in sorted(registry_names - matrix_names)
    ]
    extra = [
        f"responsibility contract has no retained agent: {name}"
        for name in sorted(matrix_names - registry_names)
    ]
    return [*missing, *extra]
def _participant_errors(
    name: str, role: str, participants: Any, registry_names: set[str]
) -> list[str]:
    if not isinstance(participants, list) or not participants:
        return [f"{role} must declare at least one overlap participant: {name}"]
    errors = []
    if name in participants or len(participants) != len(set(participants)):
        errors.append(f"{role} contains an invalid or duplicate participant: {name}")
    errors.extend(
        f"{role} references an undeclared agent: {name} -> {participant}"
        for participant in participants
        if participant not in registry_names
    )
    return errors


def _agent_document_errors(root: Path, name: str, bundle: dict[str, Any]) -> list[str]:
    agent_file = bundle.get("agent_file")
    if not isinstance(agent_file, str) or not (root / agent_file).is_file():
        return [f"agent file is missing or unresolved: {name}"]
    document = (root / agent_file).read_text(encoding="utf-8")
    skills_section = re.search(
        r"^## Primary Skills\s*(.*?)(?=^## |\Z)", document, re.MULTILINE | re.DOTALL
    )
    output_section = re.search(
        r"^## Output\s*(.*?)(?=^## |\Z)", document, re.MULTILINE | re.DOTALL
    )
    documented_skills = list(
        dict.fromkeys(
            re.findall(
                r"`([a-z0-9][a-z0-9-]+)`",
                skills_section.group(1) if skills_section else "",
            )
        )
    )
    documented_templates = list(
        dict.fromkeys(
            re.findall(
                r"`(templates/[a-z0-9-]+\.md)`",
                output_section.group(1) if output_section else "",
            )
        )
    )
    errors = []
    if documented_skills != bundle.get("skills", []):
        errors.append(f"agent document Primary Skills do not match resolved bundle: {name}")
    if documented_templates != bundle.get("templates", []):
        errors.append(f"agent document Output does not match resolved bundle: {name}")
    return errors


def _agent_contract_errors(
    root: Path,
    name: str,
    bundle: dict[str, Any],
    contract: dict[str, Any],
    registry_names: set[str],
    evidence_counts: Counter[str],
    command_agents: dict[str, Any],
) -> tuple[list[str], str | None, str | None]:
    wrong_keys = set(contract) ^ RESPONSIBILITY_KEYS
    if wrong_keys:
        return ([f"agent responsibility contract must use exact keys for {name}: {sorted(wrong_keys)}"], None, None)
    errors = []
    responsibility = contract["primary_responsibility"]
    responsibility_key = None
    if not isinstance(responsibility, str) or len(responsibility.strip()) < 24:
        errors.append(f"primary responsibility is not substantive: {name}")
    else:
        responsibility_key = " ".join(responsibility.casefold().split())
    evidence = contract["evidence_anchor"]
    if not isinstance(evidence, str) or evidence not in bundle.get("required_evidence", []):
        errors.append(f"evidence anchor is not required by its agent: {name}")
    elif evidence_counts[evidence] != 1:
        errors.append(f"evidence anchor is not globally exclusive: {name} -> {evidence}")
    output = contract["responsibility_id"]
    output_key = output if isinstance(output, str) and SLUG.fullmatch(output) else None
    if output_key is None:
        errors.append(f"deterministic output must be a canonical slug: {name}")
    if contract["output_binding"] not in bundle.get("templates", []):
        errors.append(f"deterministic output is not bound to a declared template: {name}")
    command_row = command_agents.get(name)
    if not isinstance(command_row, dict) or contract["execution_class"] != command_row.get("execution_class"):
        errors.append(f"execution class does not match command registry: {name}")
    errors.extend(_participant_errors(name, "contributors", contract["contributors"], registry_names))
    errors.extend(_participant_errors(name, "consulted", contract["consulted"], registry_names))
    if contract["handoff_to"] not in registry_names or contract["handoff_to"] == name:
        errors.append(f"handoff direction is invalid: {name} -> {contract['handoff_to']}")
    errors.extend(_agent_document_errors(root, name, bundle))
    return errors, responsibility_key, output_key


def _duplicate_value_errors(values: dict[str, list[str]], label: str) -> list[str]:
    return [
        f"duplicate {label}: {value} -> {sorted(owners)}"
        for value, owners in values.items()
        if len(owners) > 1
    ]


def _capability_overlap_errors(registry_agents: dict[str, Any]) -> list[str]:
    signatures: defaultdict[tuple[tuple[str, ...], ...], list[str]] = defaultdict(list)
    for name, bundle in registry_agents.items():
        if isinstance(bundle, dict):
            signatures[_functional_signature(bundle)].append(name)
    errors = [
        "persona-only capability duplication: agents share the same functional signature -> "
        f"{sorted(owners)}"
        for owners in signatures.values()
        if len(owners) > 1
    ]
    names = sorted(registry_agents)
    for index, left_name in enumerate(names):
        left = _functional_tokens(registry_agents[left_name])
        for right_name in names[index + 1 :]:
            right = _functional_tokens(registry_agents[right_name])
            union = left | right
            similarity = len(left & right) / len(union) if union else 1.0
            if similarity >= 0.80:
                errors.append(
                    "near-clone capability duplication (Jaccard >= 0.80): "
                    f"{left_name} <-> {right_name} ({similarity:.3f})"
                )
    return errors


def _evaluation_case_errors(
    root: Path,
    agent: str,
    case: dict[str, Any],
    contract: dict[str, Any],
    responsibility_ids: set[Any],
) -> list[str]:
    expected = {
        "evidence_anchor": contract["evidence_anchor"],
        "responsibility_id": contract["responsibility_id"],
        "expected_artifact": contract["output_binding"],
        "execution_class": contract["execution_class"],
    }
    errors = [
        f"evaluation {field} does not bind to matrix: {agent}"
        for field, value in expected.items()
        if case.get(field) != value
    ]
    forbidden = case.get("forbidden_responsibility_id")
    if forbidden not in responsibility_ids or forbidden == contract["responsibility_id"]:
        errors.append(f"evaluation lacks a valid forbidden cross-agent behavior: {agent}")
    artifact = case.get("expected_artifact")
    if not isinstance(artifact, str) or not (root / artifact).is_file():
        errors.append(f"evaluation artifact is unresolved: {agent}")
    return errors


def _evaluation_errors(
    root: Path,
    evaluation: dict[str, Any],
    registry_names: set[str],
    matrix_agents: dict[str, Any],
) -> list[str]:
    cases = evaluation.get("cases")
    if not isinstance(cases, list):
        return ["agent differentiation evaluation must contain a cases list"]
    errors = []
    by_agent: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    case_ids = []
    for case in cases:
        if not isinstance(case, dict):
            errors.append("agent differentiation evaluation case must be an object")
            continue
        by_agent[str(case.get("agent", ""))].append(case)
        case_ids.append(str(case.get("id", "")))
    if len(case_ids) != len(set(case_ids)) or any(not item for item in case_ids):
        errors.append("agent differentiation evaluation case ids must be unique")
    responsibility_ids = {
        row.get("responsibility_id") for row in matrix_agents.values() if isinstance(row, dict)
    }
    for agent in sorted(registry_names):
        agent_cases = by_agent.get(agent, [])
        if len(agent_cases) != 1:
            errors.append(f"agent must have exactly one differentiation evaluation case: {agent}")
        elif agent in matrix_agents:
            errors.extend(
                _evaluation_case_errors(
                    root, agent, agent_cases[0], matrix_agents[agent], responsibility_ids
                )
            )
    errors.extend(
        f"evaluation references undeclared agent: {agent}"
        for agent in sorted(set(by_agent) - registry_names)
    )
    return errors


def validate_documents(
    root: Path,
    registry: dict[str, Any],
    matrix: dict[str, Any],
    command_registry: dict[str, Any] | None = None,
    evaluation: dict[str, Any] | None = None,
) -> list[str]:
    registry_agents = registry.get("agents")
    matrix_agents = matrix.get("agents")
    if not isinstance(registry_agents, dict) or not isinstance(matrix_agents, dict):
        return ["registry and responsibility matrix must each contain an agents object"]
    registry_names, matrix_names = set(registry_agents), set(matrix_agents)
    errors = [*_matrix_metadata_errors(matrix), *_inventory_errors(registry_names, matrix_names)]
    evidence_counts = Counter(
        str(evidence)
        for bundle in registry_agents.values()
        if isinstance(bundle, dict)
        for evidence in bundle.get("required_evidence", [])
    )
    responsibility_values: defaultdict[str, list[str]] = defaultdict(list)
    output_values: defaultdict[str, list[str]] = defaultdict(list)
    command_agents = (command_registry or {}).get("agents", {})
    for name in sorted(registry_names & matrix_names):
        bundle, contract = registry_agents[name], matrix_agents[name]
        if not isinstance(bundle, dict) or not isinstance(contract, dict):
            errors.append(f"agent contract must be an object: {name}")
            continue
        agent_errors, responsibility, output = _agent_contract_errors(
            root, name, bundle, contract, registry_names, evidence_counts, command_agents
        )
        errors.extend(agent_errors)
        if responsibility is not None:
            responsibility_values[responsibility].append(name)
        if output is not None:
            output_values[output].append(name)
    errors.extend(_duplicate_value_errors(responsibility_values, "primary responsibility"))
    errors.extend(_duplicate_value_errors(output_values, "deterministic output responsibility"))
    errors.extend(_capability_overlap_errors(registry_agents))
    if evaluation is not None:
        errors.extend(_evaluation_errors(root, evaluation, registry_names, matrix_agents))
    return errors


def validate_repository(root: Path = ROOT) -> list[str]:
    registry = _effective_capabilities(
        _load(root / REGISTRY_PATH), _load(root / CAPABILITY_OVERLAY_PATH)
    )
    return validate_documents(
        root,
        registry,
        _load(root / MATRIX_PATH),
        load_command_registry(),
        _load(root / EVALUATION_PATH),
    )


def _mutation_result(name: str, expected: str, errors: list[str]) -> dict[str, Any]:
    killed = any(expected in error for error in errors)
    return {"name": name, "killed": killed, "expected": expected, "errors": errors}


def _evaluation_mutation_results(
    root: Path,
    registry: dict[str, Any],
    matrix: dict[str, Any],
    command_registry: dict[str, Any],
    evaluation: dict[str, Any],
) -> list[dict[str, Any]]:
    results = []
    for name, candidate, expected in build_evaluation_mutants(evaluation):
        errors = validate_documents(root, registry, matrix, command_registry, candidate)
        results.append(_mutation_result(name, expected, errors))
    return results


def run_mutation_suite(root: Path = ROOT) -> dict[str, Any]:
    registry = _effective_capabilities(
        _load(root / REGISTRY_PATH), _load(root / CAPABILITY_OVERLAY_PATH)
    )
    matrix = _load(root / MATRIX_PATH)
    command_registry = load_command_registry()
    evaluation = _load(root / EVALUATION_PATH)
    mutants = build_contract_mutants(registry, matrix)
    results = []
    for name, candidate_registry, candidate_matrix, expected in mutants:
        errors = validate_documents(
            root, candidate_registry, candidate_matrix, command_registry, evaluation
        )
        results.append(_mutation_result(name, expected, errors))
    results.extend(
        _evaluation_mutation_results(root, registry, matrix, command_registry, evaluation)
    )
    return {
        "status": "PASS" if all(item["killed"] for item in results) else "FAIL",
        "mutants": len(results),
        "killed": sum(bool(item["killed"]) for item in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bounded agent differentiation contracts.")
    parser.add_argument("--mutations", action="store_true", help="run the fixed overlap mutation suite")
    args = parser.parse_args()
    errors = validate_repository()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.mutations:
        result = run_mutation_suite()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    print("Agent differentiation contract: PASS (25 retained agents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
