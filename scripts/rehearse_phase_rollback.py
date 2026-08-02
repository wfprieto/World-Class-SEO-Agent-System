#!/usr/bin/env python3
"""Rehearse the current phase's exact rollback boundary in a disposable CI checkout."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    program = _load(ROOT / "evaluation/remediation/owner-controlled-remediation-program.json")
    eligible = [
        phase
        for phase in program["phases"]
        if phase.get("rollback_baseline_commit") and phase.get("status") != "NOT_STARTED"
    ]
    if not eligible:
        raise RuntimeError("no active or most-recent phase has a rollback boundary")
    phase = eligible[-1]
    phase_id = str(phase["id"])
    artifact = _load(
        ROOT / "evaluation/remediation" / f"phase{phase_id[1:]}-rollback-evidence.json"
    )
    baseline = str(artifact["baseline_commit"])
    candidate = _git("rev-parse", "HEAD")
    commits = _git("rev-list", f"{baseline}..{candidate}").splitlines()
    if not commits:
        raise RuntimeError("rollback range is empty")
    merge_commits = _git("rev-list", "--min-parents=2", f"{baseline}..{candidate}").splitlines()
    if merge_commits:
        raise RuntimeError(f"rollback range contains unsupported merge commits: {merge_commits}")
    subprocess.run(
        ["git", "config", "user.name", "Phase rollback verifier"], cwd=ROOT, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", "rollback-verifier@users.noreply.github.com"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["git", "revert", "--no-commit", *commits], cwd=ROOT, check=True)
    baseline_tree = _git("rev-parse", f"{baseline}^{{tree}}")
    post_revert_tree = _git("write-tree")
    if baseline_tree != artifact["expected_baseline_tree"]:
        raise RuntimeError("durable rollback artifact has a stale baseline tree")
    if post_revert_tree != baseline_tree:
        raise RuntimeError("post-revert tree does not equal the phase baseline tree")
    receipt = {
        "phase_id": phase_id,
        "candidate_commit": candidate,
        "baseline_commit": baseline,
        "commit_count": len(commits),
        "baseline_tree": baseline_tree,
        "post_revert_tree": post_revert_tree,
        "result": "TREE_MATCH",
    }
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    # The tree and index already equal the baseline. Move only the disposable checkout's
    # symbolic HEAD so baseline validators that inspect history evaluate the restored boundary,
    # while the receipt retains the immutable candidate identity.
    subprocess.run(["git", "reset", "--soft", baseline], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
