"""Validate authenticated Phase 8 issue evidence against the operations registry."""

from __future__ import annotations

from typing import Any


def _indexed_rows(rows: list[object]) -> tuple[dict[int, dict[str, Any]], list[str]]:
    errors: list[str] = []
    actual: dict[int, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            errors.append("Phase 8 issue inventory must contain unique issue objects")
            continue
        number = item.get("number")
        valid = isinstance(number, int) and not isinstance(number, bool) and number > 0
        if not valid or number in actual:
            errors.append("Phase 8 issue inventory must contain unique issue objects")
            continue
        assert isinstance(number, int)
        actual[number] = item
    return actual, sorted(set(errors))


def _row_errors(
    number: int, observed: dict[str, Any], control: dict[str, Any], owner_login: str
) -> list[str]:
    errors: list[str] = []
    expected_issue = control.get("issue", {})
    comparisons = (
        ("control_id", control.get("id"), "control identity"),
        ("url", expected_issue.get("url"), "URL"),
        ("state", expected_issue.get("expected_state"), "state"),
    )
    for field, expected, label in comparisons:
        if observed.get(field) != expected:
            errors.append(f"issue {number} {label} does not match the registry")
    assignees = observed.get("assignees")
    if not isinstance(assignees, list) or owner_login not in assignees:
        errors.append(f"issue {number} is not assigned to the repository owner")
    elif assignees != sorted(set(assignees)):
        errors.append(f"issue {number} assignees must be sorted and unique")
    title = observed.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append(f"issue {number} requires a title")
    if observed.get("locked") is not False:
        errors.append(f"issue {number} must remain unlocked for working intake")
    return errors


def issue_errors(
    snapshot: dict[str, Any], contract: dict[str, Any], operations: dict[str, Any]
) -> list[str]:
    rows = snapshot.get("phase8_issues")
    if not isinstance(rows, list):
        return ["Phase 8 provider snapshot requires issue inventory"]
    expected = {
        int(item["issue"]["number"]): item for item in operations.get("critical_paths", [])
    }
    actual, errors = _indexed_rows(rows)
    if set(actual) != set(expected):
        errors.append("Phase 8 issue inventory does not match the operations registry")
    owner_login = str(contract.get("repository", "")).partition("/")[0]
    for number in sorted(set(actual) & set(expected)):
        errors.extend(_row_errors(number, actual[number], expected[number], owner_login))
    return errors
