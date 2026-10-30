"""Validate claim freshness only at an approved historical rollback boundary.

This helper is not a current repository certification. The rollback workflow uses it
only between adjacent exact-tree proofs and restores the baseline validator afterward.
"""

from __future__ import annotations

import json
import os
import runpy
from datetime import date
from pathlib import Path

APPROVED_BOUNDARIES = {
    "e8c37abb5e939d4433e42ea8a02af63549ca0010": date(2026, 10, 12),
    "aebd681097bb3c3322da50233e7fe2dc2e5a9144": date(2026, 10, 12),
    "4350c3716f6da11e0f57ddf85997c096b2e0c8fd": date(2026, 10, 12),
}


def main() -> int:
    """Run the restored baseline's validator with explicitly historical semantics."""
    expected = os.environ.get("WCSEO_ROLLBACK_EXPECTED_SHA", "")
    source = os.environ.get("WCSEO_BASELINE_CLAIM_VALIDATOR", "")
    boundary = APPROVED_BOUNDARIES.get(expected)
    if boundary is None or not source:
        raise ValueError("approved rollback SHA and restored baseline validator are required")
    validator = runpy.run_path(source)
    failures = validator["validate"](Path.cwd(), as_of=boundary)
    print(json.dumps({
        "status": "failed" if failures else "historical_rollback_only",
        "certification_scope": "HISTORICAL_ROLLBACK_ONLY",
        "current_certification": False,
        "baseline_commit": expected,
        "as_of": boundary.isoformat(),
        "failures": failures,
    }, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
