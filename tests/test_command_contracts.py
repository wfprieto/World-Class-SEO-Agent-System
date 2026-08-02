from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from runtime.finding_registry import FindingRegistry
from seoctl.command_contracts import (
    FAILURE_CONTRACT,
    command_contracts,
    runtime_handler_definitions,
    validate_command_contracts,
)
from seoctl.entrypoint import HANDLERS
from seoctl.registry import command_specs, load_registry
from seoctl.result_contract import HandlerContractError, execute_handler, validate_handler_result

ROOT = Path(__file__).resolve().parents[1]


class _ControlledInvalidArguments:
    """Prevent provider calls while proving that each real handler is executable."""

    def __getattr__(self, name: str) -> object:
        raise ValueError(f"controlled missing argument: {name}")


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
                "code": "BLOCKED",
                "type": "EvidenceError",
                "state": "BLOCKED",
                "message": "Current evidence is required.",
            },
        }
    )

    agent_schema = json.loads(
        (ROOT / "schemas/agent-output.schema.json").read_text(encoding="utf-8")
    )
    action_schema = agent_schema["properties"]["findings"]["items"]["properties"]["action_polarity"]
    Draft202012Validator(action_schema).validate(
        {"target": "product-page crawling", "polarity": "DISABLE"}
    )


@pytest.mark.parametrize("spec", command_specs(), ids=lambda spec: spec.id)
def test_every_effective_handler_has_executable_bounded_behavior_evidence(spec) -> None:
    """Invoke all 67 real handlers without credentials or live-provider traffic."""
    payload, exit_code = execute_handler(
        spec.id,
        HANDLERS[spec.handler],
        _ControlledInvalidArguments(),
    )

    assert payload["command"] == spec.id
    assert exit_code in {0, 2, 3, 4, 5}
    if exit_code:
        failure = next(
            item
            for item in FAILURE_CONTRACT
            if item.status == payload["status"] and item.exit_code == exit_code
        )
        assert payload["error"]["state"] == failure.state
        assert payload["error"]["code"] in failure.error_codes


