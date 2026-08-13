"""Validate the source-inspired upgrade matrix used for governed SEO upgrades."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "evaluation" / "upgrade-source-matrix.json"
REQUIRED_SOURCE_FIELDS = {
    "id",
    "repo",
    "local_path",
    "head_observed",
    "primary_value",
    "license_review",
    "status",
}
REQUIRED_UNIT_FIELDS = {
    "id",
    "apivr_phase",
    "title",
    "priority",
    "impact",
    "effort",
    "source_ids",
    "target_files",
    "target_agents",
    "target_skills",
    "acceptance_criteria",
    "verification_commands",
    "status",
}


def _load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(path: Path = MATRIX_PATH) -> list[str]:
    matrix = _load_matrix(path)
    failures: list[str] = []

    if matrix.get("schema_version") != "1.0.0":
        failures.append("schema_version must be 1.0.0")
    if matrix.get("apivr_tier") != "Comprehensive":
        failures.append("apivr_tier must be Comprehensive")

    policy = matrix.get("source_policy", {})
    for key in ("allowed_use", "forbidden_use", "verification_standard"):
        values = policy.get(key)
        if not isinstance(values, list) or not values:
            failures.append(f"source_policy.{key} must be a non-empty list")

    sources = matrix.get("sources", [])
    if not isinstance(sources, list) or not sources:
        failures.append("sources must be a non-empty list")
        sources = []
    source_ids: set[str] = set()
    for source in sources:
        missing = REQUIRED_SOURCE_FIELDS - set(source)
        if missing:
            failures.append(f"source missing fields: {sorted(missing)}")
            continue
        source_id = str(source["id"])
        if source_id in source_ids:
            failures.append(f"duplicate source id: {source_id}")
        source_ids.add(source_id)
        if source["license_review"] != "required_before_copying_any_expression":
            failures.append(f"source {source_id} must require license review")

    units = matrix.get("upgrade_units", [])
    if not isinstance(units, list) or not units:
        failures.append("upgrade_units must be a non-empty list")
        units = []
    unit_ids: set[str] = set()
    phases: set[int] = set()
    for unit in units:
        missing = REQUIRED_UNIT_FIELDS - set(unit)
        if missing:
            failures.append(f"upgrade unit missing fields: {sorted(missing)}")
            continue
        unit_id = str(unit["id"])
        if unit_id in unit_ids:
            failures.append(f"duplicate upgrade unit id: {unit_id}")
        unit_ids.add(unit_id)
        phase = unit["apivr_phase"]
        if not isinstance(phase, int) or phase < 1:
            failures.append(f"upgrade unit {unit_id} has invalid apivr_phase")
        else:
            phases.add(phase)
        unknown_sources = set(unit["source_ids"]) - source_ids
        if unknown_sources:
            failures.append(
                f"upgrade unit {unit_id} references unknown sources: {sorted(unknown_sources)}"
            )
        for field in (
            "source_ids",
            "target_files",
            "target_agents",
            "target_skills",
            "acceptance_criteria",
            "verification_commands",
        ):
            values = unit.get(field)
            if not isinstance(values, list) or not values:
                failures.append(f"upgrade unit {unit_id}.{field} must be a non-empty list")
        if unit["status"] not in {"planned", "implemented", "verified", "blocked"}:
            failures.append(f"upgrade unit {unit_id} has invalid status")

    if phases and phases != set(range(1, max(phases) + 1)):
        failures.append(f"APIVR phases are not contiguous: {sorted(phases)}")

    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Upgrade source matrix validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Upgrade source matrix validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
