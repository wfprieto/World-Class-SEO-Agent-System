from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from jsonschema import Draft202012Validator

from runtime.finding_registry import FindingRegistry
from seoctl.command_contracts import (
    FAILURE_CONTRACT,
    command_contracts,
    runtime_handler_definitions,
    validate_command_contracts,
)
from seoctl.entrypoint import HANDLERS
from seoctl.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]


def test_every_effective_command_has_one_complete_runtime_contract() -> None:
    contracts = command_contracts()
    registry = load_registry()
    assert len(contracts) == len(registry["commands"])
    assert len({item.command_id for item in contracts}) == len(contracts)
    assert validate_command_contracts() == []
    for contract in contracts:
        assert callable(HANDLERS[contract.handler])
        assert contract.input_schema == "schemas/seoctl-command-input.schema.json"
        assert contract.output_schema == "schemas/seoctl-command-output.schema.json"
        assert contract.tests == ("tests/test_command_contracts.py",)
        assert contract.evidence_mode in {"DETERMINISTIC", "LIVE_CAPABLE"}
        assert contract.failures == FAILURE_CONTRACT


def test_command_contract_validator_is_machine_readable() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate_command_contracts.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"status": "PASS", "errors": []}


def test_contract_schemas_accept_normalized_invocation_and_typed_failure() -> None:
    input_schema = json.loads(
        (ROOT / "schemas/seoctl-command-input.schema.json").read_text(encoding="utf-8")
    )
    output_schema = json.loads(
        (ROOT / "schemas/seoctl-command-output.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(input_schema).validate(
        {"command": "content.serp", "arguments": {"results": "capture.json"}}
    )
    Draft202012Validator(output_schema).validate(
        {
            "command": "content.serp",
            "status": "blocked",
            "data": None,
            "warnings": [],
            "error": {
                "code": "INSUFFICIENT_EVIDENCE",
                "type": "EvidenceError",
                "state": "BLOCKED",
                "message": "Current evidence is required.",
            },
        }
    )


def test_contract_validator_rejects_missing_stale_duplicate_and_contradictory_rows() -> None:
    registry = load_registry()
    contracts = command_contracts(registry)
    first = contracts[0]
    stale = replace(first, command_id="stale.command")
    contradictory = replace(contracts[2], evidence_mode="LIVE_CAPABLE")
    failures = list(FAILURE_CONTRACT)
    failures[0] = replace(failures[0], exit_code=5)
    contradictory_failure = replace(contracts[3], failures=tuple(failures))

    errors = validate_command_contracts(
        registry=registry,
        contracts=[
            contracts[1],
            contracts[1],
            contradictory,
            contradictory_failure,
            *contracts[4:],
            stale,
        ],
    )
    assert f"missing command contract: {first.command_id}" in errors
    assert "stale command contract: stale.command" in errors
    assert f"duplicate command contract: {contracts[1].command_id}" in errors
    assert any("evidence mode" in error for error in errors)
    assert any("contradictory typed failure contract" in error for error in errors)


def test_contract_validator_rejects_missing_and_duplicate_runtime_handlers() -> None:
    registry = load_registry()
    contracts = command_contracts(registry)
    first = contracts[0]
    handlers = dict(HANDLERS)
    handlers.pop(first.handler)
    definitions = runtime_handler_definitions()
    definitions[first.handler] = [HANDLERS[first.handler], HANDLERS[first.handler]]
    errors = validate_command_contracts(
        registry=registry,
        contracts=contracts,
        handlers=handlers,
        handler_definitions=definitions,
    )
    assert f"{first.command_id} has no callable runtime handler {first.handler!r}" in errors
    assert any("must have exactly one runtime definition; found 2" in error for error in errors)


def _finding_output(
    *, evidence: list[dict[str, str]], refs: list[str], finding: str = "Canonical is invalid."
) -> dict[str, object]:
    return {
        "agent": "SEO Technical Agent",
        "evidence": evidence,
        "findings": [
            {
                "id": "finding-1",
                "severity": "High",
                "finding": finding,
                "affected_scope": "product template",
                "evidence_refs": refs,
            }
        ],
    }


def test_finding_registry_reports_valid_missing_stale_and_duplicate_evidence() -> None:
    valid = FindingRegistry()
    valid.add_output(
        _finding_output(
            evidence=[{"id": "crawl-1", "source": "crawl.json", "state": "CURRENT"}],
            refs=["crawl-1"],
        )
    )
    assert valid.records()[0]["evidence_state"] == "VALID"

    missing = FindingRegistry()
    missing.add_output(_finding_output(evidence=[], refs=["missing-1"]))
    missing.accept_all_without_conflict([])
    assert missing.records()[0]["evidence_state"] == "MISSING"
    assert missing.records()[0]["state"] == "EVIDENCE_REVIEW"
    assert missing.records()[0]["evidence_issues"] == ["unknown evidence reference: missing-1"]

    stale = FindingRegistry()
    stale.add_output(
        _finding_output(
            evidence=[{"id": "crawl-1", "source": "crawl.json", "state": "STALE"}],
            refs=["crawl-1"],
        )
    )
    stale.accept_all_without_conflict([])
    assert stale.records()[0]["evidence_state"] == "STALE"
    assert stale.records()[0]["state"] == "EVIDENCE_REVIEW"

    duplicate = FindingRegistry()
    duplicate.add_output(
        _finding_output(
            evidence=[{"id": "crawl-1", "source": "crawl.json", "state": "CURRENT"}],
            refs=["crawl-1", "crawl-1"],
        )
    )
    duplicate.accept_all_without_conflict([])
    assert duplicate.records()[0]["evidence_state"] == "DUPLICATE"
    assert duplicate.records()[0]["state"] == "EVIDENCE_REVIEW"


def test_finding_registry_marks_contradictory_specialist_evidence() -> None:
    registry = FindingRegistry()
    launch = _finding_output(
        evidence=[{"id": "crawl-1", "source": "crawl.json", "state": "CURRENT"}],
        refs=["crawl-1"],
        finding="Allow launch and index this template.",
    )
    block = copy.deepcopy(launch)
    block["agent"] = "SEO Compliance & Legal Agent"
    block["findings"][0]["id"] = "finding-2"  # type: ignore[index]
    block["findings"][0]["finding"] = "Block launch and noindex this template."  # type: ignore[index]
    registry.add_output(launch)
    registry.add_output(block)
    conflicts = registry.conflicts([launch, block])
    registry.accept_all_without_conflict(conflicts)
    assert conflicts
    records = registry.records()
    assert all(item["evidence_state"] == "CONTRADICTORY" for item in records)
    assert all(item["state"] == "CONFLICTED" for item in records)
