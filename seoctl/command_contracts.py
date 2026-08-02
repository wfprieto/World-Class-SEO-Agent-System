"""Deterministic runtime contracts for every effective ``seoctl`` command."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator

from runtime.assets import resolve_asset_root
from seoctl.registry import CommandSpec, command_specs

ROOT = resolve_asset_root(Path(__file__).resolve().parents[1])
INPUT_SCHEMA = "schemas/seoctl-command-input.schema.json"
OUTPUT_SCHEMA = "schemas/seoctl-command-output.schema.json"
CONTRACT_TEST = "tests/test_command_contracts.py"

EvidenceMode = Literal["DETERMINISTIC", "LIVE_CAPABLE"]

NETWORK_EVIDENCE_MODES: dict[str, EvidenceMode] = {
    "none": "DETERMINISTIC",
    "provider_optional": "LIVE_CAPABLE",
    "live_optional": "LIVE_CAPABLE",
    "live_required": "LIVE_CAPABLE",
}


@dataclass(frozen=True)
class FailureState:
    status: str
    state: str
    exit_code: int


FAILURE_CONTRACT: tuple[FailureState, ...] = (
    FailureState("input_error", "INPUT_ERROR", 2),
    FailureState("unavailable", "UNAVAILABLE", 3),
    FailureState("blocked", "BLOCKED", 4),
    FailureState("failed", "FAILED", 5),
)


@dataclass(frozen=True)
class CommandContract:
    command_id: str
    handler: str
    input_schema: str
    output_schema: str
    tests: tuple[str, ...]
    evidence_mode: EvidenceMode
    failures: tuple[FailureState, ...]


def contract_for(spec: CommandSpec) -> CommandContract:
    """Derive the one canonical contract for a registered command."""
    return CommandContract(
        command_id=spec.id,
        handler=spec.handler,
        input_schema=INPUT_SCHEMA,
        output_schema=OUTPUT_SCHEMA,
        tests=(CONTRACT_TEST,),
        evidence_mode=NETWORK_EVIDENCE_MODES[spec.network],
        failures=FAILURE_CONTRACT,
    )


def command_contracts(registry: dict[str, Any] | None = None) -> list[CommandContract]:
    return [contract_for(spec) for spec in command_specs(registry)]


def runtime_handler_definitions() -> dict[str, list[Callable[..., object]]]:
    """Inspect family maps before entrypoint composition can hide collisions."""
    from seoctl import (
        audit_cli,
        authority_cli,
        cli,
        content_cli,
        extensions_cli,
        google_cli,
        intelligence_cli,
        technical_cli,
    )

    definitions: dict[str, list[Callable[..., object]]] = {}
    for module in (
        cli,
        content_cli,
        google_cli,
        technical_cli,
        authority_cli,
        extensions_cli,
        audit_cli,
        intelligence_cli,
    ):
        for name, handler in module.HANDLERS.items():
            definitions.setdefault(name, []).append(handler)
    return definitions


def _schema_errors(root: Path, relative: str) -> list[str]:
    path = root / relative
    if not path.is_file():
        return [f"missing command schema: {relative}"]
    try:
        schema = json.loads(path.read_text(encoding="utf-8-sig"))
        Draft202012Validator.check_schema(schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"invalid command schema {relative}: {exc}"]
    return []


def _inventory_errors(
    specs: list[CommandSpec], contracts: list[CommandContract]
) -> tuple[list[str], dict[str, list[CommandContract]]]:
    errors: list[str] = []
    spec_ids = {spec.id for spec in specs}
    contracts_by_id: dict[str, list[CommandContract]] = {}
    for contract in contracts:
        contracts_by_id.setdefault(contract.command_id, []).append(contract)
    for command_id in sorted(spec_ids - set(contracts_by_id)):
        errors.append(f"missing command contract: {command_id}")
    for command_id in sorted(set(contracts_by_id) - spec_ids):
        errors.append(f"stale command contract: {command_id}")
    for command_id, rows in sorted(contracts_by_id.items()):
        if len(rows) != 1:
            errors.append(f"duplicate command contract: {command_id}")
    return errors, contracts_by_id


def _command_errors(
    spec: CommandSpec,
    contract: CommandContract,
    handlers: Mapping[str, Callable[..., object]],
    definitions: Mapping[str, list[Callable[..., object]]],
) -> list[str]:
    errors: list[str] = []
    if contract.handler != spec.handler:
        errors.append(
            f"{spec.id} contract handler {contract.handler!r} disagrees with registry {spec.handler!r}"
        )
    if not callable(handlers.get(spec.handler)):
        errors.append(f"{spec.id} has no callable runtime handler {spec.handler!r}")
    sources = definitions.get(spec.handler, [])
    if len(sources) != 1:
        errors.append(
            f"{spec.id} handler {spec.handler!r} must have exactly one runtime definition; found {len(sources)}"
        )
    expected_mode = NETWORK_EVIDENCE_MODES.get(spec.network)
    if contract.evidence_mode != expected_mode:
        errors.append(
            f"{spec.id} evidence mode {contract.evidence_mode!r} disagrees with network class {spec.network!r}"
        )
    if contract.failures != FAILURE_CONTRACT:
        errors.append(f"{spec.id} has a contradictory typed failure contract")
    return errors


def validate_command_contracts(
    root: Path = ROOT,
    *,
    registry: dict[str, Any] | None = None,
    contracts: Iterable[CommandContract] | None = None,
    handlers: Mapping[str, Callable[..., object]] | None = None,
    handler_definitions: Mapping[str, list[Callable[..., object]]] | None = None,
) -> list[str]:
    """Reconcile registry, runtime, schemas, evidence modes, failures, and tests."""
    from seoctl.entrypoint import HANDLERS

    root = root.resolve()
    specs = command_specs(registry)
    active_contracts = list(contracts if contracts is not None else command_contracts(registry))
    active_handlers = handlers if handlers is not None else HANDLERS
    definitions = (
        handler_definitions if handler_definitions is not None else runtime_handler_definitions()
    )
    errors, contracts_by_id = _inventory_errors(specs, active_contracts)

    schema_refs: set[str] = set()
    test_refs: set[str] = set()
    for spec in specs:
        rows = contracts_by_id.get(spec.id, [])
        if len(rows) != 1:
            continue
        contract = rows[0]
        errors.extend(_command_errors(spec, contract, active_handlers, definitions))
        schema_refs.update((contract.input_schema, contract.output_schema))
        test_refs.update(contract.tests)

    for relative in sorted(schema_refs):
        errors.extend(_schema_errors(root, relative))
    for relative in sorted(test_refs):
        if not (root / relative).is_file():
            errors.append(f"missing command contract test: {relative}")
    return errors
