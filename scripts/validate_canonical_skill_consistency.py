"""Validate generated skill metadata, package anchors, and reference freshness."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_skill_index import render as render_index
from scripts.validate_reference_freshness import validate as validate_references

INDEX = ROOT / "skills" / "SKILL_INDEX.md"
CATALOG = ROOT / "skills" / "skill-catalog.json"
PACKAGES = ROOT / "skills" / "package-registry.json"
PROCEDURES = ROOT / "skills" / "deep-skill-procedures.md"
ALLOWED_EXECUTION_CLASSES = {"executable", "advisory", "hybrid"}

PROHIBITED = {
    "geo-grid-rank-scan": [r"haversine\s+offset", r"default\s+7x7"],
    "gbp-profile-audit": [r"25\s+ranking-relevant\s+fields", r"present-and-optimized\s+2"],
    "cross-platform-nap-verify": [r"name\s+mismatch\s+critical"],
    "programmatic-seo-governance": [
        r"warn\s+at\s+30\s+near-duplicate", r"hard\s+stop\s+at\s+50",
        r"below\s+60%\s+unique", r"below\s+40%",
    ],
    "competitor-comparison-page-build": [
        r"min(?:imum)?\s*~?\s*1,?500\s+words",
        r"generate\s+product/softwareapplication/itemlist\s+schema",
    ],
}


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def indexed_skills() -> set[str]:
    catalog = _load(CATALOG)
    return {
        str(skill)
        for category in catalog.get("categories", [])
        for skill in category.get("skills", [])
    }


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
    if INDEX.read_text(encoding="utf-8") != render_index():
        failures.append("SKILL_INDEX.md is not synchronized with metadata")

    catalog = _load(CATALOG)
    ordered = [
        str(skill)
        for category in catalog.get("categories", [])
        for skill in category.get("skills", [])
    ]
    if len(ordered) != len(set(ordered)):
        failures.append("skill catalog contains duplicate ids")
    indexed = set(ordered)
    sections, headings = procedure_sections()
    for skill in sorted(indexed - set(sections)):
        failures.append(f"indexed skill has no deep-procedure heading: {skill}")
    for skill in sorted(set(sections) - indexed):
        failures.append(f"deep-procedure heading is not indexed: {skill}")
    for skill in sorted(set(headings)):
        if headings.count(skill) != 1:
            failures.append(f"deep-procedure heading is duplicated: {skill}")
    for skill, patterns in PROHIBITED.items():
        section = sections.get(skill, "")
        for pattern in patterns:
            if re.search(pattern, section, re.IGNORECASE):
                failures.append(f"{skill} restores prohibited duplicate rule: {pattern}")

    package_payload = _load(PACKAGES)
    packages = package_payload.get("packages", {})
    document_path = str(package_payload.get("package_document", ""))
    document = ROOT / document_path
    text = document.read_text(encoding="utf-8") if document.is_file() else ""
    if not document.is_file():
        failures.append("priority package document is missing")
    defaults = package_payload.get("defaults", {})
    if not defaults.get("quality_gate") or not defaults.get("failure_states"):
        failures.append("package registry defaults are incomplete")
    for skill, row in sorted(packages.items()):
        if skill not in indexed:
            failures.append(f"package is not indexed: {skill}")
            continue
        if row.get("execution_class") not in ALLOWED_EXECUTION_CLASSES:
            failures.append(f"package {skill} has invalid execution_class")
        anchor = str(row.get("anchor", ""))
        if anchor != skill or f'id="{anchor}"' not in text:
            failures.append(f"package {skill} anchor is missing or mismatched")
        if not row.get("references"):
            failures.append(f"package {skill} requires references")
        for reference in row.get("references", []):
            base = str(reference).split("#", 1)[0]
            if not (ROOT / base).exists():
                failures.append(f"package {skill} reference missing: {reference}")

    failures.extend(f"reference: {item}" for item in validate_references())
    return failures


def main() -> int:
    failures = validate()
    if failures:
        print("Canonical skill consistency failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(
        f"Canonical skill consistency passed: {len(indexed_skills())} indexed skills, "
        f"{len(_load(PACKAGES).get('packages', {}))} priority packages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
