from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DISPOSITION_PATH = ROOT / "governance" / "architecture-exception-disposition.json"
EXPECTED_KEYS = {
    "schema_version",
    "source_contract",
    "overdue_phase",
    "disposition",
    "target_phase",
    "expected_exception_count",
    "expected_edges_sha256",
    "rationale",
    "retirement_plans",
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _retirement_plan_errors(plans: object, edges: list[str]) -> list[str]:
    if not isinstance(plans, list) or not plans:
        return ["architecture exception disposition requires retirement plans"]
    errors: list[str] = []
    planned_edges: list[str] = []
    plan_ids: list[str] = []
    exact_fields = {"id", "owner", "edges", "acceptance", "verification"}
    for plan in plans:
        if not isinstance(plan, dict) or set(plan) != exact_fields:
            errors.append("architecture retirement plans must use exact fields")
            continue
        plan_ids.append(str(plan["id"]))
        plan_edges = plan["edges"]
        if not isinstance(plan_edges, list) or not plan_edges:
            errors.append(f"architecture retirement plan {plan['id']} requires edges")
        else:
            planned_edges.extend(map(str, plan_edges))
        for field in ("owner", "acceptance", "verification"):
            if not isinstance(plan[field], str) or not plan[field].strip():
                errors.append(f"architecture retirement plan {plan['id']} requires {field}")
    if len(plan_ids) != len(set(plan_ids)):
        errors.append("architecture retirement plan ids must be unique")
    if len(planned_edges) != len(set(planned_edges)):
        errors.append("architecture retirement plans must not duplicate edges")
    if set(planned_edges) != set(edges):
        errors.append("architecture retirement plans must cover every exact reauthorized edge")
    return errors


def validate(root: Path = ROOT, disposition: dict[str, Any] | None = None) -> list[str]:
    active = disposition or _load(root / DISPOSITION_PATH.relative_to(ROOT))
    errors = []
    if set(active) != EXPECTED_KEYS:
        errors.append("architecture exception disposition must use exact keys")
        return errors
    source = active["source_contract"]
    if source != "governance/architecture-contract.json":
        return ["architecture exception disposition must bind the canonical contract"]
    contract = _load(root / source)
    target_phase = active["target_phase"]
    edges = sorted(
        f"{item['source']}->{item['target']}"
        for item in contract.get("exceptions", [])
        if item.get("removal_phase") == target_phase
    )
    digest = hashlib.sha256(("\n".join(edges) + "\n").encode()).hexdigest()
    if active["schema_version"] != "1.0.0":
        errors.append("architecture exception disposition schema version must be 1.0.0")
    if (
        active["disposition"] != "REAUTHORIZE"
        or active["overdue_phase"] != "P8"
        or target_phase != "P9"
    ):
        errors.append("remaining P8 architecture exceptions require explicit dated P9 reauthorization")
    if active["expected_exception_count"] != len(edges):
        errors.append("overdue architecture exception count does not match disposition")
    if active["expected_edges_sha256"] != digest:
        errors.append("overdue architecture exception edge set does not match disposition")
    if not isinstance(active["rationale"], str) or len(active["rationale"].strip()) < 80:
        errors.append("architecture exception disposition requires a concise governance rationale")
    errors.extend(_retirement_plan_errors(active.get("retirement_plans"), edges))
    return errors


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