def test_invalid_arguments_are_a_complete_typed_failure_contract(capsys) -> None:
    from seoctl.entrypoint import main

    assert main(["content", "quality", "--definitely-invalid-option"]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == {
        "code": "INVALID_ARGUMENTS",
        "message": "Invalid command arguments.",
        "state": "INPUT_ERROR",
        "type": "ArgumentError",
    }
    validate_handler_result("content.quality", (payload, 2))


def test_callable_returning_non_envelope_fails_executable_contract(monkeypatch) -> None:
    spec = command_specs()[0]
    monkeypatch.setitem(HANDLERS, spec.handler, lambda _args: "NOT_A_JSON_ENVELOPE")
    with pytest.raises(HandlerContractError, match="must return"):
        execute_handler(
            spec.id,
            HANDLERS[spec.handler],
            _ControlledInvalidArguments(),
        )


@pytest.mark.parametrize(
    ("status", "state", "exit_code"),
    [
        ("not_configured", "NOT_CONFIGURED", 3),
        ("not_found", "NOT_FOUND", 3),
        ("rate_limited", "RATE_LIMITED", 3),
        ("blocked", "BLOCKED", 4),
        ("unauthorized", "UNAUTHORIZED", 4),
        ("invalid", "INVALID", 5),
        ("invalid_response", "INVALID_RESPONSE", 5),
    ],
)
def test_current_runtime_failure_taxonomy_has_exact_state_and_exit_mapping(
    status: str,
    state: str,
    exit_code: int,
) -> None:
    from seoctl.cli import envelope

    payload = envelope("technical.robots", status)
    assert payload["error"]["state"] == state
    validate_handler_result("technical.robots", (payload, exit_code))


def test_output_schema_rejects_missing_or_contradictory_failure_metadata() -> None:
    schema = json.loads(
        (ROOT / "schemas/seoctl-command-output.schema.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    base = {
        "command": "technical.robots",
        "status": "blocked",
        "data": None,
        "warnings": [],
        "error": {
            "code": "BLOCKED",
            "type": "CommandFailure",
            "state": "BLOCKED",
            "message": "Blocked by policy.",
        },
    }
    assert not list(validator.iter_errors(base))

    missing_state = copy.deepcopy(base)
    del missing_state["error"]["state"]
    assert list(validator.iter_errors(missing_state))

    contradictory = copy.deepcopy(base)
    contradictory["error"]["code"] = "FAILED"
    contradictory["error"]["state"] = "FAILED"
    assert list(validator.iter_errors(contradictory))

    success_with_error = copy.deepcopy(base)
    success_with_error["status"] = "ok"
    assert list(validator.iter_errors(success_with_error))


@pytest.mark.parametrize(
    ("module_name", "wrapper_name", "status", "expected_exit"),
    [
        ("seoctl.technical_cli", "_result", "invalid", 5),
        ("seoctl.extensions_cli", "_result", "unauthorized", 4),
        ("seoctl.extensions_cli", "_result", "rate_limited", 3),
        ("seoctl.content_cli", "_result", "blocked", 4),
        ("seoctl.authority_cli", "_result", "not_configured", 3),
        ("seoctl.audit_cli", "_result", "invalid_response", 5),
        ("seoctl.intelligence_cli", "_wrap", "failed", 5),
    ],
)
def test_family_result_wrappers_use_the_canonical_failure_exit_mapping(
    module_name: str,
    wrapper_name: str,
    status: str,
    expected_exit: int,
) -> None:
    import importlib

    wrapper = getattr(importlib.import_module(module_name), wrapper_name)
    payload, exit_code = wrapper(
        "technical.robots",
        SimpleNamespace(status=status, data=None, warnings=[]),
    )
    assert exit_code == expected_exit
    validate_handler_result("technical.robots", (payload, exit_code))


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


def test_finding_registry_treats_one_items_identical_id_and_source_as_aliases() -> None:
    registry = FindingRegistry()
    registry.add_output(
        _finding_output(
            evidence=[{"id": "crawl.json", "source": "crawl.json", "state": "CURRENT"}],
            refs=["crawl.json"],
        )
    )
    registry.accept_all_without_conflict([])
    record = registry.records()[0]
    assert record["evidence_state"] == "VALID"
    assert record["state"] == "ACCEPTED"
    assert record["evidence_issues"] == []


def test_finding_registry_preserves_real_inventory_and_reference_duplicates() -> None:
    inventory_duplicate = FindingRegistry()
    inventory_duplicate.add_output(
        _finding_output(
            evidence=[
                {"id": "crawl-1", "source": "first.json", "state": "CURRENT"},
                {"id": "crawl-1", "source": "second.json", "state": "CURRENT"},
            ],
            refs=["crawl-1"],
        )
    )
    inventory_duplicate.accept_all_without_conflict([])
    assert inventory_duplicate.records()[0]["evidence_state"] == "DUPLICATE"

    repeated_reference = FindingRegistry()
    repeated_reference.add_output(
        _finding_output(
            evidence=[{"id": "crawl-1", "source": "crawl.json", "state": "CURRENT"}],
            refs=["crawl-1", "crawl-1"],
        )
    )
    repeated_reference.accept_all_without_conflict([])
    assert repeated_reference.records()[0]["evidence_state"] == "DUPLICATE"


def test_finding_registry_marks_contradictory_specialist_evidence() -> None:
    registry = FindingRegistry()
    launch = _finding_output(
        evidence=[{"id": "crawl-1", "source": "crawl.json", "state": "CURRENT"}],
        refs=["crawl-1"],
        finding="Allow launch and index this template.",
    )
    launch["findings"][0]["action_polarity"] = {  # type: ignore[index]
        "target": "template indexation",
        "polarity": "ENABLE",
    }
    block = copy.deepcopy(launch)
    block["agent"] = "SEO Compliance & Legal Agent"
    block["findings"][0]["id"] = "finding-2"  # type: ignore[index]
    block["findings"][0]["finding"] = "Block launch and noindex this template."  # type: ignore[index]
    block["findings"][0]["action_polarity"]["polarity"] = "DISABLE"  # type: ignore[index]
    registry.add_output(launch)
    registry.add_output(block)
    conflicts = registry.conflicts([launch, block])
    registry.accept_all_without_conflict(conflicts)
    assert conflicts
    records = registry.records()
    assert all(item["evidence_state"] == "CONTRADICTORY" for item in records)
    assert all(item["state"] == "CONFLICTED" for item in records)


def test_finding_registry_structured_polarity_catches_crawling_action_variants() -> None:
    for positive, negative in (("Enable", "Disable"), ("Permit", "Prevent")):
        registry = FindingRegistry()
        allow = _finding_output(
            evidence=[{"id": "allow", "source": "allow.json", "state": "CURRENT"}],
            refs=["allow"],
            finding=f"{positive} crawling for product pages.",
        )
        allow["findings"][0]["action_polarity"] = {  # type: ignore[index]
            "target": "product-page crawling",
            "polarity": "ENABLE",
        }
        block = _finding_output(
            evidence=[{"id": "block", "source": "block.json", "state": "CURRENT"}],
            refs=["block"],
            finding=f"{negative} crawling for product pages.",
        )
        block["agent"] = "SEO Compliance & Legal Agent"
        block["findings"][0]["id"] = "finding-2"  # type: ignore[index]
        block["findings"][0]["action_polarity"] = {  # type: ignore[index]
            "target": "product page crawling",
            "polarity": "DISABLE",
        }

        registry.add_output(allow)
        registry.add_output(block)
        conflicts = registry.conflicts([allow, block])
        registry.accept_all_without_conflict(conflicts)
        assert len(conflicts) == 1
        assert all(record["state"] == "CONFLICTED" for record in registry.records())


def test_finding_registry_sends_unstructured_paraphrases_and_negation_to_review() -> None:
    registry = FindingRegistry()
    permit = _finding_output(
        evidence=[{"id": "permit", "source": "permit.json", "state": "CURRENT"}],
        refs=["permit"],
        finding="Permit search bots to fetch product pages.",
    )
    prevent = _finding_output(
        evidence=[{"id": "prevent", "source": "prevent.json", "state": "CURRENT"}],
        refs=["prevent"],
        finding="Do not allow crawler access to product pages.",
    )
    prevent["agent"] = "SEO Compliance & Legal Agent"
    prevent["findings"][0]["id"] = "finding-2"  # type: ignore[index]

    registry.add_output(permit)
    registry.add_output(prevent)
    conflicts = registry.conflicts([permit, prevent])
    registry.accept_all_without_conflict(conflicts)
    assert conflicts == []
    assert all(record["state"] == "EVIDENCE_REVIEW" for record in registry.records())
    assert all(record["evidence_state"] == "VALID" for record in registry.records())
    assert all(record["review_issues"] for record in registry.records())


def test_finding_registry_sends_malformed_action_contracts_to_review() -> None:
    malformed_contracts = [
        {"target": "product page crawling", "polarity": "DENY"},
        {"target": "product page crawling", "polarity": "enable"},
        {"target": "product page crawling", "polarity": "DISABLE", "extra": True},
    ]
    for action_polarity in malformed_contracts:
        registry = FindingRegistry()
        output = _finding_output(
            evidence=[{"id": "crawl", "source": "crawl.json", "state": "CURRENT"}],
            refs=["crawl"],
            finding="Disable crawling for product pages.",
        )
        output["findings"][0]["action_polarity"] = action_polarity  # type: ignore[index]
        registry.add_output(output)
        registry.accept_all_without_conflict([])
        record = registry.records()[0]
        assert record["evidence_state"] == "VALID"
        assert record["state"] == "EVIDENCE_REVIEW"
        assert record["review_issues"]


def test_finding_registry_structured_polarity_negative_controls_do_not_conflict() -> None:
    registry = FindingRegistry()
    crawl = _finding_output(
        evidence=[{"id": "crawl", "source": "crawl.json", "state": "CURRENT"}],
        refs=["crawl"],
        finding="Enable crawling for product pages.",
    )
    crawl["findings"][0]["action_polarity"] = {  # type: ignore[index]
        "target": "product page crawling",
        "polarity": "ENABLE",
    }
    render = _finding_output(
        evidence=[{"id": "render", "source": "render.json", "state": "CURRENT"}],
        refs=["render"],
        finding="Disable rendering for preview pages.",
    )
    render["agent"] = "SEO JavaScript Agent"
    render["findings"][0]["id"] = "finding-2"  # type: ignore[index]
    render["findings"][0]["action_polarity"] = {  # type: ignore[index]
        "target": "preview page rendering",
        "polarity": "DISABLE",
    }

    registry.add_output(crawl)
    registry.add_output(render)
    conflicts = registry.conflicts([crawl, render])
    registry.accept_all_without_conflict(conflicts)
    assert conflicts == []
    assert all(record["state"] == "ACCEPTED" for record in registry.records())


def test_finding_registry_matching_polarities_for_same_target_do_not_conflict() -> None:
    registry = FindingRegistry()
    enable = _finding_output(
        evidence=[{"id": "first", "source": "first.json", "state": "CURRENT"}],
        refs=["first"],
        finding="Enable crawling for product pages.",
    )
    enable["findings"][0]["action_polarity"] = {  # type: ignore[index]
        "target": "product page crawling",
        "polarity": "ENABLE",
    }
    permit = _finding_output(
        evidence=[{"id": "second", "source": "second.json", "state": "CURRENT"}],
        refs=["second"],
        finding="Permit crawling for product pages.",
    )
    permit["agent"] = "SEO Rendering Agent"
    permit["findings"][0]["id"] = "finding-2"  # type: ignore[index]
    permit["findings"][0]["action_polarity"] = {  # type: ignore[index]
        "target": "product-page crawling",
        "polarity": "ENABLE",
    }
    registry.add_output(enable)
    registry.add_output(permit)
    conflicts = registry.conflicts([enable, permit])
    registry.accept_all_without_conflict(conflicts)
    assert conflicts == []
    assert all(record["state"] == "ACCEPTED" for record in registry.records())


def test_finding_registry_does_not_infer_conflict_between_one_specialists_observations() -> None:
    registry = FindingRegistry()
    output = _finding_output(
        evidence=[
            {"id": "canonical", "source": "canonical.json", "state": "CURRENT"},
            {"id": "schema", "source": "schema.json", "state": "CURRENT"},
        ],
        refs=["canonical"],
        finding="Canonical differs from the rendered URL.",
    )
    output["findings"].append(  # type: ignore[union-attr]
        {
            "id": "finding-2",
            "severity": "Medium",
            "finding": "Schema omits the product identifier.",
            "affected_scope": "product template",
            "evidence_refs": ["schema"],
        }
    )
    registry.add_output(output)
    conflicts = registry.conflicts([output])
    registry.accept_all_without_conflict(conflicts)
    assert conflicts == []
    assert all(record["state"] == "ACCEPTED" for record in registry.records())
