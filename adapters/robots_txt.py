"""robots.txt validation adapter."""

from __future__ import annotations

from pathlib import Path

from adapters.base import AdapterResult


class RobotsTxtAdapter:
    name = "robots_txt"

    def fetch(
        self,
        path: str = "",
        text: str = "",
        user_agent: str = "*",
        meta_robots: str = "",
        x_robots_tag: str = "",
        **_: object,
    ) -> AdapterResult:
        source = path or "robots_text"
        content = text or Path(path).read_text(encoding="utf-8")
        warnings = []
        groups = self._groups(content)
        active = groups.get(user_agent.lower(), groups.get("*", []))
        disallow_all = any(rule.lower().strip() == "disallow: /" for rule in active)
        sitemap_count = len([line for line in content.splitlines() if line.lower().startswith("sitemap:")])
        meta_blocks_indexing = self._blocks_indexing(meta_robots)
        x_robots_blocks_indexing = self._blocks_indexing(x_robots_tag)
        if disallow_all:
            warnings.append(f"User-agent {user_agent} is disallowed from all crawling.")
        if meta_blocks_indexing:
            warnings.append("Meta robots directive blocks indexing.")
        if x_robots_blocks_indexing:
            warnings.append("X-Robots-Tag directive blocks indexing.")
        if sitemap_count == 0:
            warnings.append("No Sitemap directive found.")
        return AdapterResult(
            source=source,
            status="ok" if not warnings else "needs-review",
            data={
                "user_agent": user_agent,
                "disallow_all": disallow_all,
                "sitemap_count": sitemap_count,
                "meta_blocks_indexing": meta_blocks_indexing,
                "x_robots_blocks_indexing": x_robots_blocks_indexing,
            },
            warnings=warnings,
        )

    @staticmethod
    def _groups(content: str) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        current = "*"
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent:"):
                current = line.split(":", 1)[1].strip().lower()
                groups.setdefault(current, [])
            elif line.lower().startswith(("disallow:", "allow:")):
                groups.setdefault(current, []).append(line)
        return groups

    @staticmethod
    def _blocks_indexing(value: str) -> bool:
        directives = {part.strip().lower() for part in value.replace(";", ",").split(",")}
        return bool({"noindex", "none"} & directives)
