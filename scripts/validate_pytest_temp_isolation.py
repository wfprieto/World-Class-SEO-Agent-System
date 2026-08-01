"""Reject pytest temporary roots nested inside the repository Git boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def validate(candidate: Path, *, repository_root: Path = ROOT) -> list[str]:
    resolved_candidate = candidate.resolve()
    resolved_repository = repository_root.resolve()
    if resolved_candidate == resolved_repository or resolved_repository in resolved_candidate.parents:
        return [
            "pytest temporary root is nested inside the repository; Git-backed fixture helpers "
            "can resolve the parent index instead of the isolated fixture"
        ]
    probe = resolved_candidate
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        git_root_text = subprocess.check_output(
            ["git", "-C", str(probe), "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        ).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        git_root_text = ""
    if git_root_text:
        git_root = Path(git_root_text).resolve()
        if resolved_candidate == git_root or git_root in resolved_candidate.parents:
            return [
                "pytest temporary root is nested inside an enclosing Git worktree; "
                "fixture repositories would inherit the enclosing index"
            ]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=Path(tempfile.gettempdir()))
    args = parser.parse_args()
    errors = validate(args.candidate)
    print(
        json.dumps(
            {
                "status": "PASS" if not errors else "FAIL",
                "candidate": str(args.candidate.resolve()),
                "repository_root": str(ROOT),
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
