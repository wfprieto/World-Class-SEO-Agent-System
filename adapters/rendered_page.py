"""Headless render adapter for the rendered-visual-audit skill.

Renders a URL as a browser would, so agents can judge what a user (and a
JS-incapable AI crawler) actually sees. Returns the canonical AdapterResult.

Security: outbound targets are validated by adapters.url_safety.validate_public_url
(the kit's single SSRF policy). Browser subresource requests are additionally
guarded, because the browser resolves DNS itself (rebinding defence).

Playwright is optional. Rendering is performed by an injectable `render_fn`, so the
success-path logic is testable without a live browser. When Playwright is missing or a
render fails, the adapter returns raw-fetch evidence with status "partial" and never
claims rendered, visual, or accessibility evidence it does not have.

Failure classification (warning prefixes, so callers can branch on cause):
  dependency_missing:  Playwright is not installed
  render_failed:       browser launched but navigation/rendering failed
  fetch_failed:        the raw HTTP fetch failed

Modes: auto (render only when an SPA shell is detected), always, never.
Install rendering: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
from typing import Any, Callable

from adapters.base import AdapterResult
from adapters.url_safety import host_is_public, validate_public_url

_SPA_MARKERS = ('id="root"', 'id="app"', 'id="__next"', "data-reactroot", "ng-version")
_HTTP_TIMEOUT = 30
_MAX_RESPONSE_BYTES = 12_000_000
_RENDER_TIMEOUT_MS = 30_000
_SPA_TEXT_WORD_FLOOR = 120
_MODES = ("auto", "always", "never")

DEPENDENCY_MISSING = "dependency_missing"
RENDER_FAILED = "render_failed"
FETCH_FAILED = "fetch_failed"


def _raw_fetch(url: str) -> tuple[str, int | None, dict]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; SEO-Kit-Render/1.0)"}
    )
    with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:
        body = response.read(_MAX_RESPONSE_BYTES + 1)
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ValueError("Response exceeds the maximum allowed size")
        return body.decode("utf-8", "replace"), response.status, dict(response.headers)


def is_spa(raw_html: str) -> bool:
    """True when server HTML looks like a hydration shell with little real content."""
    if not raw_html:
        return False
    lowered = raw_html.lower()
    if not any(marker in lowered for marker in _SPA_MARKERS):
        return False
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(text.split()) < _SPA_TEXT_WORD_FLOOR


def _playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def dependency_status() -> dict[str, str]:
    """Report optional-dependency availability without importing a browser."""
    return {"playwright": "installed" if _playwright_available() else "missing"}


def _blank_evidence(url: str, raw_html: str, status: int | None, headers: dict) -> dict[str, Any]:
    return {
        "url": url,
        "status_code": status,
        "is_spa": is_spa(raw_html),
        "mode_used": "raw",
        "render_engine": None,
        "raw_content": raw_html,
        "content": raw_html,
        "headers": headers,
        "accessibility_tree": None,
        "console_errors": [],
        "render_ms": 0,
        "js_added_chars": None,
        "evidence": {"rendered": "Not Run", "accessibility": "Not Run"},
    }


def playwright_render(url: str, block: tuple[str, ...] = ()) -> dict[str, Any]:
    """Render with Playwright Chromium. Raises on any failure; never returns partial data."""
    from playwright.sync_api import sync_playwright

    started = time.time()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        def guard(route):
            host = urllib.parse.urlparse(route.request.url).hostname
            if host and not host_is_public(host):
                return route.abort()
            if route.request.resource_type in block:
                return route.abort()
            return route.continue_()

        page.route("**/*", guard)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        response = page.goto(url, wait_until="networkidle", timeout=_RENDER_TIMEOUT_MS)
        rendered = page.content()
        tree = page.accessibility.snapshot()
        status = response.status if response else None
        context.close()
        browser.close()

    return {
        "content": rendered,
        "status_code": status,
        "accessibility_tree": tree,
        "console_errors": errors,
        "render_ms": round((time.time() - started) * 1000),
        "render_engine": "playwright-chromium",
    }


def fetch(
    url: str,
    mode: str = "auto",
    block: tuple[str, ...] = (),
    render_fn: Callable[..., dict[str, Any]] | None = None,
    **_: Any,
) -> AdapterResult:
    """Fetch and optionally render a URL.

    `render_fn` is injectable so the rendered success path can be exercised in tests
    without a live browser. Injecting a renderer does not imply a real browser ran; the
    evidence block records exactly what produced the result.
    """
    if mode not in _MODES:
        raise ValueError(f"mode must be one of {_MODES}")
    warnings: list[str] = []

    try:
        safe_url = validate_public_url(url)
    except ValueError as exc:
        return AdapterResult(
            source="rendered_page", status="blocked", data={"url": url}, warnings=[str(exc)]
        )

    raw_html, status, headers = "", None, {}
    try:
        raw_html, status, headers = _raw_fetch(safe_url)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{FETCH_FAILED}: {exc}")

    data = _blank_evidence(safe_url, raw_html, status, headers)
    wants_render = mode == "always" or (mode == "auto" and data["is_spa"])
    if not wants_render:
        return AdapterResult(
            source="rendered_page",
            status="ok" if raw_html else "partial",
            data=data,
            warnings=warnings,
        )

    renderer = render_fn
    if renderer is None:
        if not _playwright_available():
            warnings.append(
                f"{DEPENDENCY_MISSING}: Playwright is not installed. Returned raw HTML only; "
                "rendered, visual and accessibility evidence is Not Run. "
                "Install: pip install playwright && playwright install chromium"
            )
            return AdapterResult(
                source="rendered_page", status="partial", data=data, warnings=warnings
            )
        renderer = playwright_render

    try:
        rendered = renderer(safe_url, block)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{RENDER_FAILED}: {exc}. Returned raw HTML only; rendered evidence is Not Run.")
        return AdapterResult(source="rendered_page", status="partial", data=data, warnings=warnings)

    data.update(
        {
            "mode_used": "rendered",
            "render_engine": rendered.get("render_engine", "injected"),
            "content": rendered.get("content", raw_html),
            "status_code": rendered.get("status_code") or data["status_code"],
            "accessibility_tree": rendered.get("accessibility_tree"),
            "console_errors": rendered.get("console_errors", []),
            "render_ms": rendered.get("render_ms", 0),
            "js_added_chars": len(rendered.get("content", "")) - len(raw_html or ""),
            "evidence": {"rendered": "Verified", "accessibility": "Verified"},
        }
    )
    return AdapterResult(source="rendered_page", status="ok", data=data, warnings=warnings)


class RenderedPageAdapter:
    name = "rendered_page"

    def fetch(self, url: str, mode: str = "auto", **kwargs: Any) -> AdapterResult:
        return fetch(url, mode=mode, **kwargs)
