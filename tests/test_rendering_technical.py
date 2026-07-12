from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.base import AdapterResult
from integrations.technical.browser import (
    BrowserHealth,
    BrowserNotConfigured,
    RenderedPageService,
)
from integrations.technical.http import BoundedHttpClient, HttpHop
from integrations.technical.inspection import TechnicalInspectionService


class QueueHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class FakeRenderer:
    def __init__(self):
        self.calls = []

    def health(self):
        return BrowserHealth(
            dependency="installed",
            browser="installed",
            executable="/fake/chromium",
            state="AVAILABLE",
            install_command="python -m playwright install chromium",
            uninstall_command="python -m playwright uninstall chromium",
        )

    def render(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return {
            "url": url,
            "final_url": url,
            "status_code": 200,
            "html": "<html><head><title>Rendered</title></head><body><main>Hello</main></body></html>",
            "title": "Rendered",
            "text": "Hello",
            "console_errors": [],
            "page_errors": [],
            "failed_requests": [],
            "render_ms": 42,
            "render_engine": "injected-browser",
            "screenshot_bytes": b"\x89PNG\r\n\x1a\nfixture",
            "viewport": {"width": 1440, "height": 900},
        }


def response(url: str, body: str = "", status: int = 200, headers=None):
    return HttpHop(
        requested_url=url,
        final_url=url,
        status_code=status,
        headers=headers or {},
        body=body.encode("utf-8"),
        elapsed_ms=5,
    )


def test_browser_health_reports_missing_dependency_truthfully(monkeypatch):
    monkeypatch.setattr("integrations.technical.browser.importlib.util.find_spec", lambda _: None)
    health = RenderedPageService().health()
    assert health.state == "NOT_CONFIGURED"
    assert health.dependency == "missing"
    assert "playwright install chromium" in health.install_command
    assert health.uninstall_command.endswith("uninstall chromium")


def test_render_and_screenshot_use_injected_browser_and_safe_output(tmp_path: Path):
    renderer = FakeRenderer()
    service = RenderedPageService(renderer=renderer)
    rendered = service.render("https://example.com/page", wait_until="domcontentloaded")
    assert rendered.status == "ok"
    assert rendered.data["data_state"] == "AVAILABLE"
    assert rendered.data["render_engine"] == "injected-browser"
    assert rendered.data["html"].startswith("<html")
    assert renderer.calls[0][1]["wait_until"] == "domcontentloaded"

    screenshot = service.screenshot(
        "https://example.com/page",
        output=tmp_path / "capture.png",
        full_page=True,
    )
    assert screenshot.status == "ok"
    assert Path(screenshot.data["path"]).read_bytes().startswith(b"\x89PNG")
    assert screenshot.data["full_page"] is True

    with pytest.raises(ValueError, match="png"):
        service.screenshot(
            "https://example.com/page",
            output=tmp_path / "capture.jpg",
        )


def test_browser_service_never_claims_rendered_evidence_when_browser_missing():
    class MissingRenderer:
        def health(self):
            return BrowserHealth(
                dependency="missing",
                browser="unknown",
                executable=None,
                state="NOT_CONFIGURED",
                install_command="python -m playwright install chromium",
                uninstall_command="python -m playwright uninstall chromium",
            )

        def render(self, url, **kwargs):
            raise BrowserNotConfigured("Chromium is not installed")

    result = RenderedPageService(renderer=MissingRenderer()).render("https://example.com")
    assert result.status == "not_configured"
    assert result.data["data_state"] == "NOT_CONFIGURED"
    assert result.data["rendered"] is False


def test_robots_inspection_preserves_groups_rules_and_sitemaps():
    text = """User-agent: *
Disallow: /private/
Allow: /private/public/
Sitemap: https://example.com/sitemap.xml

User-agent: Googlebot
Disallow:
"""
    service = TechnicalInspectionService(http=QueueHttp([
        response("https://example.com/robots.txt", text, headers={"Content-Type": "text/plain"})
    ]))
    result = service.robots("https://example.com")
    assert result.status == "ok"
    assert result.data["groups"][0]["user_agents"] == ["*"]
    assert result.data["groups"][0]["rules"][0] == {"directive": "disallow", "value": "/private/"}
    assert result.data["sitemaps"] == ["https://example.com/sitemap.xml"]
    assert result.data["data_state"] == "AVAILABLE"


def test_sitemap_supports_urlset_and_index_and_rejects_unsafe_locations():
    xml = """<?xml version='1.0'?>
<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
  <url><loc>https://example.com/a</loc></url>
  <url><loc>https://example.com/a</loc></url>
  <url><loc>http://127.0.0.1/private</loc></url>
</urlset>"""
    service = TechnicalInspectionService(http=QueueHttp([
        response("https://example.com/sitemap.xml", xml, headers={"Content-Type": "application/xml"})
    ]))
    result = service.sitemap("https://example.com/sitemap.xml")
    assert result.status == "needs-review"
    assert result.data["kind"] == "urlset"
    assert result.data["url_count"] == 3
    assert result.data["duplicates"] == ["https://example.com/a"]
    assert result.data["unsafe_locations"] == ["http://127.0.0.1/private"]


def test_hreflang_preload_indexability_and_schema_are_derived_from_html():
    html = """<html><head>
<link rel='canonical' href='https://example.com/en/page'>
<meta name='robots' content='noindex,follow'>
<link rel='alternate' hreflang='en-US' href='https://example.com/en/page'>
<link rel='alternate' hreflang='fr-FR' href='https://example.com/fr/page'>
<link rel='alternate' hreflang='x-default' href='https://example.com/page'>
<link rel='preload' href='/hero.webp' as='image' fetchpriority='high'>
<script type='application/ld+json'>{"@context":"https://schema.org","@type":"Article","headline":"Example"}</script>
</head><body><h1>Example</h1></body></html>"""
    service = TechnicalInspectionService(http=QueueHttp([
        response("https://example.com/en/page", html, headers={"X-Robots-Tag": "index, follow"})
    ]))
    hreflang = service.hreflang("https://example.com/en/page")
    assert hreflang.data["alternate_count"] == 3
    assert hreflang.data["has_x_default"] is True
    assert hreflang.data["invalid_language_codes"] == []

    service.http = QueueHttp([response("https://example.com/en/page", html)])
    preload = service.preload("https://example.com/en/page")
    assert preload.data["preloads"][0]["as"] == "image"
    assert preload.data["preloads"][0]["fetchpriority"] == "high"

    service.http = QueueHttp([
        response("https://example.com/en/page", html, headers={"X-Robots-Tag": "index, follow"})
    ])
    indexability = service.indexability("https://example.com/en/page")
    assert indexability.data["indexable"] is False
    assert "meta_robots_noindex" in indexability.data["blocking_reasons"]
    assert indexability.data["canonical"] == "https://example.com/en/page"

    detected = service.schema_detect(html=html, source="fixture")
    assert detected.data["item_count"] == 1
    assert detected.data["types"] == ["Article"]
    validated = service.schema_validate(jsonld=detected.data["items"][0])
    assert validated.status == "ok"


def test_schema_generate_is_bounded_and_does_not_invent_business_facts():
    service = TechnicalInspectionService(http=QueueHttp([]))
    result = service.schema_generate(
        schema_type="Organization",
        values={"name": "Example Inc.", "url": "https://example.com"},
    )
    assert result.data["jsonld"] == {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Example Inc.",
        "url": "https://example.com",
    }
    assert result.data["omitted_optional_fields"]
    with pytest.raises(ValueError, match="supported"):
        service.schema_generate(schema_type="MedicalClinic", values={"name": "X"})


def test_redirect_chain_is_bounded_and_detects_loops():
    client = BoundedHttpClient(max_redirects=3, opener=None)
    client._single_request = lambda url: {
        "https://example.com/a": response(
            url,
            status=301,
            headers={"Location": "https://example.com/b"},
        ),
        "https://example.com/b": response(
            url,
            status=302,
            headers={"Location": "https://example.com/a"},
        ),
    }[url]
    chain = client.redirect_chain("https://example.com/a")
    assert chain["data_state"] == "BLOCKED"
    assert chain["loop_detected"] is True
    assert len(chain["hops"]) == 2


def test_cwv_normalizes_fixture_without_claiming_live_measurement(tmp_path: Path):
    fixture = {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.91}},
            "audits": {
                "largest-contentful-paint": {"numericValue": 2300},
                "interaction-to-next-paint": {"numericValue": 180},
                "cumulative-layout-shift": {"numericValue": 0.08},
            },
        }
    }
    path = tmp_path / "psi.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")
    result = TechnicalInspectionService(http=QueueHttp([])).cwv(fixture_path=path)
    assert result.status == "ok"
    assert result.data["source"] == "fixture"
    assert result.data["metrics"]["lcp_ms"]["rating"] == "good"
    assert result.data["metrics"]["inp_ms"]["rating"] == "good"
    assert result.data["metrics"]["cls"]["rating"] == "good"
    assert result.data["live_measurement"] is False
