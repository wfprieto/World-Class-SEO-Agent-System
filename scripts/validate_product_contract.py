"""Validate product identity, proof boundaries, and complete capability classification."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_capability_evidence_registry import (  # noqa: E402
    NETWORK_EXECUTION_MODES,
    _effective_command_registry,
    _skill_ids,
)
from scripts.generate_capability_evidence_registry import (  # noqa: E402
    build as build_evidence_registry,
)
from seoctl.capability_certification import RECEIPT_ROOT, validate_receipt  # noqa: E402
from seoctl.registry import command_specs  # noqa: E402

CONTRACT_PATH = Path("governance/product-contract.json")
EVIDENCE_PATH = Path("orchestration/capability-evidence-registry.json")
EXPECTED_AUTHORITIES = {
    "README.md",
    "SYSTEM_SPEC.md",
    "pyproject.toml",
    "docs/QUICKSTART.md",
    "skills/product-proof-technical-audit.md",
}
EVIDENCE_CLASSES = {"SOURCE", "AUTOMATED", "CI", "PROVIDER", "DEPLOYED", "OPERATIONAL"}
EVIDENCE_STATUSES = {"PASS", "FAIL", "NOT_RUN", "OUT_OF_SCOPE"}
DELIVERY_STATES = {"COMMAND_BACKED", "RUNTIME_CONTEXT", "DOCUMENTED_ONLY"}
EXECUTION_MODES = {*NETWORK_EXECUTION_MODES.values(), "FIXTURE_CAPABLE", "ADVISORY"}
CLAIM_CEILINGS = {
    "DOCUMENTED_ONLY",
    "REGISTRY_VERIFIED",
    "FIXTURE_VERIFIED",
    "LIVE_CAPABLE_NOT_VERIFIED",
    "LIVE_VERIFIED",
}
PROVIDER_RECEIPT_ROOT = PurePosixPath(RECEIPT_ROOT.as_posix())


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _runtime_artifact_filenames(root: Path) -> set[str]:
    """Read the selected root's literal contract without importing another checkout."""
    path = root / "integrations" / "product_proof" / "service.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "ARTIFACT_FILENAMES" for target in targets):
            continue
        value_node = node.value
        if value_node is None:
            break
        value = ast.literal_eval(value_node)
        if not isinstance(value, dict) or any(
            not isinstance(name, str) or not name for name in value.values()
        ):
            raise ValueError("runtime ARTIFACT_FILENAMES must be a literal string mapping")
        return set(value.values())
    raise ValueError(f"runtime ARTIFACT_FILENAMES literal is missing: {path}")


