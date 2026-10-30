"""Validate claim freshness only at an approved historical rollback boundary.

This helper is not a current repository certification. The rollback workflow uses it
only between adjacent exact-tree proofs and restores the baseline validator afterward.
The pure mode selector lets unlisted baselines use their original current-freshness
validation instead; it never grants another historical exception.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

APPROVED_BOUNDARIES = {
    "e8c37abb5e939d4433e42ea8a02af63549ca0010": date(2026, 10, 12),
    "aebd681097bb3c3322da50233e7fe2dc2e5a9144": date(2026, 10, 12),
    "4350c3716f6da11e0f57ddf85997c096b2e0c8fd": date(2026, 10, 12),
}


def review_mode(expected: str) -> str:
    """Select freshness semantics, never authorize or validate a rollback."""
    if re.fullmatch(r"[0-9a-f]{40}", expected) is None:
        raise ValueError("rollback baseline must be a full lowercase Git SHA")
    return "APPROVED_HISTORICAL" if expected in APPROVED_BOUNDARIES else "CURRENT_FRESHNESS"


def main(argv: Sequence[str] = ()) -> int:
    """Run the restored baseline's validator with explicitly historical semantics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-mode", metavar="BASELINE_SHA")
    args = parser.parse_args(argv)
    if args.review_mode is not None:
        print(review_mode(args.review_mode))
        return 0
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
    raise SystemExit(main(sys.argv[1:]))
