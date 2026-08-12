"""Rehearse rollback for the autonomous SEO expansion P0 candidate."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "evaluation" / "remediation" / "autonomous-seo-expansion-program.json"
P0_CLOSURE = ROOT / "evaluation" / "remediation" / "autonomous-seo-expansion-p0-closure.json"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout.strip()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def _rollback_candidate(program: dict[str, Any], finalization_head: str) -> str:
    p0 = next(phase for phase in program["phases"] if phase["id"] == "P0")
    if p0["status"] != "COMPLETE":
        return finalization_head
    if not P0_CLOSURE.is_file():
        raise RuntimeError("completed P0 requires its closure before rollback certification")
    closure = _load(P0_CLOSURE)
    candidate = str(closure["candidate_commit"])
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", candidate, finalization_head],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=20,
    )
    return candidate


def rehearse(receipt_path: Path) -> dict[str, Any]:
    if not (ROOT / ".git").exists():
        raise RuntimeError("autonomous SEO rollback certification requires Git history")
    program = _load(PROGRAM)
    baseline = str(program["baseline"]["commit"])
    finalization_head = _git("rev-parse", "HEAD")
    candidate = _rollback_candidate(program, finalization_head)
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, candidate],
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=20,
    )
    _git("reset", "--hard", candidate)
    commits = _git("rev-list", f"{baseline}..{candidate}").splitlines()
    if not commits:
        raise RuntimeError("autonomous SEO P0 rollback has no candidate commits to rehearse")
    _git("config", "user.name", "Autonomous SEO rollback verifier")
    _git("config", "user.email", "autonomous-seo-rollback@users.noreply.github.com")
    subprocess.run(
        ["git", "revert", "--no-commit", *commits],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    baseline_tree = _git("rev-parse", f"{baseline}^{{tree}}")
    post_revert_tree = _git("write-tree")
    if baseline_tree != post_revert_tree:
        raise RuntimeError("autonomous SEO rollback tree does not match declared program baseline")
    receipt = {
        "program_id": str(program["program_id"]),
        "phase_id": "P0",
        "finalization_head": finalization_head,
        "candidate_commit": candidate,
        "baseline_commit": baseline,
        "commit_count": len(commits),
        "baseline_tree": baseline_tree,
        "post_revert_tree": post_revert_tree,
        "result": "TREE_MATCH",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    _git("reset", "--soft", baseline)
    if _git("rev-parse", "HEAD") != baseline:
        raise RuntimeError("autonomous SEO rollback did not restore the declared baseline commit")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        receipt = rehearse(ROOT / args.receipt)
    except (KeyError, StopIteration, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}))
        return 1
    print(json.dumps({"status": "PASS", "receipt": receipt}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
