"""Cohesive TranscriptService operations with bounded evidence states."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from contracts.adapter import AdapterResult
from integrations.authority_media.input_data import (
    _bounded_text,
    _state,
)


class TranscriptService:
    TIMESTAMP = re.compile(r"(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->")

    def check(self, input_path: str, *, video_id: str | None = None) -> AdapterResult:
        text = _bounded_text(input_path)
        caption_lines = _caption_lines(text)
        words = re.findall(r"\b[\w'-]+\b", " ".join(caption_lines), flags=re.UNICODE)
        repeated = [
            line for line, count in Counter(caption_lines).items() if count >= 3 and len(line) > 8
        ]
        issues: list[dict[str, Any]] = []
        if not self.TIMESTAMP.search(text):
            issues.append({"code": "NO_TIMESTAMPS", "severity": "warning"})
        if len(words) < 50:
            issues.append({"code": "VERY_SHORT_TRANSCRIPT", "severity": "warning"})
        if any(len(line) > 160 for line in caption_lines):
            issues.append({"code": "LONG_CAPTION_LINES", "severity": "info"})
        if repeated:
            issues.append(
                {"code": "REPEATED_SEGMENTS", "severity": "warning", "examples": repeated[:5]}
            )
        placeholders = [
            token for token in ("[music]", "[inaudible]", "[applause]") if token in text.lower()
        ]
        status = "ok" if caption_lines else "empty"
        return AdapterResult(
            source=input_path,
            status=status,
            data={
                "data_state": _state(status),
                "video_id": video_id,
                "word_count": len(words),
                "caption_line_count": len(caption_lines),
                "timestamp_evidence": bool(self.TIMESTAMP.search(text)),
                "placeholder_markers": placeholders,
                "issues": issues,
                "semantic_accuracy_verified": False,
            },
            warnings=[
                "Structural transcript checks do not verify spoken-word accuracy, speaker identity, or legal accessibility compliance."
            ],
        )


def _caption_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    caption_lines = [
        line
        for line in lines
        if not TranscriptService.TIMESTAMP.search(line)
        and not line.isdigit()
        and line.upper() not in {"WEBVTT", "NOTE"}
    ]

    return caption_lines
