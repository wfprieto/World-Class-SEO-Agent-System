"""Enforce per-file coverage floors for high-risk operational boundaries."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any


def validate(coverage_path: Path, config_path: Path) -> list[str]:
    coverage: dict[str, Any] = json.loads(coverage_path.read_text(encoding="utf-8"))
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    thresholds = config["tool"]["wcseo"]["risk_coverage"]
    measured = {
        name.replace("\\", "/"): details
        for name, details in coverage.get("files", {}).items()
    }
    errors: list[str] = []
    for filename, minimum in sorted(thresholds.items()):
        if not isinstance(minimum, (int, float)) or not 1 <= minimum <= 100:
            errors.append(f"{filename}: invalid threshold {minimum!r}")
            continue
        details = measured.get(filename)
        if details is None:
            errors.append(f"{filename}: missing from coverage report")
            continue
        actual = float(details["summary"]["percent_covered"])
        print(f"{filename}: {actual:.2f}% (required {float(minimum):.2f}%)")
        if actual + 1e-9 < float(minimum):
            errors.append(
                f"{filename}: {actual:.2f}% is below required {float(minimum):.2f}%"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("coverage", type=Path)
    parser.add_argument("--config", type=Path, default=Path("pyproject.toml"))
    args = parser.parse_args(argv)
    errors = validate(args.coverage, args.config)
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
