"""Sanitized evidence projection for rendered-page transport results."""
from __future__ import annotations

from typing import Any

from adapters.url_safety import (
    sanitize_headers_for_evidence,
    sanitize_text_for_evidence,
    sanitize_url_for_evidence,
)


def blank_evidence(
    url: str,
    raw_html: str,
    status: int | None,
    headers: dict,
    *,
    is_spa: bool,
) -> dict[str, Any]:
    return {
        "url": sanitize_url_for_evidence(url),
        "status_code": status,
        "is_spa": is_spa,
        "mode_used": "raw",
        "render_engine": None,
        "raw_content": raw_html,
        "content": raw_html,
        "headers": sanitize_headers_for_evidence(headers),
        "accessibility_tree": None,
        "console_errors": [],
        "render_ms": 0,
        "js_added_chars": None,
        "evidence": {"rendered": "Not Run", "accessibility": "Not Run"},
    }


def merge_rendered(
    data: dict[str, Any], rendered: dict[str, Any], raw_html: str
) -> None:
    content = rendered.get("content", raw_html)
    data.update(
        {
            "mode_used": "rendered",
            "render_engine": rendered.get("render_engine", "injected"),
            "content": content,
            "status_code": rendered.get("status_code") or data["status_code"],
            "accessibility_tree": rendered.get("accessibility_tree"),
            "console_errors": [
                sanitize_text_for_evidence(item)
                for item in rendered.get("console_errors", [])
            ],
            "render_ms": rendered.get("render_ms", 0),
            "js_added_chars": len(content) - len(raw_html or ""),
            "evidence": {"rendered": "Verified", "accessibility": "Verified"},
        }
    )
