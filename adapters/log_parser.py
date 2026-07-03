"""Server log parser for bot crawl diagnostics."""

from __future__ import annotations

from pathlib import Path

from adapters.base import AdapterResult


class LogParserAdapter:
    name = "log_parser"

    BOT_MARKERS = ("googlebot", "bingbot", "GPTBot", "ClaudeBot", "PerplexityBot", "OAI-SearchBot")

    def fetch(self, path: str, **_: object) -> AdapterResult:
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
        counts = {marker: 0 for marker in self.BOT_MARKERS}
        for line in lines:
            lower = line.lower()
            for marker in self.BOT_MARKERS:
                if marker.lower() in lower:
                    counts[marker] += 1
        return AdapterResult(source=path, status="ok", data={"line_count": len(lines), "bot_hits": counts}, warnings=[])

