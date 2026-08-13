"""Rehearse Phase 0 rollback from the exact checked-out release candidate.

The verifier intentionally uses Git history instead of deleting files or checking
out a baseline tree. That proves every candidate commit can be backed out and
that the resulting tree exactly matches the approved Phase 0 baseline.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path


def _git(args: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        capture_output=True,
        check=check,
        text=True,
    )


def _git_text(args: Sequence[str]) -> str:
    return _git(args).stdout.strip()


def _parents(commit: str) -> list[str]:
    parent_text = _git_text(["show", "-s", "--format=%P", commit])
    return parent_text.split() if parent_text else []


def _revert_commit(commit: str) -> dict[str, object]:
    parents = _parents(commit)
    command = ["revert", "--no-commit"]
    mode = "single-parent"
    if len(parents) > 1:
        command.extend(["-m", "1"])
        mode = "merge-mainline-1"
    command.append(commit)
    result = _git(command, check=False)
    if result.returncode:
        raise RuntimeError(
            f"rollback revert failed for {commit} using {mode}: "
            f"{(result.stderr or result.stdout).strip()}"
        )
    return {
        "commit": commit,
        "parent_count": len(parents),
        "mode": mode,
    }


def verify_phase0_rollback(baseline: str, receipt_path: Path) -> dict[str, object]:
    candidate = _git_text(["rev-parse", "HEAD"])
    commits = _git_text(["rev-list", f"{baseline}..{candidate}"]).splitlines()
    if not commits:
        raise RuntimeError("Phase 0 rollback requires at least one candidate commit")

    _git(["config", "user.name", "Phase 0 rollback verifier"])
    _git(["config", "user.email", "rollback-verifier@users.noreply.github.com"])
    reverted = [_revert_commit(commit) for commit in commits]

    baseline_tree = _git_text(["rev-parse", f"{baseline}^{{tree}}"])
    post_revert_tree = _git_text(["write-tree"])
    if post_revert_tree != baseline_tree:
        raise RuntimeError(
            "Phase 0 rollback tree mismatch: "
            f"baseline={baseline_tree} post_revert={post_revert_tree}"
        )

    receipt = {
        "candidate_commit": candidate,
        "baseline_commit": baseline,
        "commit_count": len(commits),
        "baseline_tree": baseline_tree,
        "post_revert_tree": post_revert_tree,
        "reverted_commits": reverted,
        "result": "TREE_MATCH",
    }
    receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")

    _git(["reset", "--soft", baseline])
    restored_head = _git_text(["rev-parse", "HEAD"])
    if restored_head != baseline:
        raise RuntimeError(
            f"Phase 0 rollback soft reset failed: expected {baseline}, got {restored_head}"
        )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    verify_phase0_rollback(args.baseline, args.receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
