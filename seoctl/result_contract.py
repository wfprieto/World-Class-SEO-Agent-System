"""Executable result-envelope rules shared by every ``seoctl`` command."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

EXIT_OK = 0
EXIT_INPUT = 2
EXIT_UNAVAILABLE = 3
EXIT_BLOCKED = 4
EXIT_FAILED = 5


@dataclass(frozen=True)
class FailureState:
    status: str
    state: str
    exit_code: int
    error_codes: tuple[str, ...]


FAILURE_CONTRACT: tuple[FailureState, ...] = (
    FailureState("input_error", "INPUT_ERROR", EXIT_INPUT, ("INPUT_ERROR", "INVALID_ARGUMENTS")),
    FailureState("not_configured", "NOT_CONFIGURED", EXIT_UNAVAILABLE, ("NOT_CONFIGURED",)),
    FailureState("unavailable", "UNAVAILABLE", EXIT_UNAVAILABLE, ("UNAVAILABLE",)),
    FailureState("not_found", "NOT_FOUND", EXIT_UNAVAILABLE, ("NOT_FOUND",)),
    FailureState("rate_limited", "RATE_LIMITED", EXIT_UNAVAILABLE, ("RATE_LIMITED",)),
    FailureState("blocked", "BLOCKED", EXIT_BLOCKED, ("BLOCKED",)),
    FailureState("unauthorized", "UNAUTHORIZED", EXIT_BLOCKED, ("UNAUTHORIZED",)),
    FailureState("failed", "FAILED", EXIT_FAILED, ("FAILED",)),
    FailureState("invalid", "INVALID", EXIT_FAILED, ("INVALID",)),
    FailureState("invalid_response", "INVALID_RESPONSE", EXIT_FAILED, ("INVALID_RESPONSE",)),
)

FAILURE_BY_STATUS = {item.status: item for item in FAILURE_CONTRACT}
SUCCESS_STATUSES = frozenset({"ok", "complete", "success", "needs-review", "partial", "empty"})


class HandlerContractError(RuntimeError):
    """A registered handler returned a value outside its executable contract."""


def exit_code_for_status(status: str) -> int:
    """Return the one process exit code assigned to a contracted status."""
    if status in SUCCESS_STATUSES:
        return EXIT_OK
    failure = FAILURE_BY_STATUS.get(status)
    if failure is None:
        raise HandlerContractError(f"uncontracted command status {status!r}")
    return failure.exit_code


def normalize_error(status: str, error: Mapping[str, str] | None) -> dict[str, str] | None:
    """Complete failure metadata without erasing a more specific parser code."""
    failure = FAILURE_BY_STATUS.get(status)
    if failure is None:
        return dict(error) if error is not None else None
    normalized = dict(error or {})
    normalized.setdefault("code", failure.error_codes[0])
    normalized.setdefault("type", "CommandFailure")
    normalized["state"] = failure.state
    normalized.setdefault("message", f"Command ended in {status} state.")
    return normalized


def validate_handler_result(
    command_id: str,
    result: object,
    *,
    schema_path: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Validate the actual payload and its process exit code as one contract."""
    if not isinstance(result, tuple) or len(result) != 2:
        raise HandlerContractError(f"{command_id} handler must return (JSON envelope, exit code)")
    payload, exit_code = result
    if (
        not isinstance(payload, dict)
        or not isinstance(exit_code, int)
        or isinstance(exit_code, bool)
    ):
        raise HandlerContractError(
            f"{command_id} handler returned an invalid envelope or exit code"
        )
    if payload.get("command") != command_id:
        raise HandlerContractError(
            f"{command_id} handler emitted command {payload.get('command')!r}"
        )

    schema = (
        schema_path
        or Path(__file__).resolve().parents[1] / "schemas" / "seoctl-command-output.schema.json"
    )
    errors = sorted(
        Draft202012Validator(json.loads(schema.read_text(encoding="utf-8-sig"))).iter_errors(
            payload
        ),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        raise HandlerContractError(f"{command_id} envelope schema violation: {errors[0].message}")

    status = str(payload["status"])
    if status in SUCCESS_STATUSES:
        if exit_code != EXIT_OK:
            raise HandlerContractError(f"{command_id} status {status!r} requires exit code 0")
        return payload, exit_code
    failure = FAILURE_BY_STATUS.get(status)
    if failure is None:
        raise HandlerContractError(f"{command_id} emitted uncontracted status {status!r}")
    error = payload["error"]
    if exit_code != failure.exit_code:
        raise HandlerContractError(
            f"{command_id} status {status!r} requires exit code {failure.exit_code}"
        )
    if error["state"] != failure.state or error["code"] not in failure.error_codes:
        raise HandlerContractError(f"{command_id} emitted contradictory failure metadata")
    return payload, exit_code


def execute_handler(
    command_id: str,
    handler: Callable[[Any], object],
    arguments: Any,
) -> tuple[dict[str, Any], int]:
    """Execute a handler through the same typed boundary used by contract evidence."""
    try:
        result = handler(arguments)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        result = (
            {
                "command": command_id,
                "status": "input_error",
                "data": None,
                "warnings": [],
                "error": normalize_error(
                    "input_error",
                    {"type": type(exc).__name__, "message": str(exc)},
                ),
            },
            EXIT_INPUT,
        )
    except Exception as exc:  # noqa: BLE001
        result = (
            {
                "command": command_id,
                "status": "failed",
                "data": None,
                "warnings": [],
                "error": normalize_error(
                    "failed",
                    {"type": type(exc).__name__, "message": str(exc)[:500]},
                ),
            },
            EXIT_FAILED,
        )
    return validate_handler_result(command_id, result)
