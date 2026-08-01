"""Deterministic comparative inventory and score validation.

This module performs no network calls. External comparator facts are pinned in
``evaluation/comparative`` and must carry provenance. The local inventory is
computed from the checked-out repository so counts cannot drift silently.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
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


def _git_head(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    head = result.stdout.strip().lower()
    return head if re.fullmatch(r"[0-9a-f]{40}", head) else None


def _is_ancestor(root: Path, commit: str, head: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, head],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_current_target_commits(
    world: dict[str, Any],
    parity: dict[str, Any],
    readiness: dict[str, Any],
    root: Path = ROOT,
) -> list[str]:
    """Reject unknown baselines while allowing reviewed descendant commits.

    A reviewed baseline commit may remain valid on descendants because this
    validator also pins the canonical inventories. This avoids making every
    documentation-only commit stale while still failing closed when the
    capability or command source of truth changes.
    """
    errors: list[str] = []
    head = _git_head(root)
    if head is None:
        return ["cannot resolve current Git HEAD; comparative freshness is unverified"]
    target_values = {
        "world-class": str(world.get("target_repository", "")).rsplit("@", 1)[-1],
        "parity": str(parity.get("target_commit", "")),
        "release-readiness": str(readiness.get("evaluated_target_commit", "")),
    }
    for label, commit in target_values.items():
        if not re.fullmatch(r"[0-9a-f]{40}", commit) or not _is_ancestor(root, commit, head):
            errors.append(f"{label} target commit is stale or is not an ancestor of current HEAD {head}")

    pins = parity.get("canonical_inventory_sha256", {})
    for relative in ("seoctl/command-registry.json", "orchestration/capability-registry.json"):
        path = root / relative
        expected = pins.get(relative) if isinstance(pins, dict) else None
        if not path.is_file() or expected != _sha256(path):
            errors.append(f"canonical inventory drifted since evaluation: {relative}")
    return errors


def validate_capability_inventory(ledger: dict[str, Any], root: Path = ROOT) -> list[str]:
    """Cross-check code-state claims against the canonical command registry."""
    registry_path = root / "seoctl" / "command-registry.json"
    if not registry_path.is_file():
        return ["canonical command inventory is missing: seoctl/command-registry.json"]
    registry = load_json(registry_path)
    command_ids = {str(row.get("id")) for row in registry.get("commands", []) if isinstance(row, dict)}
    errors: list[str] = []
    for row in ledger.get("capabilities", []):
        if not isinstance(row, dict):
            continue
        required = row.get("required_command_ids", [])
        if not isinstance(required, list) or not required:
            continue
        required_ids = {str(item) for item in required}
        present = required_ids.issubset(command_ids)
        code_state = row.get("code_state")
        row_id = row.get("id")
        if present and code_state == "ABSENT":
            errors.append(f"{row_id} contradicts the canonical command inventory: required commands exist")
        if not present and code_state == "CODE_VERIFIED":
            missing = sorted(required_ids - command_ids)
            errors.append(f"{row_id} contradicts the canonical command inventory: missing {missing}")
    return errors


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
    raw_ids = [row.get("id") for row in categories if isinstance(row, dict)]
    if not all(isinstance(item, int) for item in raw_ids) or sorted(
        item for item in raw_ids if isinstance(item, int)
    ) != list(range(1, 11)):
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
    return set(
        re.findall(
            r"^- `([a-z0-9-]+)`(?:\s+—\s+package:.*)?$",
            text,
            flags=re.MULTILINE,
        )
    )


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
    agent_files = [path for path in (root / "agents").glob("*.md") if path.name != "AGENT_INDEX.md"]
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
    comparative = root / "evaluation" / "comparative"
    world = load_json(comparative / "world-class-baseline.json")
    claude = load_json(comparative / "claude-seo-baseline.json")
    parity = load_json(comparative / "capability-parity.json")
    readiness = load_json(comparative / "final-release-readiness.json")
    errors = [
        *[f"world-class: {item}" for item in validate_scorecard(world)],
        *[f"claude-seo: {item}" for item in validate_scorecard(claude)],
        *[f"parity: {item}" for item in validate_parity_ledger(parity)],
        *[f"freshness: {item}" for item in validate_current_target_commits(world, parity, readiness, root)],
        *[f"inventory: {item}" for item in validate_capability_inventory(parity, root)],
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
        "open_capabilities": sum(1 for row in parity["capabilities"] if row.get("status") == "GAP_OPEN"),
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
