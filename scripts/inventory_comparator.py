"""Deterministic comparative inventory and score validation.

This module performs no network calls. External comparator facts are pinned in
``evaluation/comparative`` and must carry provenance. The local inventory is
computed from the checked-out repository so counts cannot drift silently.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPARATIVE = ROOT / "evaluation" / "comparative"

MATURITY_MAX_SCORE = {
    "ABSENT": 1.9,
    "DOCUMENTED": 3.9,
    "STUB": 5.9,
    "FUNCTIONAL": 7.9,
    "LIVE_CAPABLE": 8.9,
    "PRODUCTION_READY": 9.5,
    "BEST_IN_CLASS": 10.0,
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def weighted_score(scorecard: dict[str, Any]) -> float:
    return round(
        sum((float(row["score"]) / 10.0) * float(row["weight"]) for row in scorecard["categories"]),
        4,
    )


def validate_scorecard(scorecard: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    categories = scorecard.get("categories")
    if not isinstance(categories, list) or len(categories) != 10:
        return ["scorecard must contain exactly ten categories"]

    ids = [row.get("id") for row in categories if isinstance(row, dict)]
    if sorted(ids) != list(range(1, 11)):
        errors.append("category ids must be unique integers 1 through 10")

    weight = sum(float(row.get("weight", 0)) for row in categories)
    if abs(weight - 100.0) > 0.0001:
        errors.append(f"category weights must total 100; found {weight}")

    for row in categories:
        if not isinstance(row, dict):
            errors.append("every category must be an object")
            continue
        maturity = str(row.get("evidence_maturity", ""))
        score = float(row.get("score", -1))
        if maturity not in MATURITY_MAX_SCORE:
            errors.append(f"category {row.get('id')} has unknown evidence maturity {maturity!r}")
            continue
        maximum = MATURITY_MAX_SCORE[maturity]
        if score > maximum:
            errors.append(
                f"category {row.get('id')} score {score} exceeds maturity ceiling {maximum} for {maturity}"
            )
        evidence = row.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"category {row.get('id')} has no evidence")
        if score >= 8 and maturity not in {"LIVE_CAPABLE", "PRODUCTION_READY", "BEST_IN_CLASS"}:
            errors.append(f"category {row.get('id')} cannot score 8+ without live-capable evidence")

    calculated = weighted_score(scorecard)
    claimed = float(scorecard.get("overall_score", -1))
    if abs(calculated - claimed) > 0.0001:
        errors.append(f"overall_score is {claimed}, but the formula produces {calculated}")
    return errors


def _skill_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    text = path.read_text(encoding="utf-8-sig")
    return set(re.findall(r"^- `([a-z0-9-]+)`\s*$", text, flags=re.MULTILINE))


def _test_functions(path: Path) -> int:
    total = 0
    for file in path.rglob("test_*.py"):
        try:
            tree = ast.parse(file.read_text(encoding="utf-8-sig"), filename=str(file))
        except (OSError, SyntaxError, UnicodeError):
            continue
        total += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        )
    return total


def inventory_repo(root: Path = ROOT) -> dict[str, Any]:
    agent_files = [
        path
        for path in (root / "agents").glob("*.md")
        if path.name != "AGENT_INDEX.md"
    ]
    script_files = [path for path in (root / "scripts").glob("*.py") if path.name != "__init__.py"]
    adapter_files = [path for path in (root / "adapters").glob("*.py") if path.name != "__init__.py"]
    knowledge_files = [path for path in (root / "knowledge").iterdir() if path.is_file()]
    reference_files = list((root / "skills").glob("**/references/*"))
    prompt_files = list((root / "skills" / "flow-prompts").glob("*.md"))
    workflow_files = list((root / "workflows").glob("*.md"))
    return {
        "agent_files": len(agent_files),
        "indexed_skills": len(_skill_ids(root / "skills" / "SKILL_INDEX.md")),
        "python_scripts": len(script_files),
        "python_adapters": len(adapter_files),
        "knowledge_files": len(knowledge_files),
        "skill_reference_files": len([path for path in reference_files if path.is_file()]),
        "flow_prompt_files": len(prompt_files),
        "workflow_files": len(workflow_files),
        "test_functions": _test_functions(root / "tests"),
        "has_contributors": (root / "CONTRIBUTORS.md").exists(),
        "has_citation": (root / "CITATION.cff").exists(),
        "has_issue_templates": (root / ".github" / "ISSUE_TEMPLATE").exists(),
        "has_codeowners": (root / ".github" / "CODEOWNERS").exists(),
    }


def validate_parity_ledger(ledger: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    allowed = set(ledger.get("allowed_statuses", []))
    rows = ledger.get("capabilities")
    if not isinstance(rows, list) or not rows:
        return ["capability parity ledger must contain rows"]
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("every parity row must be an object")
            continue
        row_id = str(row.get("id", ""))
        if not row_id:
            errors.append("parity row missing id")
        elif row_id in seen:
            errors.append(f"duplicate parity id: {row_id}")
        seen.add(row_id)
        status = str(row.get("status", ""))
        if status not in allowed:
            errors.append(f"{row_id} has invalid status {status!r}")
        if status == "GAP_OPEN" and not row.get("target_pr"):
            errors.append(f"{row_id} is open without a target PR")
        if status != "GAP_OPEN" and not row.get("evidence"):
            errors.append(f"{row_id} claims closure without evidence")
        acceptance = row.get("acceptance")
        if not isinstance(acceptance, list) or not acceptance:
            errors.append(f"{row_id} has no acceptance criteria")
    return errors


def validate_all(root: Path = ROOT) -> dict[str, Any]:
    world = load_json(COMPARATIVE / "world-class-baseline.json")
    claude = load_json(COMPARATIVE / "claude-seo-baseline.json")
    parity = load_json(COMPARATIVE / "capability-parity.json")
    errors = [
        *[f"world-class: {item}" for item in validate_scorecard(world)],
        *[f"claude-seo: {item}" for item in validate_scorecard(claude)],
        *[f"parity: {item}" for item in validate_parity_ledger(parity)],
    ]
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "inventory": inventory_repo(root),
        "scores": {
            "world_class": weighted_score(world),
            "claude_seo": weighted_score(claude),
            "gap": round(weighted_score(claude) - weighted_score(world), 4),
            "target": float(world.get("target_score", 92)),
        },
        "open_capabilities": sum(
            1 for row in parity["capabilities"] if row.get("status") == "GAP_OPEN"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the comparative SEO-system rebaseline.")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_all(args.root.resolve())
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
