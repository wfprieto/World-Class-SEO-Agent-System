"""Compose content-production prompts from one manifest and two shared documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "prompts" / "prompt-manifest.json"
PLACEHOLDER = re.compile(r"\{\{([a-z0-9_]+)\}\}")


def _manifest() -> dict[str, Any]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("prompt manifest must be an object")
    return payload


def _section(path: Path, anchor: str) -> str:
    text = path.read_text(encoding="utf-8")
    marker = f'<a id="{anchor}"></a>'
    start = text.find(marker)
    if start < 0:
        raise ValueError(f"missing prompt anchor {anchor} in {path}")
    body_start = text.find("\n", start) + 1
    next_anchor = text.find('\n<a id="', body_start)
    return text[body_start: next_anchor if next_anchor >= 0 else len(text)].strip()


def compose(workflow_id: str, values: dict[str, Any]) -> dict[str, Any]:
    manifest = _manifest()
    workflows = manifest.get("workflows", {})
    if workflow_id not in workflows:
        raise ValueError(f"unknown prompt workflow: {workflow_id}")
    row = workflows[workflow_id]
    required = [str(item) for item in row.get("required_inputs", [])]
    missing = [key for key in required if key not in values or values[key] in (None, "")]
    if missing:
        raise ValueError("missing prompt inputs: " + ", ".join(missing))
    unknown = sorted(set(values) - set(required))
    if unknown:
        raise ValueError("unknown prompt inputs: " + ", ".join(unknown))

    template = _section(ROOT / row["path"], row["anchor"])
    placeholders = set(PLACEHOLDER.findall(template))
    if placeholders != set(required):
        raise ValueError(
            f"prompt manifest/template mismatch for {workflow_id}: "
            f"required={sorted(required)} placeholders={sorted(placeholders)}"
        )
    rendered = PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)
    component_text = []
    for component_id in row.get("components", []):
        component = manifest["components"][component_id]
        component_text.append(_section(ROOT / component["path"], component["anchor"]))
    output = "\n\n".join([*component_text, rendered.strip()]) + "\n"
    return {
        "workflow": workflow_id,
        "title": row["title"],
        "components": list(row.get("components", [])),
        "required_inputs": required,
        "prompt": output,
    }


def list_workflows() -> list[dict[str, Any]]:
    manifest = _manifest()
    return [
        {"id": workflow_id, "title": row["title"],
         "components": row["components"], "required_inputs": row["required_inputs"]}
        for workflow_id, row in sorted(manifest.get("workflows", {}).items())
    ]
