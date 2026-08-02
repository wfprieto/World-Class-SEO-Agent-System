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
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


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
    overdue_phase = active["overdue_phase"]
    edges = sorted(
        f"{item['source']}->{item['target']}"
        for item in contract.get("exceptions", [])
        if item.get("removal_phase") == overdue_phase
    )
    digest = hashlib.sha256(("\n".join(edges) + "\n").encode()).hexdigest()
    if active["schema_version"] != "1.0.0":
        errors.append("architecture exception disposition schema version must be 1.0.0")
    if active["disposition"] != "REPLAN" or active["target_phase"] != "P8":
        errors.append("overdue P5 architecture exceptions must be explicitly replanned to P8")
    if active["expected_exception_count"] != len(edges):
        errors.append("overdue architecture exception count does not match disposition")
    if active["expected_edges_sha256"] != digest:
        errors.append("overdue architecture exception edge set does not match disposition")
    if not isinstance(active["rationale"], str) or len(active["rationale"].strip()) < 80:
        errors.append("architecture exception disposition requires a concise governance rationale")
    return errors


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
