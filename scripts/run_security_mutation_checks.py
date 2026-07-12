"""Run targeted mutation probes for security-critical redaction invariants."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.telemetry import redact


def _redaction_invariant(redactor: Callable[[Any], Any]) -> bool:
    payload = redactor(
        {"api_key": "secret-value", "nested": {"authorization": "Bearer x"}}
    )
    return (
        payload["api_key"] == "[REDACTED]"
        and payload["nested"]["authorization"] == "[REDACTED]"
    )


def run() -> dict[str, object]:
    baseline_passed = _redaction_invariant(redact)
    mutant_survived = _redaction_invariant(lambda value: value)
    status = "PASS" if baseline_passed and not mutant_survived else "FAIL"
    return {
        "status": status,
        "mutants": 1,
        "killed": 1 if not mutant_survived else 0,
        "baseline_passed": baseline_passed,
    }


def main() -> int:
    result = run()
    print(result)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
