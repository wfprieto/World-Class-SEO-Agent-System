from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from adapters.base import AdapterResult
from seoctl import technical_cli
from seoctl.cli import EXIT_OK, EXIT_UNAVAILABLE
from seoctl.entrypoint import HANDLERS
from seoctl.registry import command_specs

ROOT = Path(__file__).resolve().parents[1]


class FakeBrowser:
    def health(self):
        from integrations.technical.browser import BrowserHealth

        return BrowserHealth(
            dependency="installed",
            browser="installed",
            executable="/fake/chromium",
            state="AVAILABLE",
            install_command="python -m playwright install chromium",
            uninstall_command="python -m playwright uninstall chromium",
        )

    def render(self, url, **kwargs):
        return AdapterResult(
            source="rendered_page",
            status="ok",
            data={"url": url, "rendered": True, "data_state": "AVAILABLE", "kwargs": kwargs},
            warnings=[],
        )

    def screenshot(self, url, output, **kwargs):
        return AdapterResult(
            source="rendered_page",
            status="ok",
            data={"url": url, "path": str(output), "data_state": "AVAILABLE", "kwargs": kwargs},
            warnings=[],
        )


class FakeTechnical:
    def _result(self, operation, **kwargs):
        return AdapterResult(
            source="technical_inspection",
            status="ok",
            data={"operation": operation, "data_state": "AVAILABLE", "kwargs": kwargs},
            warnings=[],
        )

    def robots(self, url): return self._result("robots", url=url)
    def sitemap(self, url): return self._result("sitemap", url=url)
    def hreflang(self, url): return self._result("hreflang", url=url)
    def preload(self, url): return self._result("preload", url=url)
    def redirect_chain(self, url, max_redirects=10): return self._result("redirect-chain", url=url, max_redirects=max_redirects)
    def indexability(self, url): return self._result("indexability", url=url)
    def cwv(self, url=None, fixture_path=None, strategy="mobile"): return self._result("cwv", url=url, fixture_path=fixture_path, strategy=strategy)
    def schema_detect(self, url=None, html=None, source=None): return self._result("schema-detect", url=url, html=html, source=source)
    def schema_validate(self, jsonld): return self._result("schema-validate", jsonld=jsonld)
    def schema_generate(self, schema_type, values): return self._result("schema-generate", schema_type=schema_type, values=values)


def test_all_render_technical_schema_commands_route(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(technical_cli, "RenderedPageService", FakeBrowser)
    monkeypatch.setattr(technical_cli, "TechnicalInspectionService", FakeTechnical)

    commands = [
        (["render", "health"], "render.health"),
        (["render", "page", "--url", "https://example.com"], "render.page"),
        (["render", "screenshot", "--url", "https://example.com", "--output", str(tmp_path / "shot.png")], "render.screenshot"),
        (["technical", "robots", "--url", "https://example.com"], "technical.robots"),
        (["technical", "sitemap", "--url", "https://example.com/sitemap.xml"], "technical.sitemap"),
        (["technical", "hreflang", "--url", "https://example.com"], "technical.hreflang"),
        (["technical", "preload", "--url", "https://example.com"], "technical.preload"),
        (["technical", "redirect-chain", "--url", "https://example.com"], "technical.redirect-chain"),
        (["technical", "indexability", "--url", "https://example.com"], "technical.indexability"),
        (["technical", "cwv", "--fixture", "fixture.json"], "technical.cwv"),
        (["schema", "detect", "--url", "https://example.com"], "schema.detect"),
        (["schema", "validate", "--json", '{"@context":"https://schema.org","@type":"Article"}'], "schema.validate"),
        (["schema", "generate", "--type", "Organization", "--value", "name=Example", "--value", "url=https://example.com"], "schema.generate"),
    ]
    for argv, command_id in commands:
        payload, code = technical_cli.run(argv)
        assert code == EXIT_OK, (argv, payload)
        assert payload["command"] == command_id


def test_missing_browser_returns_structured_unavailable(monkeypatch):
    class MissingBrowser(FakeBrowser):
        def health(self):
            from integrations.technical.browser import BrowserHealth

            return BrowserHealth(
                dependency="missing",
                browser="unknown",
                executable=None,
                state="NOT_CONFIGURED",
                install_command="python -m playwright install chromium",
                uninstall_command="python -m playwright uninstall chromium",
            )

    monkeypatch.setattr(technical_cli, "RenderedPageService", MissingBrowser)
    payload, code = technical_cli.run(["render", "health"])
    assert code == EXIT_UNAVAILABLE
    assert payload["status"] == "not_configured"
    assert payload["data"]["state"] == "NOT_CONFIGURED"


def test_installed_module_help_lists_complete_phase_commands():
    for family, expected in {
        "render": ["health", "page", "screenshot"],
        "technical": ["robots", "sitemap", "hreflang", "preload", "redirect-chain", "indexability", "cwv"],
        "schema": ["detect", "validate", "generate"],
    }.items():
        completed = subprocess.run(
            [sys.executable, "-m", "seoctl", family, "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        for command in expected:
            assert command in completed.stdout


def test_every_updated_registry_handler_resolves():
    for spec in command_specs():
        assert spec.handler in HANDLERS
        assert callable(HANDLERS[spec.handler])
