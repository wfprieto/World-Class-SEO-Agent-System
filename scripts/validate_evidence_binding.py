"""Deterministically validate material claims against an agent output's evidence inventory."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_URL = re.compile(r"https?://[^\s)\]>\"']+")
_NUMBER = re.compile(r"(?<![A-Za-z0-9])(?:\$?\d+(?:[.,]\d+)*(?:%|x)?)(?![A-Za-z0-9])")


def _texts(output: dict[str, Any]) -> list[str]:
    values = [
        str(output.get("summary", "")),
        str(output.get("impact", "")),
        str(output.get("follow_up", "")),
    ]
    values.extend(
        str(item.get("finding", ""))
        for item in output.get("findings", [])
        if isinstance(item, dict)
    )
    values.extend(
        " ".join(
            [
                str(item.get("action", "")),
                str(item.get("success_metric", "")),
            ]
        )
        for item in output.get("recommended_actions", [])
        if isinstance(item, dict)
    )
    return values


def validate_output(output: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    evidence_ids: set[str] = set()
    for item in output.get("evidence", []):
        if not isinstance(item, dict):
            continue
        if item.get("id"):
            evidence_ids.add(str(item["id"]))
        if item.get("source"):
            evidence_ids.add(str(item["source"]))

    claims = output.get("material_claims", [])
    if not isinstance(claims, list):
        return ["material_claims must be a list"]

    claim_text = "\n".join(
        str(claim.get("statement", ""))
        for claim in claims
        if isinstance(claim, dict)
    )
    execution_state = str(output.get("execution_state", ""))
    if execution_state in {"COMPLETE", "PARTIAL"}:
        observed_tokens: set[str] = set()
        for text in _texts(output):
            observed_tokens.update(_URL.findall(text))
            observed_tokens.update(_NUMBER.findall(text))
        for token in sorted(observed_tokens):
            if token not in claim_text:
                errors.append(f"material value or URL is not bound to a material_claim: {token}")

    seen_claim_ids: set[str] = set()
    for index, claim in enumerate(claims):
        prefix = f"material_claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix} must be an object")
            continue
        claim_id = str(claim.get("claim_id", ""))
        if not claim_id:
            errors.append(f"{prefix}.claim_id is required")
        elif claim_id in seen_claim_ids:
            errors.append(f"duplicate material claim id: {claim_id}")
        seen_claim_ids.add(claim_id)

        refs = claim.get("evidence_refs", [])
        if not refs:
            errors.append(f"{prefix} has no evidence_refs")
        for ref in refs:
            if str(ref) not in evidence_ids:
                errors.append(f"{prefix} references unknown evidence: {ref}")

        state = str(claim.get("evidence_state", ""))
        inference = bool(claim.get("inference", False))
        if not inference and state in {"MISSING", "INVALID", "BLOCKED"}:
            errors.append(
                f"{prefix} presents unavailable evidence state {state} as a factual claim"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate material claim evidence binding.")
    parser.add_argument("agent_output")
    args = parser.parse_args()
    payload = json.loads(Path(args.agent_output).read_text(encoding="utf-8-sig"))
    errors = validate_output(payload)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Evidence binding validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
