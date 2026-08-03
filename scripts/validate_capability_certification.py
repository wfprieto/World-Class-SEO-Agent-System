"""Validate offline capability-certification profiles and committed receipts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seoctl.capability_certification import certification_state  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    state = certification_state(args.root, as_of=args.as_of)
    payload = {
        "status": "ok" if not state["errors"] else "failed",
        "verified_capabilities": sorted(state["current"]),
        "candidate_capabilities": sorted(state["candidates"]),
        "receipt_count": state["receipt_count"],
        "failures": state["errors"],
        "scope": "STATIC_OFFLINE_ONLY",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