def _safe_evidence_reference(root: Path, reference: object) -> str | None:
    if not isinstance(reference, str) or not reference:
        return "reference must be a non-empty string"
    if "\\" in reference:
        return "reference must use repository-relative POSIX separators"
    relative = PurePosixPath(reference)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        return "reference must be a normalized repository-relative path"
    candidate = (root / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return "reference resolves outside the repository"
    if not candidate.is_file():
        return "reference does not identify an existing file"
    return None


def _provider_receipt_problem(
    root: Path,
    reference: object,
    kind: str,
    item_id: str,
    allowed_commands: set[str],
) -> str | None:
    if not isinstance(reference, str):
        return "provider receipt reference must be a string"
    relative = PurePosixPath(reference)
    if relative.suffix != ".json" or relative.parent != PROVIDER_RECEIPT_ROOT:
        return f"provider receipt must be a JSON file directly under {PROVIDER_RECEIPT_ROOT}"
    receipt, errors = validate_receipt(root, root / Path(*relative.parts))
    if errors:
        return "; ".join(errors)
    assert receipt is not None
    capability_id = str(receipt["capability"]["id"])
    if kind == "commands" and capability_id != item_id:
        return "provider receipt capability binding does not match the classified command"
    if kind == "skills" and capability_id not in allowed_commands:
        return "provider receipt is not bound to a backing command for the classified skill"
    return None


def _validate_evidence_record(
    root: Path,
    kind: str,
    item_id: str,
    evidence_class: str,
    record: object,
    errors: list[str],
) -> None:
    if not isinstance(record, dict) or set(record) != {"status", "refs"}:
        errors.append(f"{kind} {item_id} {evidence_class} must contain only status and refs")
        return
    status = record["status"]
    refs = record["refs"]
    if status not in EVIDENCE_STATUSES:
        errors.append(f"{kind} {item_id} {evidence_class} has invalid status {status!r}")
    if not isinstance(refs, list):
        errors.append(f"{kind} {item_id} {evidence_class} refs must be a list")
        return
    if len(refs) != len({str(reference) for reference in refs}):
        errors.append(f"{kind} {item_id} {evidence_class} refs contain duplicates")
    if status == "PASS" and not refs:
        errors.append(f"{kind} {item_id} {evidence_class} PASS has no references")
    if status != "PASS" and refs:
        errors.append(f"{kind} {item_id} {evidence_class} {status} must not cite proof")
    for reference in refs:
        problem = _safe_evidence_reference(root, reference)
        if problem:
            errors.append(
                f"{kind} {item_id} {evidence_class} invalid reference {reference!r}: {problem}"
            )


def _validate_evidence_map(
    root: Path, kind: str, item_id: str, evidence_map: object, errors: list[str]
) -> dict[str, Any] | None:
    if not isinstance(evidence_map, dict) or set(evidence_map) != EVIDENCE_CLASSES:
        actual = set(evidence_map) if isinstance(evidence_map, dict) else set()
        errors.append(
            f"{kind} {item_id} has incomplete evidence-class coverage; "
            f"missing={sorted(EVIDENCE_CLASSES - actual)}; extra={sorted(actual - EVIDENCE_CLASSES)}"
        )
        return None
    for evidence_class in sorted(EVIDENCE_CLASSES):
        _validate_evidence_record(
            root, kind, item_id, evidence_class, evidence_map[evidence_class], errors
        )
    return evidence_map


def _validate_claim_proof(
    root: Path,
    kind: str,
    item_id: str,
    row: dict[str, Any],
    evidence_map: dict[str, Any],
    errors: list[str],
) -> None:
    claim_ceiling = row.get("claim_ceiling")
    source_pass = evidence_map["SOURCE"].get("status") == "PASS"
    automated_pass = evidence_map["AUTOMATED"].get("status") == "PASS"
    if claim_ceiling in {"REGISTRY_VERIFIED", "FIXTURE_VERIFIED", "LIVE_VERIFIED"} and not (
        source_pass and automated_pass
    ):
        errors.append(f"{kind} {item_id} {claim_ceiling} requires source and automated proof")
    if claim_ceiling == "LIVE_VERIFIED":
        provider_record = evidence_map["PROVIDER"]
        if provider_record.get("status") != "PASS":
            errors.append(f"{kind} {item_id} claims LIVE_VERIFIED without provider evidence")
        else:
            provider_refs = provider_record.get("refs", [])
            receipt_problems = [
                problem
                for reference in provider_refs
                if (
                    problem := _provider_receipt_problem(
                        root,
                        reference,
                        kind,
                        item_id,
                        {str(item) for item in row.get("backing_commands", [])},
                    )
                )
            ]
            if receipt_problems:
                errors.extend(
                    f"{kind} {item_id} LIVE_VERIFIED invalid PROVIDER provenance: {problem}"
                    for problem in receipt_problems
                )


def _validate_evidence_row(
    root: Path, kind: str, item_id: str, row: object, errors: list[str]
) -> None:
    if not isinstance(row, dict):
        errors.append(f"{kind} {item_id} classification must be an object")
        return
    delivery_state = row.get("delivery_state")
    execution_mode = row.get("execution_mode")
    claim_ceiling = row.get("claim_ceiling")
    if delivery_state not in DELIVERY_STATES:
        errors.append(f"{kind} {item_id} has invalid delivery_state {delivery_state!r}")
    if execution_mode not in EXECUTION_MODES:
        errors.append(f"{kind} {item_id} has invalid execution_mode {execution_mode!r}")
    if claim_ceiling not in CLAIM_CEILINGS:
        errors.append(f"{kind} {item_id} has invalid claim_ceiling {claim_ceiling!r}")
    evidence_map = _validate_evidence_map(root, kind, item_id, row.get("evidence"), errors)
    if evidence_map is None:
        return
    _validate_claim_proof(root, kind, item_id, row, evidence_map, errors)
    if delivery_state == "DOCUMENTED_ONLY" and (
        claim_ceiling != "DOCUMENTED_ONLY" or execution_mode != "ADVISORY"
    ):
        errors.append(f"{kind} {item_id} promotes a documented-only capability")
    if claim_ceiling == "REGISTRY_VERIFIED" and execution_mode != "DETERMINISTIC":
        errors.append(f"{kind} {item_id} REGISTRY_VERIFIED must be deterministic")
    if claim_ceiling == "FIXTURE_VERIFIED" and execution_mode not in {
        "FIXTURE_CAPABLE",
        "LIVE_CAPABLE",
    }:
        errors.append(f"{kind} {item_id} FIXTURE_VERIFIED has incompatible execution mode")


def validate(root: Path = ROOT) -> list[str]:  # noqa: C901 - canonical contract audit
    root = root.resolve()
    errors: list[str] = []
    try:
        contract = _json(root / CONTRACT_PATH)
        schema = _json(root / "schemas" / "product-contract.schema.json")
        jsonschema.Draft202012Validator(schema).validate(contract)
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        return [f"product contract schema validation failed: {exc}"]

    surfaces = contract["authoritative_surfaces"]
    configured = [str(row["path"]) for row in surfaces]
    if len(configured) != len(set(configured)):
        errors.append("authoritative product surfaces must not contain duplicate paths")
    configured_set = set(configured)
    if configured_set != EXPECTED_AUTHORITIES:
        errors.append(
            "authoritative surface inventory mismatch; "
            f"missing={sorted(EXPECTED_AUTHORITIES - configured_set)}; "
            f"extra={sorted(configured_set - EXPECTED_AUTHORITIES)}"
        )
    for row in surfaces:
        relative = str(row["path"])
        reference_problem = _safe_evidence_reference(root, relative)
        if reference_problem:
            errors.append(f"invalid authoritative product surface {relative!r}: {reference_problem}")
            continue
        text = (root / relative).read_text(encoding="utf-8-sig")
        for term in row["required_terms"]:
            if str(term) not in text:
                errors.append(f"{relative} is missing canonical product term: {term}")
        for pattern in contract["claim_language_policy"]["prohibited_patterns"]:
            try:
                match = re.search(str(pattern), text, flags=re.IGNORECASE)
            except re.error as exc:
                errors.append(f"invalid prohibited product-claim pattern {pattern!r}: {exc}")
                continue
            if match:
                errors.append(
                    f"{relative} contains prohibited product wording matched by {pattern!r}: "
                    f"{match.group(0)!r}"
                )

    try:
        registry, _ = _effective_command_registry(root)
        specs = command_specs(registry)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return [*errors, f"effective command registry could not be loaded: {exc}"]
    flagship = contract["flagship"]
    matches = [spec for spec in specs if spec.id == flagship["command_id"]]
    if len(matches) != 1:
        errors.append("exactly one effective flagship command must exist")
    elif matches[0].owner != flagship["owner"] or flagship["skill"] not in matches[0].skills:
        errors.append("flagship owner or skill disagrees with the effective command registry")
    try:
        runtime_artifacts = _runtime_artifact_filenames(root)
    except (OSError, SyntaxError, ValueError) as exc:
        errors.append(f"flagship runtime artifact contract could not be read: {exc}")
    else:
        if set(flagship["artifacts"]) != runtime_artifacts:
            errors.append("flagship artifact inventory disagrees with runtime ARTIFACT_FILENAMES")

    try:
        evidence = _json(root / EVIDENCE_PATH)
        generated = build_evidence_registry(root)
        effective_command_ids = {spec.id for spec in specs}
        effective_skill_ids = set(_skill_ids(root))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return [*errors, f"capability evidence registry could not be built: {exc}"]
    if evidence != generated:
        errors.append(
            "capability evidence registry is stale or does not match effective base-plus-overlay inventories"
        )
    if evidence.get("schema_version") != "1.1.0":
        errors.append("capability evidence registry schema_version must be 1.1.0")
    expected_inventories = {"commands": effective_command_ids, "skills": effective_skill_ids}
    for kind in ("commands", "skills"):
        rows = evidence.get(kind)
        if not isinstance(rows, dict):
            errors.append(f"capability evidence {kind} must be an object")
            continue
        actual_ids = {str(item_id) for item_id in rows}
        expected_ids = expected_inventories[kind]
        if actual_ids != expected_ids:
            errors.append(
                f"capability evidence {kind} inventory mismatch; "
                f"missing={sorted(expected_ids - actual_ids)}; extra={sorted(actual_ids - expected_ids)}"
            )
        for item_id, row in sorted(rows.items()):
            _validate_evidence_row(root, kind, str(item_id), row, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = validate(args.root)
    print(json.dumps({"status": "ok" if not errors else "failed", "failures": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
