"""Cohesive IPTCLabelService operations with bounded evidence states."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from contracts.adapter import AdapterResult
from integrations.authority_media.input_data import (
    IPTC_BASE,
    IPTC_LABELS,
    IPTC_RETIRED,
    _read_json,
    _state,
)


class IPTCLabelService:
    @staticmethod
    def _extract(payload: Mapping[str, Any]) -> list[str]:
        candidates = []
        for key in ("digital_source_type", "DigitalSourceType", "digitalSourceType"):
            value = payload.get(key)
            if isinstance(value, str):
                candidates.append(value)
            elif isinstance(value, list):
                candidates.extend(str(item) for item in value)
        return candidates

    def inspect(
        self,
        input_path: str,
        *,
        label: str | None = None,
        write: bool = False,
        authorize_write: bool = False,
        output_path: str | None = None,
    ) -> AdapterResult:
        payload = _read_json(input_path)
        if not isinstance(payload, dict):
            return AdapterResult(
                input_path, "invalid_response", {"data_state": "INVALID_RESPONSE"}, []
            )
        observed = self._extract(payload)
        normalized, invalid, retired = _observed_labels(observed)
        requested_uri = _requested_label(label, invalid, retired)
        if write and not authorize_write:
            return AdapterResult(
                input_path,
                "blocked",
                {"data_state": "BLOCKED", "reason": "explicit_write_authorization_required"},
                [],
            )
        if write and not output_path:
            raise ValueError("--output is required when --write is used")
        written = None
        if write:
            if invalid or retired or not requested_uri:
                return AdapterResult(
                    input_path,
                    "invalid_response",
                    {"data_state": "INVALID_RESPONSE", "invalid": invalid, "retired": retired},
                    [],
                )
            sidecar = dict(payload)
            sidecar["digital_source_type"] = requested_uri
            target = Path(str(output_path))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            written = str(target)
        status = "invalid_response" if invalid or retired else "ok"
        return AdapterResult(
            source=input_path,
            status=status,
            data={
                "data_state": _state(status),
                "observed": normalized,
                "requested": requested_uri,
                "invalid": invalid,
                "retired": retired,
                "written_sidecar": written,
                "source_mutated": False,
                "rollback": f"Delete {written}" if written else None,
            },
            warnings=[
                "This command validates or writes a JSON sidecar only; it does not modify binary media metadata."
            ],
        )


def _observed_labels(observed: list[str]) -> tuple[list[str], list[str], list[str]]:
    normalized = []
    invalid = []
    retired = []
    for value in observed:
        token = value.rsplit("/", 1)[-1].split(":")[-1]
        if token in IPTC_RETIRED:
            retired.append(value)
        elif token in IPTC_LABELS:
            normalized.append(IPTC_BASE + token)
        else:
            invalid.append(value)

    return normalized, invalid, retired


def _requested_label(label: str | None, invalid: list[str], retired: list[str]) -> str | None:
    requested_uri = None
    if label:
        token = label.rsplit("/", 1)[-1].split(":")[-1]
        if token in IPTC_RETIRED:
            retired.append(label)
        elif token not in IPTC_LABELS:
            invalid.append(label)
        else:
            requested_uri = IPTC_BASE + token

    return requested_uri
