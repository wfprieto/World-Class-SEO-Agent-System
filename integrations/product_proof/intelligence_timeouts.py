"""Offline-safe SEO intelligence analyzers derived from the governed source corpus."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from contracts.adapter import AdapterResult
from sensitive_data import redact

_COMMON_LOG = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[[^\]]+\]\s+"(?P<method>\S+)\s+(?P<path>\S+)\s+[^\"]+"\s+(?P<status>\d{3})\s+(?P<bytes>\S+)(?:\s+"[^\"]*"\s+"(?P<ua>[^\"]*)")?'
)
_RESPONSE_TIME = re.compile(r"(?:request_time|rt|response_time)[=:](?P<seconds>\d+(?:\.\d+)?)")
AI_USER_AGENTS = {
    "OpenAI on-demand retrieval": ("chatgpt-user", "oai-searchbot"),
    "OpenAI training": ("gptbot",),
    "Anthropic": ("claudebot",),
    "Perplexity": ("perplexitybot", "perplexity-user"),
    "Google extended use control": ("google-extended",),
    "Apple extended": ("applebot-extended",),
    "Common Crawl": ("ccbot",),
    "Meta external": ("meta-externalagent",),
}


def _classify_ua(user_agent: str) -> str | None:
    lowered = user_agent.lower()
    for label, tokens in AI_USER_AGENTS.items():
        if any(token in lowered for token in tokens):
            return label
    return None


@dataclass(frozen=True)
class TimeoutRecord:
    line: int
    bot_family: str
    status: int
    path: str
    response_seconds: float | None


def _timeout_samples(text: str) -> tuple[
    list[TimeoutRecord], Counter[str], Counter[tuple[str, int]], Counter[str],
    dict[str, list[float]], int,
]:
    records: list[TimeoutRecord] = []
    ai_requests: Counter[str] = Counter()
    statuses: Counter[tuple[str, int]] = Counter()
    path_counts: Counter[str] = Counter()
    response_samples: dict[str, list[float]] = defaultdict(list)
    malformed = 0
    for line_number, raw in enumerate(text.splitlines(), 1):
        match = _COMMON_LOG.search(raw)
        if not match:
            malformed += 1
            continue
        family = _classify_ua(match.group("ua") or "")
        if not family:
            continue
        status = int(match.group("status"))
        path = str(redact(match.group("path")))
        time_match = _RESPONSE_TIME.search(raw)
        seconds = float(time_match.group("seconds")) if time_match else None
        ai_requests[family] += 1
        statuses[(family, status)] += 1
        path_counts[path] += 1
        if seconds is not None:
            response_samples[family].append(seconds)
        if status == 499:
            records.append(TimeoutRecord(line_number, family, status, path, seconds))
    return records, ai_requests, statuses, path_counts, response_samples, malformed


class AITimeoutAnalyzer:
    name = "ai_timeout_analysis"

    def analyze(self, *, log_path: str | Path, server_stack: str) -> AdapterResult:
        stack = server_stack.strip().lower()
        if not stack:
            raise ValueError("server_stack is required because 499 is server-specific evidence")
        text = Path(log_path).read_text(encoding="utf-8-sig", errors="replace")
        records, ai_requests, statuses, path_counts, response_samples, malformed = _timeout_samples(text)
        total_ai = sum(ai_requests.values())
        timeout_count = len(records)
        warnings: list[str] = []
        if stack not in {"nginx", "openresty", "ingress-nginx", "unknown-nginx-compatible"}:
            warnings.append(
                "HTTP 499 is an nginx-family convention. Confirm the server or proxy's status semantics before interpreting it as a client-closed request."
            )
        if total_ai == 0:
            warnings.append(
                "No recognized AI crawler or user-triggered fetcher requests were found in the supplied log."
            )
        medians: dict[str, float] = {}
        for family, samples in response_samples.items():
            ordered = sorted(samples)
            mid = len(ordered) // 2
            medians[family] = round(
                ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2, 4
            )
        data = {
            "operation": "ai_timeouts",
            "server_stack": server_stack,
            "ai_requests": total_ai,
            "timeout_499_count": timeout_count,
            "timeout_rate": round(timeout_count / total_ai, 4) if total_ai else None,
            "by_bot_family": dict(sorted(ai_requests.items())),
            "status_counts": [
                {"bot_family": family, "status": status, "count": count}
                for (family, status), count in sorted(statuses.items())
            ],
            "median_response_seconds": medians,
            "top_paths": [
                {"path": path, "count": count} for path, count in path_counts.most_common(20)
            ],
            "timeouts": [asdict(record) for record in records[:1000]],
            "truncated": timeout_count > 1000,
            "malformed_lines": malformed,
            "evidence_class": "OBSERVED_OPERATOR_SUPPLIED",
            "limitations": [
                "A 499 is not part of the HTTP standard and must be interpreted in the context of the actual server or proxy.",
                "User-agent strings can be spoofed. This analysis does not verify source IP ownership.",
                "A timeout correlation does not prove that a search or AI system excluded the URL from an answer.",
            ],
        }
        return AdapterResult(
            source=self.name, status="ok" if total_ai else "empty", data=data, warnings=warnings
        )
