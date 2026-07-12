"""Run deterministic local performance budgets for operator-critical metadata paths."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _measure(fn, iterations: int) -> dict[str, float]:
    samples = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "median_ms": round(statistics.median(samples), 3),
        "max_ms": round(max(samples), 3),
    }


def run(root: Path = ROOT, iterations: int = 20) -> dict:
    from scripts.generate_skill_index import render
    from scripts.render_content_prompt import list_workflows
    from seoctl.registry import load_registry, validate_registry

    cases = {
        "command_registry": (
            _measure(lambda: validate_registry(load_registry()), iterations),
            250.0,
        ),
        "skill_index_render": (_measure(render, iterations), 250.0),
        "prompt_manifest": (_measure(list_workflows, iterations), 250.0),
    }
    results = {
        name: {
            **metrics,
            "budget_ms": budget,
            "passed": metrics["max_ms"] <= budget,
        }
        for name, (metrics, budget) in cases.items()
    }
    return {
        "status": "PASS" if all(row["passed"] for row in results.values()) else "FAIL",
        "iterations": iterations,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not 3 <= args.iterations <= 1000:
        raise SystemExit("iterations must be from 3 to 1000")
    payload = run(iterations=args.iterations)
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
