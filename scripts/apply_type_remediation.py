"""Apply the residual evidence-backed static typing remediation batch.

This temporary helper is deterministic and idempotent. It fails when neither an
original pattern nor its expected replacement exists, so repository drift cannot
be hidden by a successful no-op.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def edit(path: str, replacements: list[tuple[str, str]]) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
        elif new not in text:
            raise RuntimeError(f"missing remediation pattern in {path}: {old[:100]!r}")
    target.write_text(text, encoding="utf-8")


def remove_stale_ignores(path: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    target.write_text(re.sub(r"\s+# type: ignore\[[^\]]+\]", "", text), encoding="utf-8")


def type_handler_map(path: str, count: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if "from collections.abc import Callable" not in text:
        text = text.replace(
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\nfrom collections.abc import Callable\n",
        )
    original = "        handlers = {"
    replacement = "        handlers: dict[str, Callable[..., AdapterResult]] = {"
    if original in text:
        text = text.replace(original, replacement, count)
    elif text.count(replacement) < count:
        raise RuntimeError(f"missing handler-map pattern in {path}")
    target.write_text(text, encoding="utf-8")


def main() -> int:
    for path in [
        "integrations/technical/browser.py",
        "integrations/technical/http.py",
        "integrations/google/client.py",
        "integrations/extensions/indexnow.py",
        "integrations/authority_media/transport.py",
        "integrations/technical/inspection.py",
        "seoctl/technical_cli.py",
        "seoctl/intelligence_cli.py",
        "seoctl/extensions_cli.py",
        "seoctl/authority_cli.py",
        "seoctl/audit_cli.py",
        "seoctl/content_cli.py",
    ]:
        remove_stale_ignores(path)

    edit("integrations/product_proof/rules.py", [
        (
            "self.policy=policy; self.findings=[]; self.decisions=[]; self.counts=Counter()",
            "self.policy=policy; self.findings=[]; self.decisions=[]; self.counts: Counter[str]=Counter()",
        )
    ])
    edit("adapters/evidence_store.py", [
        (
            "            return int(cursor.lastrowid)",
            "            if cursor.lastrowid is None:\n                raise RuntimeError(\"snapshot insert did not return a row id\")\n            return int(cursor.lastrowid)",
        )
    ])
    edit("adapters/page_drift.py", [
        ("    _sha256,\n", "    _sha256 as _payload_sha256,\n"),
        ("def _sha256(text: str | None) -> str | None:", "def _hash_optional(text: str | None) -> str | None:"),
        (
            '"html_hash": _sha256(fields.get("html")),',
            '"html_hash": _hash_optional(fields.get("html") if isinstance(fields.get("html"), str) else None),',
        ),
        (
            '"schema_hash": _sha256(fields.get("schema_json")),',
            '"schema_hash": _hash_optional(fields.get("schema_json") if isinstance(fields.get("schema_json"), str) else None),',
        ),
        (
            'row["payload_sha256"] != _sha256(row["payload_json"])',
            'row["payload_sha256"] != _payload_sha256(row["payload_json"])',
        ),
    ])
    edit("adapters/rendered_page.py", [
        (
            '    raw_html, status, headers = "", None, {}',
            '    raw_html: str = ""\n    status: int | None = None\n    headers: dict[str, str] = {}',
        )
    ])
    edit("integrations/product_proof/crawler.py", [
        (
            '            candidate = values.get("src") or values.get("poster")\n            if candidate:\n                self.assets.append(candidate)',
            '            media_candidate: str | None = values.get("src") or values.get("poster")\n            if media_candidate:\n                self.assets.append(media_candidate)',
        )
    ])
    edit("adapters/google_pagespeed_live.py", [
        ("        params: dict[str, str | None],", "        params: dict[str, str | int | None],")
    ])
    edit("integrations/google/sitemaps.py", [
        ("        query: dict[str, str] = {}", "        query: dict[str, str | int | None] = {}")
    ])
    edit("integrations/authority_media/services.py", [
        (
            '            identifier = item.get("id") if isinstance(item.get("id"), dict) else {}\n            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}',
            '            raw_identifier = item.get("id")\n            identifier: dict[str, Any] = raw_identifier if isinstance(raw_identifier, dict) else {}\n            raw_snippet = item.get("snippet")\n            snippet: dict[str, Any] = raw_snippet if isinstance(raw_snippet, dict) else {}',
        ),
        (
            '        page_info = payload.get("pageInfo") if isinstance(payload.get("pageInfo"), dict) else {}',
            '        raw_page_info = payload.get("pageInfo")\n        page_info: dict[str, Any] = raw_page_info if isinstance(raw_page_info, dict) else {}',
        ),
        (
            "        issues = []\n        if not self.TIMESTAMP.search(text):",
            "        issues: list[dict[str, Any]] = []\n        if not self.TIMESTAMP.search(text):",
        ),
    ])

    type_handler_map("integrations/product_proof/adapters.py")

    edit("seoctl/cli.py", [
        ("from typing import Any, Callable", "from typing import Any, Callable, cast"),
        ("        return asdict(value)", "        return asdict(cast(Any, value))"),
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
