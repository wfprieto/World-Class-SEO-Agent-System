"""Fail closed on likely committed credentials while allowing explicit placeholders."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 2_000_000
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", ".seo-cache", "outputs", "build", "dist"}
EXCLUDED_FILES = {"scripts/scan_secrets.py"}
TEXT_SUFFIXES = {".py", ".md", ".json", ".yaml", ".yml", ".toml", ".txt", ".ps1", ".sh", ".env", ""}
PLACEHOLDER_MARKERS = (
    "placeholder", "example", "sample", "dummy", "fake", "test", "fixture",
    "invalid", "not-a-real", "redacted", "changeme", "your_", "${", "$env",
    "***", "...",
)

_PATTERNS = {
    "private_key": re.compile("BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    "openai_key": re.compile(r"\bsk-" + r"(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_" + r"[A-Za-z0-9]{30,}\b"),
    "aws_access_key": re.compile(r"\bAKIA" + r"[A-Z0-9]{16}\b"),
    "google_api_key": re.compile(r"\bAIza" + r"[A-Za-z0-9_-]{30,}\b"),
    "generic_secret_assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*[\"']([^\"']{12,})[\"']"
    ),
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    preview: str


def _tracked_files(root: Path) -> Iterable[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=root, timeout=20, stderr=subprocess.DEVNULL
        )
        for item in output.decode("utf-8").split("\0"):
            if item:
                yield root / item
        return
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    yield from (path for path in root.rglob("*") if path.is_file())


def _placeholder(value: str) -> bool:
    lowered = value.lower()
    for marker in PLACEHOLDER_MARKERS:
        if marker in {"${", "$env", "***", "...", "your_", "not-a-real"}:
            if marker in lowered:
                return True
        elif re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", lowered):
            return True
    return False


def scan(root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    for path in _tracked_files(root):
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if relative in EXCLUDED_FILES or any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.exists():
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in _PATTERNS.items():
                for match in pattern.finditer(line):
                    candidate = match.group(1) if match.lastindex else match.group(0)
                    if _placeholder(candidate) or "os.environ" in line or "getenv(" in line:
                        continue
                    findings.append(
                        Finding(relative, line_number, kind, candidate[:4] + "…REDACTED")
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan tracked repository text for likely secrets")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    findings = scan(args.root.resolve())
    if args.json:
        import json
        print(json.dumps({"status": "failed" if findings else "ok", "findings": [asdict(f) for f in findings]}, indent=2))
    elif findings:
        print("Secret scan failed:")
        for finding in findings:
            print(f"- {finding.path}:{finding.line} {finding.kind} {finding.preview}")
    else:
        print("Secret scan passed: no likely committed credentials found.")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
