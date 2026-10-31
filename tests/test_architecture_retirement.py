"""A terminal retirement proves zero debt instead of reauthorizing empty debt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.validate_architecture_exception_disposition import validate

ROOT = Path(__file__).resolve().parents[1]


def retired_case(tmp_path):
    governance = tmp_path / "governance"
    governance.mkdir()
    contract = {"exceptions": []}
    (governance / "architecture-contract.json").write_text(json.dumps(contract), encoding="utf-8")
    active = json.loads((ROOT / "governance/architecture-exception-disposition.json").read_text())
    active.update(
        disposition="RETIRED",
        expected_exception_count=0,
        expected_edges_sha256=hashlib.sha256(b"\n").hexdigest(),
        retirement_plans=[],
    )
    return active, governance / "architecture-contract.json"


def test_terminal_retirement_accepts_exact_empty_debt(tmp_path):
    active, _ = retired_case(tmp_path)
    assert validate(tmp_path, active) == []


@pytest.mark.parametrize("count", [False, True, "0", 1, -1])
def test_retirement_requires_strict_integer_zero(tmp_path, count):
    active, _ = retired_case(tmp_path)
    active["expected_exception_count"] = count
    assert validate(tmp_path, active)


def test_retirement_rejects_edges_in_any_phase(tmp_path):
    active, contract = retired_case(tmp_path)
    contract.write_text(
        json.dumps({"exceptions": [{"source": "a", "target": "b", "removal_phase": "P11"}]})
    )
    assert validate(tmp_path, active)


@pytest.mark.parametrize(
    "field,value",
    [("expected_edges_sha256", "0" * 64), ("retirement_plans", [{}]), ("retirement_plans", None)],
)
def test_retirement_rejects_bad_hash_or_plans(tmp_path, field, value):
    active, _ = retired_case(tmp_path)
    active[field] = value
    assert validate(tmp_path, active)
