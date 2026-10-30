"""Exact code-remediation receipts for the comparative capability ledger."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

CODE_REMEDIATION_IDS = {
    "agents-executable-entrypoints",
    "skills-self-contained-packages",
    "content-verify",
    "nlp-entity-analysis",
    "paid-provider-packs",
    "reference-library",
    "content-prompt-pack",
    "image-generation-pack",
}


def _receipt(root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = (root / value).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _resolution_errors(row_id: str, row: dict[str, Any], root: Path) -> list[str]:
    resolution = row.get("resolution")
    if not isinstance(resolution, dict):
        return [f"{row_id} repository-controlled resolution is missing its code receipt"]
    errors: list[str] = []
    if (
        set(resolution) != {"kind", "resolved_at", "source_refs", "test_refs"}
        or resolution.get("kind") != "CODE_REMEDIATION"
    ):
        errors.append(f"{row_id} code receipt must use the exact bounded contract")
    try:
        date.fromisoformat(str(resolution.get("resolved_at", "")))
    except ValueError:
        errors.append(f"{row_id} code receipt requires an ISO resolved_at date")
    for field, prefix in (("source_refs", None), ("test_refs", "tests/")):
        label = "source receipt" if field == "source_refs" else "automated test receipt"
        refs = resolution.get(field)
        if not isinstance(refs, list) or not refs:
            errors.append(f"{row_id} code receipt requires {label}s")
            continue
        for ref in refs:
            if _receipt(root, ref) is None or (
                prefix and (not isinstance(ref, str) or not ref.startswith(prefix))
            ):
                errors.append(f"{row_id} {label} is missing or unsafe: {ref}")
    return errors


def code_remediation_errors(rows: list[dict[str, Any]], root: Path) -> list[str]:
    """Require receipts for the immutable repository-controlled gap set."""
    errors: list[str] = []
    indexed = {str(row.get("id", "")): row for row in rows}
    if not CODE_REMEDIATION_IDS.issubset(indexed):
        errors.append("canonical repository-controlled code-gap set is incomplete")
    for row_id in sorted(CODE_REMEDIATION_IDS & indexed.keys()):
        row = indexed[row_id]
        if row.get("status") == "GAP_OPEN":
            errors.append(f"{row_id} repository-controlled code gap remains open")
        else:
            errors.extend(_resolution_errors(row_id, row, root))
    return errors


def _open_reference_errors(
    row_id: str, row: dict[str, Any], field: str, root: Path
) -> list[str]:
    refs = row.get(field)
    if not isinstance(refs, list) or not refs or any(
        not isinstance(ref, str) or not ref.strip() for ref in refs
    ):
        return [f"{row_id} open gap requires non-empty {field}"]
    errors: list[str] = []
    for ref in refs:
        relative = Path(ref)
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            errors.append(f"{row_id} {field} escapes the repository: {ref}")
            continue
        if not candidate.exists():
            errors.append(f"{row_id} {field} is missing: {ref}")
        if field == "test_refs" and (
            relative.suffix != ".py" or not relative.as_posix().startswith("tests/test_")
        ):
            errors.append(f"{row_id} test_refs must name fixed automated tests: {ref}")
    return errors


def open_gap_contract_errors(
    row_id: str,
    row: dict[str, Any],
    status: str,
    root: Path,
    allowed_dispositions: set[str],
) -> list[str]:
    """Enforce the owned, testable, reversible contract for every open gap."""
    open_fields = {
        "gap_disposition", "next_action", "implementation_refs", "test_refs",
        "rollback_trigger",
    }
    if status != "GAP_OPEN":
        return (
            [f"{row_id} closed capability must not retain open-gap disposition"]
            if open_fields.intersection(row)
            else []
        )
    errors: list[str] = []
    if row.get("gap_disposition") not in allowed_dispositions:
        errors.append(f"{row_id} has invalid or missing gap disposition")
    for field in ("owner", "next_action", "rollback_trigger"):
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{row_id} open gap requires {field}")
    errors.extend(_open_reference_errors(row_id, row, "implementation_refs", root))
    errors.extend(_open_reference_errors(row_id, row, "test_refs", root))
    return errors
