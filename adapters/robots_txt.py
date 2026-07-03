"""robots.txt validation adapter."""

from __future__ import annotations

from pathlib import Path

from adapters.base import AdapterResult


class RobotsTxtAdapter:
    name = "robots_txt"

    def fetch(self, path: str = "", text: str = "", user_agent: str = "*", **_: object) -> AdapterResult:
        source = path or "robots_text"
        content = text or Path(path).read_text(encoding="utf-8")
        warnings = []
        groups = self._groups(content)
        active = groups.get(user_agent.lower(), groups.get("*", []))
        disallow_all = any(rule.lower().strip() == "disallow: /" for rule in active)
        sitemap_count = len([line for line in content.splitlines() if line.lower().startswith("sitemap:")])
        if disallow_all:
            warnings.append(f"User-agent {user_agent} is disallowed from all crawling.")
        if sitemap_count == 0:
            warnings.append("No Sitemap directive found.")
        return AdapterResult(source=source, status="ok" if not warnings else "needs-review", data={"user_agent": user_agent, "disallow_all": disallow_all, "sitemap_count": sitemap_count}, warnings=warnings)

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
