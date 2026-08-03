"""Generate truthful proof classifications from the effective repository registries."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.capability_resolver import CapabilityResolver
from seoctl.registry import command_specs

NETWORK_EXECUTION_MODES = {
    "none": "DETERMINISTIC",
    "provider_optional": "LIVE_CAPABLE",
    "live_optional": "LIVE_CAPABLE",
    "live_required": "LIVE_CAPABLE",
}
EVIDENCE_CLASSES = ("SOURCE", "AUTOMATED", "CI", "PROVIDER", "DEPLOYED", "OPERATIONAL")


def _json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _string_list(value: object, *, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must not contain duplicates")
    return value


def _effective_command_registry(root: Path) -> tuple[dict[str, Any], set[str]]:
    """Load base plus overlay relative to *root*, never relative to this module."""
    base_path = root / "seoctl" / "command-registry.json"
    overlay_path = root / "seoctl" / "command-registry-overlay.json"
    active = copy.deepcopy(_json_object(base_path))
    overlay_ids: set[str] = set()
    if not overlay_path.is_file():
        return active, overlay_ids

    overlay = _json_object(overlay_path)
    base_commands = active.get("commands")
    overlay_commands = overlay.get("commands", [])
    if not isinstance(base_commands, list) or not isinstance(overlay_commands, list):
        raise ValueError("command registry command inventories must be arrays")
    for index, row in enumerate(overlay_commands):
        command = _object(row, label=f"command overlay row {index}")
        command_id = command.get("id")
        if not isinstance(command_id, str) or not command_id:
            raise ValueError(f"command overlay row {index} has no non-empty id")
        overlay_ids.add(command_id)
    active["commands"] = [*copy.deepcopy(base_commands), *copy.deepcopy(overlay_commands)]
    active["version"] = str(overlay.get("version") or active.get("version") or "")

    agents = _object(active.get("agents"), label="command registry agents")
    execution_classes = _object(
        overlay.get("agent_execution_classes", {}),
        label="command overlay agent_execution_classes",
    )
    agent_commands = _object(
        overlay.get("agent_commands", {}), label="command overlay agent_commands"
    )
    for agent, execution_class in execution_classes.items():
        if agent not in agents:
            raise ValueError(f"command overlay references unknown agent: {agent}")
        _object(agents[agent], label=f"command agent {agent}")["execution_class"] = str(
            execution_class
        )
    for agent, command_ids in agent_commands.items():
        if agent not in agents:
            raise ValueError(f"command overlay references unknown agent: {agent}")
        additions = _string_list(command_ids, label=f"command overlay assignments for {agent}")
        row = _object(agents[agent], label=f"command agent {agent}")
        commands = _string_list(row.get("commands"), label=f"command assignments for {agent}")
        for command_id in additions:
            if command_id not in commands:
                commands.append(command_id)
        row["commands"] = commands

    ids = [spec.id for spec in command_specs(active)]
    if len(ids) != len(set(ids)):
        raise ValueError("effective command registry contains duplicate command ids")
    return active, overlay_ids


def _skill_ids(root: Path) -> list[str]:
    payload = _json_object(root / "skills" / "skill-catalog.json")
    categories = payload.get("categories")
    if not isinstance(categories, list):
        raise ValueError("skill catalog categories must be an array")
    skills: list[str] = []
    for index, category in enumerate(categories):
        row = _object(category, label=f"skill category {index}")
        skills.extend(_string_list(row.get("skills"), label=f"skill category {index} skills"))
    if len(skills) != len(set(skills)):
        raise ValueError("skill catalog contains duplicate skill ids")
    return sorted(skills)


def _package_owners(root: Path) -> dict[str, list[str]]:
    payload = _json_object(root / "skills" / "package-registry.json")
    packages = _object(payload.get("packages"), label="skill package registry packages")
    output: dict[str, list[str]] = {}
    for skill, value in packages.items():
        row = _object(value, label=f"skill package {skill}")
        output[str(skill)] = sorted(
            _string_list(row.get("owners"), label=f"skill package {skill} owners")
        )
    return output


def _evidence(source_refs: list[str], automated_refs: list[str]) -> dict[str, Any]:
    result = {
        evidence_class: {"status": "OUT_OF_SCOPE", "refs": []}
        for evidence_class in EVIDENCE_CLASSES
    }
    result["SOURCE"] = {"status": "PASS", "refs": sorted(set(source_refs))}
    result["AUTOMATED"] = {"status": "PASS", "refs": sorted(set(automated_refs))}
    result["CI"] = {"status": "NOT_RUN", "refs": []}
    return result


def build(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    registry, overlay_ids = _effective_command_registry(root)
    specs = command_specs(registry)
    agents = _object(registry.get("agents"), label="effective command registry agents")
    resolver = CapabilityResolver(root)
    agent_skills = {
        agent: set(resolver.bundle(agent).skills) for agent in sorted(resolver.registry)
    }
    if set(agents) != set(agent_skills):
        raise ValueError(
            "effective command and capability agent inventories disagree; "
            f"command_only={sorted(set(agents) - set(agent_skills))}; "
            f"capability_only={sorted(set(agent_skills) - set(agents))}"
        )

    participants: dict[str, list[str]] = {spec.id: [] for spec in specs}
    for agent in sorted(agents):
        row = _object(agents[agent], label=f"effective command agent {agent}")
        for command_id in _string_list(
            row.get("commands"), label=f"effective command assignments for {agent}"
        ):
            if command_id not in participants:
                raise ValueError(f"agent {agent} references unknown command {command_id}")
            participants[command_id].append(agent)

    skill_commands: dict[str, list[Any]] = {}
    for spec in specs:
        if spec.network not in NETWORK_EXECUTION_MODES:
            raise ValueError(f"command {spec.id} has unsupported network class {spec.network!r}")
        if spec.owner not in participants[spec.id]:
            raise ValueError(f"command {spec.id} owner is not an assigned participant")
        for skill in spec.skills:
            skill_commands.setdefault(skill, []).append(spec)

    catalog_skills = _skill_ids(root)
    unknown_command_skills = sorted(set(skill_commands) - set(catalog_skills))
    if unknown_command_skills:
        raise ValueError(f"commands reference skills absent from the catalog: {unknown_command_skills}")
    assigned_agents = {
        skill: sorted(agent for agent, skills in agent_skills.items() if skill in skills)
        for skill in catalog_skills
    }
    declared_owners = _package_owners(root)

    commands: dict[str, Any] = {}
    for spec in sorted(specs, key=lambda item: item.id):
        source_registry = (
            "seoctl/command-registry-overlay.json"
            if spec.id in overlay_ids
            else "seoctl/command-registry.json"
        )
        command_participants = sorted(participants[spec.id])
        participant_alignment = {
            agent: {
                "declares_all_command_skills": set(spec.skills) <= agent_skills[agent],
                "missing_skills": sorted(set(spec.skills) - agent_skills[agent]),
            }
            for agent in command_participants
        }
        automated_refs = ["tests/test_seoctl.py", "tests/test_seoctl_entrypoint.py"]
        if spec.id == "audit.technical":
            automated_refs.append("tests/test_product_proof_technical_audit.py")
        commands[spec.id] = {
            "delivery_state": "COMMAND_BACKED",
            "execution_mode": NETWORK_EXECUTION_MODES[spec.network],
            "network_class": spec.network,
            "owner": spec.owner,
            "skills": list(spec.skills),
            "participants": command_participants,
            "owner_skill_alignment": participant_alignment[spec.owner],
            "participant_skill_alignment": participant_alignment,
            "evidence": _evidence(
                [source_registry, "orchestration/capability-registry.json"],
                automated_refs,
            ),
            "claim_ceiling": (
                "FIXTURE_VERIFIED"
                if spec.id == "audit.technical"
                else "LIVE_CAPABLE_NOT_VERIFIED"
                if spec.network != "none"
                else "REGISTRY_VERIFIED"
            ),
        }

    skills: dict[str, Any] = {}
    for skill in catalog_skills:
        backing = sorted(skill_commands.get(skill, []), key=lambda item: item.id)
        if backing:
            delivery = "COMMAND_BACKED"
        elif assigned_agents[skill]:
            delivery = "RUNTIME_CONTEXT"
        else:
            delivery = "DOCUMENTED_ONLY"
        network_classes = {spec.network for spec in backing}
        if skill == "product-proof-technical-audit":
            mode, ceiling = "FIXTURE_CAPABLE", "FIXTURE_VERIFIED"
        elif network_classes - {"none"}:
            mode, ceiling = "LIVE_CAPABLE", "LIVE_CAPABLE_NOT_VERIFIED"
        elif backing:
            mode, ceiling = "DETERMINISTIC", "REGISTRY_VERIFIED"
        else:
            mode, ceiling = "ADVISORY", "DOCUMENTED_ONLY"
        source_refs = ["skills/skill-catalog.json", "skills/deep-skill-procedures.md"]
        if skill == "product-proof-technical-audit":
            source_refs.extend(
                [
                    "skills/product-proof-technical-audit.md",
                    "orchestration/product-proof-capability-overlay.json",
                ]
            )
        automated_refs = ["tests/test_phase4_skills_and_references.py"]
        if skill == "product-proof-technical-audit":
            automated_refs.append("tests/test_product_proof_technical_audit.py")
        skills[skill] = {
            "delivery_state": delivery,
            "execution_mode": mode,
            "assigned_agents": assigned_agents[skill],
            "declared_owners": declared_owners.get(skill, []),
            "backing_commands": [spec.id for spec in backing],
            "backing_command_owners": sorted({spec.owner for spec in backing}),
            "evidence": _evidence(source_refs, automated_refs),
            "claim_ceiling": ceiling,
        }

    return {
        "schema_version": "1.1.0",
        "generated_from": [
            "seoctl/command-registry.json",
            "seoctl/command-registry-overlay.json",
            "orchestration/capability-registry.json",
            "orchestration/product-proof-capability-overlay.json",
            "skills/skill-catalog.json",
            "skills/package-registry.json",
        ],
        "commands": commands,
        "skills": skills,
    }


def render(root: Path = ROOT) -> str:
    return json.dumps(build(root), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.out or root / "orchestration" / "capability-evidence-registry.json"
    generated = render(root)
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != generated:
            print(f"Capability evidence registry is stale: {output}")
            return 1
        print("Capability evidence registry is current.")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(generated, encoding="utf-8")
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
