"""Temporary CI diagnostic for exact Ruff I001 fixes on P0 validators."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "scripts/autonomous_seo_expansion_closure.py",
    "scripts/validate_autonomous_seo_expansion_program.py",
)


def main() -> int:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            *TARGETS,
            "--select",
            "I",
            "--diff",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    print("P0_RUFF_IMPORT_DIFF_BEGIN")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    print("P0_RUFF_IMPORT_DIFF_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
