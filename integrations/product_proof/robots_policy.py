"""Pure, bounded robots policy matching; no fetch or external capabilities."""

from __future__ import annotations

import urllib.parse
from typing import Any

MAX_ROBOTS_BYTES = 500 * 1024
MAX_ROBOTS_RULES = 10_000
MAX_ROBOTS_PATH_CHARACTERS = 8192
MAX_ROBOTS_MATCH_WORK = 2_000_000

def validate_robots_text(text: str) -> None:
    if len(text) > MAX_ROBOTS_BYTES or len(text.encode("utf-8")) > MAX_ROBOTS_BYTES:
        raise ValueError("Robots text byte limit exceeded; crawl permission is unknown.")


class RobotsPolicy:
    """Google-style longest-path matcher with least-restrictive ties."""

    def __init__(self, groups: list[dict[str, Any]]) -> None:
        entries = len(groups)
        characters = 0
        for group in groups:
            entries += len(group.get("user_agents", [])) + len(group.get("rules", []))
            if entries > MAX_ROBOTS_RULES:
                raise ValueError("Robots policy rule/group limit exceeded; crawl permission is unknown.")
            values = [str(value) for value in group.get("user_agents", [])]
            values.extend(str(rule.get("path", "")) for rule in group.get("rules", []))
            for value in values:
                if len(value) > MAX_ROBOTS_PATH_CHARACTERS:
                    raise ValueError("Robots policy path limit exceeded; crawl permission is unknown.")
                characters += len(value.encode("utf-8"))
                if characters > MAX_ROBOTS_BYTES:
                    raise ValueError("Robots policy size limit exceeded; crawl permission is unknown.")
        self.groups = groups

    @staticmethod
    def _matches(path: str, target: str, budget: list[int]) -> bool:
        """Deterministic glob matching; a shared budget bounds all selected rules."""
        anchored = path.endswith("$")
        pattern = path[:-1] if anchored else path
        cursor = position = 0
        star = -1
        retry = 0
        while position < len(target):
            budget[0] -= 1
            if budget[0] < 0:
                raise ValueError("Robots matching work limit exceeded; crawl permission is unknown.")
            if cursor == len(pattern) and not anchored:
                return True
            if cursor < len(pattern) and pattern[cursor] == "*":
                star, retry = cursor, position
                cursor += 1
            elif cursor < len(pattern) and pattern[cursor] == target[position]:
                cursor += 1
                position += 1
            elif star >= 0:
                retry += 1
                position, cursor = retry, star + 1
            else:
                return False
        return all(char == "*" for char in pattern[cursor:])

    @staticmethod
    def _specificity(path: str) -> int:
        return len(path.removesuffix("$").replace("*", ""))

    @staticmethod
    def _target(url: str, user_agent: str) -> str:
        if len(url) > 2 * MAX_ROBOTS_PATH_CHARACTERS or len(user_agent) > MAX_ROBOTS_PATH_CHARACTERS:
            raise ValueError("Robots URL/user-agent limit exceeded; crawl permission is unknown.")
        parsed = urllib.parse.urlsplit(url)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        if len(target) > MAX_ROBOTS_PATH_CHARACTERS:
            raise ValueError("Robots target path limit exceeded; crawl permission is unknown.")
        return target

    def _selected_groups(self, user_agent: str) -> list[dict[str, Any]]:
        ua = user_agent.lower()
        matching: list[tuple[int, dict[str, Any]]] = []
        for group in self.groups:
            agents = [str(value).lower() for value in group.get("user_agents", [])]
            exact = [agent for agent in agents if agent != "*" and agent in ua]
            if exact:
                matching.append((max(len(agent) for agent in exact), group))
            elif "*" in agents:
                matching.append((0, group))
        if not matching:
            return []
        most_specific = max(score for score, _ in matching)
        return [group for score, group in matching if score == most_specific]

    def allowed(self, url: str, user_agent: str = "googlebot") -> bool:
        target = self._target(url, user_agent)
        rules: list[tuple[int, bool]] = []
        budget = [MAX_ROBOTS_MATCH_WORK]
        for group in self._selected_groups(user_agent):
            for rule in group.get("rules", []):
                path = str(rule.get("path", ""))
                if not path:
                    continue
                if self._matches(path, target, budget):
                    rules.append((self._specificity(path), rule.get("directive") == "allow"))
        if not rules:
            return True
        longest = max(score for score, _ in rules)
        return any(allow for score, allow in rules if score == longest)
