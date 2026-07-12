"""Validate reference metadata, source coverage, anchors, and freshness windows."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "knowledge" / "reference-registry.json"
CATALOG = ROOT / "skills" / "skill-catalog.json"
WINDOWS = {"volatile": 45, "quarterly": 140, "annual": 400, "stable": 800}


def validate(*, as_of: date | None = None) -> list[str]:
    failures: list[str] = []
    today = as_of or date.today()
    payload = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
    known_skills = {
        str(skill)
        for category in catalog.get("categories", [])
        for skill in category.get("skills", [])
    }
    try:
        verified = date.fromisoformat(str(payload["verified_at"]))
    except (KeyError, ValueError):
        return ["reference registry has invalid verified_at"]
    if verified > today:
        failures.append("reference registry verified_at is in the future")

    packs = payload.get("packs", {})
    for pack_id, pack in packs.items():
        freshness_class = str(pack.get("freshness_class", ""))
        if freshness_class not in WINDOWS:
            failures.append(f"{pack_id} has invalid freshness_class")
            continue
        age = (today - verified).days
        if age > WINDOWS[freshness_class]:
            failures.append(f"{pack_id} is stale by freshness policy ({age} days)")
        path = ROOT / str(pack.get("path", ""))
        if not path.is_file():
            failures.append(f"{pack_id} path is missing")
        sources = pack.get("primary_sources", [])
        if not isinstance(sources, list) or not sources:
            failures.append(f"{pack_id} requires primary_sources")
        for source in sources:
            parsed = urlsplit(str(source))
            if parsed.scheme != "https" or not parsed.hostname:
                failures.append(f"{pack_id} has invalid primary source URL")

    entries = payload.get("entries", [])
    ids = [str(row.get("id", "")) for row in entries if isinstance(row, dict)]
    if len(ids) != len(set(ids)):
        failures.append("reference ids must be unique")
    for row in entries:
        if not isinstance(row, dict):
            failures.append("reference entry must be an object")
            continue
        ref_id = str(row.get("id", ""))
        pack_id = str(row.get("pack", ""))
        if pack_id not in packs:
            failures.append(f"{ref_id} references unknown pack {pack_id}")
            continue
        path = ROOT / str(packs[pack_id]["path"])
        anchor = str(row.get("anchor", ""))
        if path.is_file() and f'id="{anchor}"' not in path.read_text(encoding="utf-8"):
            failures.append(f"{ref_id} anchor is missing")
        unknown = sorted(set(map(str, row.get("affected_skills", []))) - known_skills)
        if unknown:
            failures.append(f"{ref_id} references unknown skills {unknown}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", type=date.fromisoformat)
    args = parser.parse_args()
    failures = validate(as_of=args.as_of)
    if failures:
        print("Reference validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    print(
        f"Reference validation passed: {len(payload['entries'])} entries "
        f"across {len(payload['packs'])} packs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
