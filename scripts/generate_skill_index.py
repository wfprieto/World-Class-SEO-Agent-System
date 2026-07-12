"""Generate the canonical skill index from machine-readable catalog and package metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "skills" / "skill-catalog.json"
PACKAGES = ROOT / "skills" / "package-registry.json"
DEFAULT_OUT = ROOT / "skills" / "SKILL_INDEX.md"


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def render() -> str:
    catalog = _load(CATALOG)
    package_payload = _load(PACKAGES)
    packages = package_payload.get("packages", {})
    package_document = str(package_payload.get("package_document", ""))
    lines = [
        "# Skill Index",
        "",
        "This file is generated from `skills/skill-catalog.json` and "
        "`skills/package-registry.json`. Do not edit it manually.",
        "",
        "Skills are reusable capabilities. Priority packages add machine-readable "
        "execution metadata while `skills/deep-skill-procedures.md` remains the "
        "canonical procedure authority.",
        "",
    ]
    total = 0
    for category in catalog.get("categories", []):
        name = str(category["name"])
        skills = [str(item) for item in category.get("skills", [])]
        total += len(skills)
        lines.extend([f"## {name}", ""])
        for skill in skills:
            if skill in packages:
                lines.append(f"- `{skill}` — package: `{package_document}#{skill}`")
            else:
                lines.append(f"- `{skill}`")
        lines.append("")
    lines.extend([
        "## Package coverage", "",
        f"- Indexed skills: {total}",
        f"- Priority packages: {len(packages)}",
        f"- Package document: `{package_document}`",
        "- Package metadata: `skills/package-registry.json`",
        "- Canonical procedures: `skills/deep-skill-procedures.md`",
        "- Definition standard: `skills/skill-definition-standard.md`", "",
        "## Supporting definition files", "",
        "- `core-skills.md`", "- `content-ia-skills.md`", "- `specialist-skills.md`",
        "- `strategy-governance-skills.md`", "- `missing-skills.md`",
        "- `public-facing-writing-skills.md`", "- `ecommerce-seo-skills.md`",
        "- `programmatic-seo-governance.md`", "- `geo-grid-local-rank-skills.md`",
        "- `competitor-comparison-pages.md`",
        "- `rendered-visual-audit-and-page-entry.md`",
        "- `seo-flow-skill.md`", "- `seo-cluster-skill.md`",
        "- `local-execution-skills.md`", "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = render()
    if args.check:
        if not args.out.exists() or args.out.read_text(encoding="utf-8") != generated:
            print(f"Skill index is stale: {args.out}")
            return 1
        print("Skill index is current.")
        return 0
    args.out.write_text(generated, encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
