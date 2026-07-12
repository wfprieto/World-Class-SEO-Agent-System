from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from adapters.base import AdapterResult
from seoctl import content_cli
from seoctl.cli import EXIT_BLOCKED, EXIT_OK
from seoctl.entrypoint import HANDLERS
from seoctl.registry import command_specs

ROOT = Path(__file__).resolve().parents[1]


class FakeContentService:
    def _result(self, operation, status="ok", **kwargs):
        return AdapterResult(
            source="content_intelligence",
            status=status,
            data={"operation": operation, "data_state": "AVAILABLE", "kwargs": kwargs},
            warnings=[],
        )

    def quality(self, **kwargs): return self._result("quality", **kwargs)
    def verify(self, **kwargs): return self._result("verify", **kwargs)
    def entities(self, **kwargs): return self._result("entities", **kwargs)
    def brief(self, **kwargs): return self._result("brief", **kwargs)
    def decay(self, **kwargs): return self._result("decay", **kwargs)
    def compare(self, **kwargs): return self._result("compare", **kwargs)
    def humanize(self, **kwargs): return self._result("humanize", **kwargs)


def _write(path: Path, value) -> str:
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")
    return str(path)


def test_all_content_intelligence_commands_route(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(content_cli, "ContentIntelligenceService", FakeContentService)
    text = _write(tmp_path / "content.md", "# Title\n\nUseful copy.")
    claims = _write(tmp_path / "claims.json", [{"id": "c1", "text": "Claim"}])
    sources = _write(tmp_path / "sources.json", [{"id": "s1", "title": "Source"}])
    catalog = _write(tmp_path / "catalog.json", [{"id": "x", "name": "Example"}])
    relevance = _write(tmp_path / "relevance.json", {"verdict": "RELEVANT"})
    serp = _write(tmp_path / "serp.json", {"status": "SUFFICIENT"})
    gains = _write(tmp_path / "gains.json", ["New evidence"])
    current = _write(tmp_path / "current.json", {"period_start": "2026-06-01", "period_end": "2026-06-30", "metrics": {}})
    prior = _write(tmp_path / "prior.json", {"period_start": "2026-05-01", "period_end": "2026-05-31", "metrics": {}})
    right = _write(tmp_path / "right.md", "# Title\n\nOther useful copy.")

    commands = [
        (["quality", "--input", text, "--title", "Title"], "content.quality"),
        (["verify", "--claims", claims, "--sources", sources], "content.verify"),
        (["entities", "--input", text, "--catalog", catalog], "content.entities"),
        ([
            "brief", "--relevance", relevance, "--serp", serp,
            "--information-gain", gains, "--sources", sources,
            "--audience", "SEO leaders", "--intent", "informational",
            "--primary-question", "What should we publish?", "--section", "Evidence",
        ], "content.brief"),
        (["decay", "--current", current, "--prior", prior], "content.decay"),
        (["compare", "--left", text, "--right", right], "content.compare"),
        (["humanize", "--input", text], "content.humanize"),
    ]
    for argv, command_id in commands:
        payload, code = content_cli.run(argv)
        assert code == EXIT_OK, (argv, payload)
        assert payload["command"] == command_id


def test_blocked_brief_returns_blocked_exit(monkeypatch, tmp_path: Path):
    class Blocked(FakeContentService):
        def brief(self, **kwargs):
            return self._result("brief", status="blocked", **kwargs)

    monkeypatch.setattr(content_cli, "ContentIntelligenceService", Blocked)
    relevance = _write(tmp_path / "relevance.json", {"verdict": "NOT_RELEVANT"})
    serp = _write(tmp_path / "serp.json", {"status": "SUFFICIENT"})
    gains = _write(tmp_path / "gains.json", [])
    sources = _write(tmp_path / "sources.json", [])
    payload, code = content_cli.run([
        "brief", "--relevance", relevance, "--serp", serp,
        "--information-gain", gains, "--sources", sources,
        "--audience", "SEO leaders", "--intent", "informational",
        "--primary-question", "What should we publish?",
    ])
    assert code == EXIT_BLOCKED
    assert payload["status"] == "blocked"


def test_humanize_can_write_reviewable_output(monkeypatch, tmp_path: Path):
    class Humanized(FakeContentService):
        def humanize(self, **kwargs):
            return AdapterResult(
                source="content_intelligence",
                status="ok",
                data={
                    "operation": "humanize",
                    "transformed_text": "Clear text.",
                    "purpose": "clarity_and_readability",
                    "ai_detector_evasion": "NOT_SUPPORTED",
                },
                warnings=[],
            )

    monkeypatch.setattr(content_cli, "ContentIntelligenceService", Humanized)
    source = _write(tmp_path / "input.txt", "Filler text.")
    output = tmp_path / "output.txt"
    payload, code = content_cli.run([
        "humanize", "--input", source, "--output", str(output)
    ])
    assert code == EXIT_OK
    assert output.read_text(encoding="utf-8") == "Clear text."
    assert payload["data"]["output_path"] == str(output.resolve())


def test_installed_help_lists_new_content_commands():
    completed = subprocess.run(
        [sys.executable, "-m", "seoctl", "content", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    for command in (
        "quality",
        "verify",
        "entities",
        "brief",
        "decay",
        "compare",
        "humanize",
    ):
        assert command in completed.stdout


def test_every_updated_registry_handler_resolves():
    for spec in command_specs():
        assert spec.handler in HANDLERS
        assert callable(HANDLERS[spec.handler])
