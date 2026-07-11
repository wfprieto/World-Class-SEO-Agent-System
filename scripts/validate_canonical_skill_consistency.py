"""Validate indexed skill headings and prevent stale duplicate rules from returning."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "skills" / "SKILL_INDEX.md"
PROCEDURES = ROOT / "skills" / "deep-skill-procedures.md"

PROHIBITED = {
    "geo-grid-rank-scan": [
        r"haversine\s+offset",
        r"default\s+7x7",
    ],
    "gbp-profile-audit": [
        r"25\s+ranking-relevant\s+fields",
        r"present-and-optimized\s+2",
    ],
    "cross-platform-nap-verify": [
        r"name\s+mismatch\s+critical",
    ],
    "programmatic-seo-governance": [
        r"warn\s+at\s+30\s+near-duplicate",
        r"hard\s+stop\s+at\s+50",
        r"below\s+60%\s+unique",
        r"below\s+40%",
    ],
    "competitor-comparison-page-build": [
        r"min(?:imum)?\s*~?\s*1,?500\s+words",
        r"generate\s+product/softwareapplication/itemlist\s+schema",
    ],
}


def indexed_skills() -> set[str]:
    text = INDEX.read_text(encoding="utf-8")
    return set(re.findall(r"`([a-z0-9-]+)`", text))


def procedure_sections() -> tuple[dict[str, str], list[str]]:
    text = PROCEDURES.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^## ([a-z0-9-]+)\s*$", text, re.MULTILINE))
    sections: dict[str, str] = {}
    headings: list[str] = []
    for position, match in enumerate(matches):
        skill = match.group(1)
        headings.append(skill)
        end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
        sections.setdefault(skill, text[match.start():end])
    return sections, headings


def validate() -> list[str]:
    failures: list[str] = []
    indexed = indexed_skills()
    sections, headings = procedure_sections()
    for skill in sorted(indexed - set(sections)):
        failures.append(f"indexed skill has no deep-procedure heading: {skill}")
    for skill in sorted(set(sections) - indexed):
        failures.append(f"deep-procedure heading is not indexed: {skill}")
    for skill in sorted(set(headings)):
        count = headings.count(skill)
        if count != 1:
            failures.append(f"deep-procedure heading appears {count} times: {skill}")
    for skill, patterns in PROHIBITED.items():
        section = sections.get(skill, "")
        for pattern in patterns:
            if re.search(pattern, section, re.IGNORECASE):
                failures.append(f"{skill} restores prohibited duplicate rule: {pattern}")
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Canonical skill consistency failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Canonical skill consistency passed: {len(indexed_skills())} indexed skills, one procedure heading each.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
