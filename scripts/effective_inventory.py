"""Build deterministic effective base-plus-overlay inventory documents."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

COMMAND_OVERLAY_SCHEMA_VERSION = "1.1.0"
CAPABILITY_OVERLAY_SCHEMA_VERSION = "1.1.0"
COMMAND_OVERLAY_KEYS = {
    "schema_version",
    "version",
    "commands",
    "agent_commands",
    "agent_execution_classes",
}
CAPABILITY_OVERLAY_KEYS = {
    "schema_version",
    "shared_knowledge_files",
    "agent_overrides",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _rows(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"{label} must be an array of objects")
    return value


def _strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{label} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    return value


def _merge_unique(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item not in merged:
                merged.append(item)
    return merged


def _validate_overlay_contract(
    overlay: dict[str, Any], label: str, allowed_keys: set[str], schema_version: str
) -> None:
    unknown_keys = sorted(set(overlay) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"{label} has unknown top-level fields: {unknown_keys}")
    actual_schema_version = overlay.get("schema_version")
    if actual_schema_version != schema_version:
        raise ValueError(
            f"{label} schema_version must be {schema_version!r}; found {actual_schema_version!r}"
        )


def effective_command_registry(root: Path) -> dict[str, Any]:
    active = copy.deepcopy(_load(root / "seoctl/command-registry.json"))
    overlay = _load(root / "seoctl/command-registry-overlay.json")
    _validate_overlay_contract(
        overlay,
        "command overlay",
        COMMAND_OVERLAY_KEYS,
        COMMAND_OVERLAY_SCHEMA_VERSION,
    )
    base_rows = _rows(active.get("commands"), "base command inventory")
    overlay_rows = _rows(overlay.get("commands"), "command overlay inventory")
    active["commands"] = [*base_rows, *copy.deepcopy(overlay_rows)]
    active["version"] = overlay.get("version") or active.get("version")
    agents = _object(active.get("agents"), "command registry agents")
    classes = _object(overlay.get("agent_execution_classes", {}), "command overlay classes")
    assignments = _object(overlay.get("agent_commands", {}), "command overlay assignments")
    for agent in set(classes) | set(assignments):
        if agent not in agents:
            raise ValueError(f"command overlay references unknown agent: {agent}")
        row = _object(agents[agent], f"command agent {agent}")
        if agent in classes:
            row["execution_class"] = classes[agent]
        if agent in assignments:
            current = _strings(row.get("commands"), f"command assignments for {agent}")
            additions = _strings(assignments[agent], f"command overlay assignments for {agent}")
            row["commands"] = _merge_unique(current, additions)
    ids = [str(row.get("id", "")) for row in active["commands"]]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("effective command inventory has missing or duplicate ids")
    return active


def effective_capability_registry(root: Path) -> dict[str, Any]:
    active = copy.deepcopy(_load(root / "orchestration/capability-registry.json"))
    overlay = _load(root / "orchestration/product-proof-capability-overlay.json")
    _validate_overlay_contract(
        overlay,
        "capability overlay",
        CAPABILITY_OVERLAY_KEYS,
        CAPABILITY_OVERLAY_SCHEMA_VERSION,
    )
    agents = _object(active.get("agents"), "capability registry agents")
    overrides = _object(overlay.get("agent_overrides"), "capability overlay overrides")
    shared = _strings(overlay.get("shared_knowledge_files"), "capability overlay shared knowledge")
    merge_fields = {"skills", "skill_files", "knowledge_files", "templates", "required_evidence"}
    unknown_agents = sorted(set(overrides) - set(agents))
    if unknown_agents:
        raise ValueError(f"capability overlay references unknown agents: {unknown_agents}")
    for agent, base_value in agents.items():
        row = _object(base_value, f"capability agent {agent}")
        override = _object(overrides.get(agent, {}), f"capability override {agent}")
        unknown_fields = sorted(set(override) - merge_fields)
        if unknown_fields:
            raise ValueError(f"capability override {agent} has unknown fields: {unknown_fields}")
        for field in merge_fields:
            base_items = _strings(row.get(field, []), f"capability agent {agent} {field}")
            additions = _strings(override.get(field, []), f"capability override {agent} {field}")
            if field == "knowledge_files":
                additions = _merge_unique(shared, additions)
            row[field] = _merge_unique(base_items, additions)
    return active


def effective_inventory_hashes(root: Path) -> dict[str, str]:
    payloads = {
        "effective_command_registry": effective_command_registry(root),
        "effective_capability_registry": effective_capability_registry(root),
    }
    return {
        label: hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        for label, value in payloads.items()
    }
