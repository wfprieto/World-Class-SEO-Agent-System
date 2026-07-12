"""Canonical command and agent-execution registry for seoctl."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.assets import resolve_asset_root

ROOT = resolve_asset_root(Path(__file__).resolve().parents[1])
REGISTRY_PATH = Path(__file__).with_name("command-registry.json")
OVERLAY_PATH = Path(__file__).with_name("command-registry-overlay.json")
ALLOWED_EXECUTION_CLASSES = {"executable", "advisory", "governance"}
ALLOWED_NETWORK = {"none", "provider_optional", "live_optional", "live_required"}


@dataclass(frozen=True)
class CommandSpec:
    id: str
    path: tuple[str, ...]
    handler: str
    owner: str
    skills: tuple[str, ...]
    execution_class: str
    network: str


def _merge_overlay(payload: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    active = copy.deepcopy(payload)
    active["version"] = str(overlay.get("version") or active.get("version") or "")
    active.setdefault("commands", []).extend(copy.deepcopy(overlay.get("commands", [])))
    agents = active.setdefault("agents", {})
    for agent, execution_class in overlay.get("agent_execution_classes", {}).items():
        if agent not in agents:
            raise ValueError(f"command overlay references unknown agent: {agent}")
        agents[agent]["execution_class"] = str(execution_class)
    for agent, command_ids in overlay.get("agent_commands", {}).items():
        if agent not in agents:
            raise ValueError(f"command overlay references unknown agent: {agent}")
        commands = agents[agent].setdefault("commands", [])
        for command_id in command_ids:
            if command_id not in commands:
                commands.append(command_id)
    return active


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("command registry must be an object")
    if path.resolve() == REGISTRY_PATH.resolve() and OVERLAY_PATH.exists():
        overlay = json.loads(OVERLAY_PATH.read_text(encoding="utf-8-sig"))
        if not isinstance(overlay, dict):
            raise ValueError("command registry overlay must be an object")
        payload = _merge_overlay(payload, overlay)
    return payload


def command_specs(registry: dict[str, Any] | None = None) -> list[CommandSpec]:
    active = registry or load_registry()
    return [
        CommandSpec(
            id=str(item["id"]),
            path=tuple(str(part) for part in item["path"]),
            handler=str(item["handler"]),
            owner=str(item["owner"]),
            skills=tuple(str(skill) for skill in item.get("skills", [])),
            execution_class=str(item["execution_class"]),
            network=str(item["network"]),
        )
        for item in active.get("commands", [])
    ]


def validate_registry(registry: dict[str, Any] | None = None) -> list[str]:
    from runtime.capability_resolver import CapabilityResolver
    from runtime.executor import AGENT_FILE_NAMES

    active = registry or load_registry()
    errors: list[str] = []
    specs = command_specs(active)
    ids = [item.id for item in specs]
    paths = [item.path for item in specs]
    if len(ids) != len(set(ids)):
        errors.append("command ids must be unique")
    if len(paths) != len(set(paths)):
        errors.append("command paths must be unique")

    canonical_agents = set(CapabilityResolver(ROOT).registry)
    runtime_agents = set(AGENT_FILE_NAMES)
    if canonical_agents != runtime_agents:
        errors.append(
            "capability and runtime agent registries disagree; "
            f"capability_only={sorted(canonical_agents - runtime_agents)}; "
            f"runtime_only={sorted(runtime_agents - canonical_agents)}"
        )

    for spec in specs:
        if len(spec.path) != 2:
            errors.append(f"{spec.id} must use exactly two path segments")
        if spec.owner not in canonical_agents:
            errors.append(f"{spec.id} has unknown canonical owner {spec.owner!r}")
        if spec.execution_class != "executable":
            errors.append(f"command {spec.id} must be executable")
        if spec.network not in ALLOWED_NETWORK:
            errors.append(f"{spec.id} has invalid network class {spec.network!r}")

    agents = active.get("agents")
    if not isinstance(agents, dict):
        return [*errors, "agent execution registry is missing"]
    if set(agents) != canonical_agents:
        missing = sorted(canonical_agents - set(agents))
        extra = sorted(set(agents) - canonical_agents)
        errors.append(f"agent registry mismatch; missing={missing}; extra={extra}")
    command_ids = set(ids)
    for agent, row in agents.items():
        if not isinstance(row, dict):
            errors.append(f"agent {agent} entry must be an object")
            continue
        execution_class = str(row.get("execution_class", ""))
        if execution_class not in ALLOWED_EXECUTION_CLASSES:
            errors.append(f"agent {agent} has invalid execution_class {execution_class!r}")
        commands = row.get("commands")
        if not isinstance(commands, list):
            errors.append(f"agent {agent} commands must be a list")
            continue
        unknown = sorted(set(str(item) for item in commands) - command_ids)
        if unknown:
            errors.append(f"agent {agent} references unknown commands {unknown}")
        if execution_class in {"executable", "governance"} and not commands:
            errors.append(f"agent {agent} is {execution_class} but has no command")
        if execution_class == "advisory" and commands:
            errors.append(f"agent {agent} is advisory but has executable commands")
    return errors


def spec_by_id(command_id: str) -> CommandSpec:
    for spec in command_specs():
        if spec.id == command_id:
            return spec
    raise KeyError(command_id)
