"""CLI wrapper for the canonical runtime material-claim evidence validator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.evidence_binding import (  # noqa: E402
    normalize_legacy_output,
    validate_evidence_binding,
)


def validate_output(output: dict) -> list[str]:
    """Backward-compatible public name used by tests and tooling."""
    return validate_evidence_binding(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate material claim evidence binding.")
    parser.add_argument("agent_output")
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Explicitly normalize an unversioned output as PARTIAL with UNVERIFIED evidence.",
    )
    args = parser.parse_args()
    payload = json.loads(Path(args.agent_output).read_text(encoding="utf-8-sig"))
    if args.legacy:
        try:
            payload = normalize_legacy_output(payload)
        except ValueError as exc:
            print(exc)
            return 1
    errors = validate_evidence_binding(payload)
    if errors:
        for error in errors:
            print(error)
        return 1
    if args.legacy:
        print("Legacy evidence binding passed with explicit PARTIAL/UNVERIFIED semantics.")
    else:
        print("Evidence binding validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
