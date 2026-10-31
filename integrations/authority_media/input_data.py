"""Bounded authority/media input and shared data-state normalization."""

from __future__ import annotations

import json
import urllib.parse
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 10_000_000
MAX_ROWS = 100_000
IPTC_BASE = "http://cv.iptc.org/newscodes/digitalsourcetype/"
IPTC_LABELS = {
    "captured": "Captured by a camera",
    "compositeCapture": "Composite of captured elements",
    "algorithmicallyEnhanced": "Algorithmically-altered media",
    "dataDrivenMedia": "Data-driven media",
    "digitalCreation": "Digital creation",
    "trainedAlgorithmicMedia": "Created using Generative AI",
    "compositeWithTrainedAlgorithmicMedia": "Edited using Generative AI",
    "algorithmicMedia": "Pure algorithmic media",
    "screenCapture": "Screen capture",
    "virtualRecording": "Virtual event recording",
    "composite": "Composite of elements",
    "compositeSynthetic": "Composite including generative AI elements",
    "humanEdits": "Human-edited media",
}
IPTC_RETIRED = {"softwareImage", "digitalArt"}


def _bounded_text(path: str | Path) -> str:
    target = Path(path)
    size = target.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise ValueError(f"input exceeds {MAX_INPUT_BYTES} bytes")
    return target.read_text(encoding="utf-8-sig")


def _read_json(path: str | Path) -> Any:
    return json.loads(_bounded_text(path))


def _host(value: str) -> str:
    text = value.strip()
    parsed = urllib.parse.urlsplit(text if "://" in text else f"https://{text}")
    if parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("domain must be a hostname or public URL without credentials")
    host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    if not host or "." not in host:
        raise ValueError("domain must contain a registrable hostname")
    return host


def _state(status: str) -> str:
    return {
        "ok": "AVAILABLE",
        "partial": "PARTIAL",
        "empty": "EMPTY",
        "not_configured": "NOT_CONFIGURED",
        "not_found": "NOT_FOUND",
        "invalid_response": "INVALID_RESPONSE",
        "blocked": "BLOCKED",
        "failed": "FAILED",
    }.get(status, status.upper())
