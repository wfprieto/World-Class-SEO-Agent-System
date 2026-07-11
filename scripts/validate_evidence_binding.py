"""CLI wrapper for the canonical runtime material-claim evidence validator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime.evidence_binding import validate_evidence_binding


def validate_output(output: dict) -> list[str]:
    """Backward-compatible public name used by tests and tooling."""
    return validate_evidence_binding(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate material claim evidence binding.")
    parser.add_argument("agent_output")
    args = parser.parse_args()
    payload = json.loads(Path(args.agent_output).read_text(encoding="utf-8-sig"))
    errors = validate_evidence_binding(payload)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Evidence binding validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
