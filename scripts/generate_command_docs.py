"""Generate the seoctl command reference from the canonical base registry plus overlays."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seoctl.registry import command_specs, load_registry, validate_registry

DEFAULT_OUT = ROOT / "docs" / "COMMANDS.md"


def render() -> str:
    registry = load_registry()
    errors = validate_registry(registry)
    if errors:
        raise ValueError("invalid command registry: " + "; ".join(errors))
    lines = [
        "# seoctl Command Reference",
        "",
        "This file is generated from `seoctl/command-registry.json` and approved overlays. Do not edit it manually.",
        "",
        "Run `python -m seoctl --help` for interactive argument details.",
        "",
        "| Command | Owner | Skills | Network |",
        "|---|---|---|---|",
    ]
    for spec in sorted(command_specs(registry), key=lambda item: item.path):
        lines.append(
            "| `seoctl " + " ".join(spec.path) + "` | " + spec.owner + " | "
            + ", ".join(f"`{skill}`" for skill in spec.skills) + " | `" + spec.network + "` |"
        )
    lines.extend([
        "", "## Stable exit codes", "", "| Code | Meaning |", "|---:|---|",
        "| 0 | Completed successfully or truthfully partial without a hard failure |",
        "| 2 | Invalid or missing operator input |",
        "| 3 | Optional capability or provider unavailable |",
        "| 4 | Blocked by evidence, authorization, privacy or governance gate |",
        "| 5 | Execution or validation failure |", "",
        "Every command writes one JSON envelope with `command`, `status`, `data`, `warnings`, and `error`.",
        "", "## Examples", "", "```bash",
        "python -m seoctl --registry-check",
        "python -m seoctl audit technical --url https://example.com --output audit-runs/example-com",
        "python -m seoctl knowledge validate",
        "python -m seoctl knowledge product-claims --status BLOCKED",
        "python -m seoctl intelligence ai-timeouts --log access.log --server-stack nginx",
        "python -m seoctl system route \"Run a full SEO audit\" --domain https://example.com --business-type saas",
        "python -m seoctl system run \"Build an SEO content brief\" --domain https://example.com --business-type saas",
        "python -m seoctl profile resolve --signal cart --signal checkout --signal visible_price",
        "python -m seoctl cluster serp --serps examples/serps.json",
        "python -m seoctl privacy consent --config consent-fixture.json",
        "python -m seoctl benchmark compare", "```", "",
        "Commands that require live providers remain optional and must preserve runtime budgets, credential redaction, and approval gates.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/COMMANDS.md from seoctl registries")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = render()
    if args.check:
        if not args.out.exists() or args.out.read_text(encoding="utf-8") != generated:
            print(f"Command documentation is stale: {args.out}")
            return 1
        print("Command documentation is current.")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(generated, encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
