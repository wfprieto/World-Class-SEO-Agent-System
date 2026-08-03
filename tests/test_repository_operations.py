from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_repository_operations import validate

ROOT = Path(__file__).resolve().parents[1]
Mutation = Callable[[dict[str, Any]], None]


def _copy_surface(tmp_path: Path) -> Path:
    for relative in (
        "schemas/repository-operations.schema.json",
        "governance/repository-operations.json",
        "docs/REPOSITORY-OPERATIONS.md",
    ):
        source = ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return tmp_path


def _mutate(tmp_path: Path, mutation: Mutation) -> list[str]:
    root = _copy_surface(tmp_path)
    contract_path = root / "governance/repository-operations.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    mutation(contract)
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return validate(root)


def test_repository_operations_contract_is_valid() -> None:
    assert validate() == []


def test_contract_requires_exactly_seven_canonical_paths(tmp_path: Path) -> None:
    errors = _mutate(tmp_path, lambda contract: contract["critical_paths"].pop())
    assert any("too short" in error or "seven canonical ids" in error for error in errors)


def test_critical_paths_and_issues_must_be_unique(tmp_path: Path) -> None:
    def duplicate(contract: dict[str, Any]) -> None:
        contract["critical_paths"][1] = copy.deepcopy(contract["critical_paths"][0])

    errors = _mutate(tmp_path, duplicate)
    assert any("ids must be unique" in error for error in errors)
    assert any("unique GitHub issues" in error for error in errors)


def test_canonical_path_cannot_bind_a_different_issue(tmp_path: Path) -> None:
    def renumber(contract: dict[str, Any]) -> None:
        issue = contract["critical_paths"][0]["issue"]
        issue["number"] = 99
        issue["url"] = "https://github.com/wfprieto/World-Class-SEO-Agent-System/issues/99"

    errors = _mutate(tmp_path, renumber)
    assert any("must bind issue #26" in error for error in errors)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("owner", "", "should be non-empty"),
        ("verification", [], "should be non-empty"),
        ("metric", "", "should be non-empty"),
        ("threshold", "", "should be non-empty"),
        ("rollback_trigger", "", "should be non-empty"),
        ("rollback_procedure", "", "should be non-empty"),
    ],
)
def test_required_operational_metadata_cannot_be_empty(
    tmp_path: Path, field: str, replacement: Any, message: str
) -> None:
    def empty_field(contract: dict[str, Any]) -> None:
        contract["critical_paths"][0][field] = replacement

    errors = _mutate(tmp_path, empty_field)
    assert errors, message


def test_runbook_path_cannot_escape_repository(tmp_path: Path) -> None:
    def escape(contract: dict[str, Any]) -> None:
        contract["critical_paths"][0]["runbook"]["path"] = "docs/../../outside.md"

    errors = _mutate(tmp_path, escape)
    assert any("escapes the repository" in error for error in errors)


def test_runbook_file_and_anchor_must_exist(tmp_path: Path) -> None:
    def missing_anchor(contract: dict[str, Any]) -> None:
        contract["critical_paths"][0]["runbook"]["anchor"] = "not-a-real-section"

    errors = _mutate(tmp_path, missing_anchor)
    assert any("runbook anchor does not exist" in error for error in errors)


def test_missing_runbook_file_is_rejected(tmp_path: Path) -> None:
    def missing_file(contract: dict[str, Any]) -> None:
        contract["critical_paths"][0]["runbook"]["path"] = "docs/missing.md"

    errors = _mutate(tmp_path, missing_file)
    assert any("runbook does not exist" in error for error in errors)


@pytest.mark.parametrize("index", [1, 4])
def test_owner_prerequisites_cannot_be_reported_ready(tmp_path: Path, index: int) -> None:
    def false_ready(contract: dict[str, Any]) -> None:
        path = contract["critical_paths"][index]
        path["status"] = "READY"
        path["blocker"] = None
        path["closure_evidence"] = {"status": "PENDING_OWNER_ACTION", "refs": []}

    errors = _mutate(tmp_path, false_ready)
    assert any("readiness requires explicit verified closure evidence" in error for error in errors)


@pytest.mark.parametrize("index", [1, 4])
def test_owner_prerequisite_can_transition_with_explicit_closure_evidence(
    tmp_path: Path, index: int
) -> None:
    def close_control(contract: dict[str, Any]) -> None:
        path = contract["critical_paths"][index]
        path["status"] = "READY"
        path["blocker"] = None
        path["closure_evidence"] = {
            "status": "VERIFIED",
            "refs": [path["issue"]["url"]],
        }

    assert _mutate(tmp_path, close_control) == []


def test_only_declared_owner_prerequisites_may_use_blocked_status(tmp_path: Path) -> None:
    def false_blocker(contract: dict[str, Any]) -> None:
        path = contract["critical_paths"][0]
        path["status"] = "BLOCKED_OWNER_ACTION"
        path["blocker"] = "invented blocker"

    errors = _mutate(tmp_path, false_blocker)
    assert any("no declared owner-only prerequisite" in error for error in errors)


def test_blocked_path_requires_a_concrete_blocker(tmp_path: Path) -> None:
    def remove_blocker(contract: dict[str, Any]) -> None:
        contract["critical_paths"][1]["blocker"] = ""

    errors = _mutate(tmp_path, remove_blocker)
    assert errors


def test_unknown_contract_fields_are_rejected(tmp_path: Path) -> None:
    def add_unknown(contract: dict[str, Any]) -> None:
        contract["critical_paths"][0]["unsupported_override"] = True

    errors = _mutate(tmp_path, add_unknown)
    assert any("Additional properties are not allowed" in error for error in errors)
