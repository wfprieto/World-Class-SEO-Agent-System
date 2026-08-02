"""Validate deterministic command-to-runtime contract reconciliation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seoctl.command_contracts import validate_command_contracts  # noqa: E402


def main() -> int:
    errors = validate_command_contracts(ROOT)
    print(
        json.dumps(
            {"status": "PASS" if not errors else "FAIL", "errors": errors},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
