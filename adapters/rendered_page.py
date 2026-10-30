"""Headless render adapter for the rendered-visual-audit skill.

Renders a URL as a browser would, so agents can judge what a user (and a
JS-incapable AI crawler) actually sees. Returns the canonical AdapterResult.

Security: HTTP and browser egress connect only to vetted numeric public addresses.
Both renderer interfaces share one isolated browser boundary. HTTPS CONNECT keeps
TLS verification end-to-end; encrypted paths/queries are not visible to the proxy.

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

from collections.abc import Callable
from typing import Any

from adapters.base import AdapterResult
from adapters.rendered_evidence import blank_evidence, merge_rendered
from adapters.url_safety import (
    sanitize_headers_for_evidence,
    sanitize_text_for_evidence,
    sanitize_url_for_evidence,
    validate_public_url,
)
from integrations.technical.http import BoundedHttpClient
from security.browser_capture import guard_request, render_browser
from security.html_analysis import html_facts

_SPA_MARKERS = ('id="root"', 'id="app"', 'id="__next"', "data-reactroot", "ng-version")
_HTTP_TIMEOUT = 30
_MAX_RESPONSE_BYTES = 12_000_000
_RENDER_TIMEOUT_MS = 30_000
_SPA_TEXT_WORD_FLOOR = 120
_MODES = ("auto", "always", "never")
DEPENDENCY_MISSING = "dependency_missing"
RENDER_FAILED = "render_failed"
FETCH_FAILED = "fetch_failed"


def _raw_fetch(
    url: str,
    client: BoundedHttpClient | None = None,
) -> tuple[str, int | None, dict[str, str]]:
    transport = client or BoundedHttpClient(
        timeout=_HTTP_TIMEOUT,
        max_response_bytes=_MAX_RESPONSE_BYTES,
        max_redirects=10,
        user_agent="Mozilla/5.0 (compatible; SEO-Kit-Render/1.0)",
    )
    hop = transport.get(url)
    return (
        hop.body.decode("utf-8", "replace"),
        hop.status_code,
        sanitize_headers_for_evidence(hop.headers),
    )


def is_spa(raw_html: str) -> bool:
    """True when server HTML looks like a hydration shell with little real content."""
    if not raw_html:
        return False
    lowered = raw_html.lower()
    if not any(marker in lowered for marker in _SPA_MARKERS):
        return False
    text = ' '.join(html_facts(raw_html).text)
    return len(text.split()) < _SPA_TEXT_WORD_FLOOR


def _playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _raw_evidence(
    url: str, raw_html: str, status: int | None, headers: dict[str, str], warnings: list[str]
) -> dict[str, Any]:
    try:
        spa: bool | None = is_spa(raw_html)
    except ValueError as exc:
        spa = None
        warnings.append(f"analysis_failed: {sanitize_text_for_evidence(exc)}; SPA detection is Not Run.")
    data = blank_evidence(url, raw_html, status, headers, is_spa=False)
    data["is_spa"] = spa
    return data


def dependency_status() -> dict[str, str]:
    """Report optional-dependency availability without importing a browser."""
    return {"playwright": "installed" if _playwright_available() else "missing"}


def _guard_browser_request(route: Any, block: tuple[str, ...]) -> Any:
    return guard_request(route, block)


def playwright_render(url: str, block: tuple[str, ...] = ()) -> dict[str, Any]:
    """Render with Playwright Chromium. Raises on any failure; never returns partial data."""
    result = render_browser(url, timeout_ms=_RENDER_TIMEOUT_MS,
                            block_resource_types=block, accessibility=True)
    return {
        "content": result["html"],
        "status_code": result["status_code"],
        "accessibility_tree": result["accessibility_tree"],
        "console_errors": result["console_errors"],
        "render_ms": result["render_ms"],
        "render_engine": result["render_engine"],
        "network_policy": result["network_policy"],
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
            source="rendered_page",
            status="blocked",
            data={"url": sanitize_url_for_evidence(url)},
            warnings=[sanitize_text_for_evidence(exc)],
        )

    raw_html: str = ""
    status: int | None = None
    headers: dict[str, str] = {}
    try:
        raw_html, status, headers = _raw_fetch(safe_url)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"{FETCH_FAILED}: {sanitize_text_for_evidence(exc)}")

    data = _raw_evidence(safe_url, raw_html, status, headers, warnings)
    wants_render = mode == "always" or (mode == "auto" and data["is_spa"])
    if not wants_render:
        return AdapterResult(
            source="rendered_page",
            status="ok" if raw_html and not warnings else "partial",
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
        warnings.append(
            f"{RENDER_FAILED}: {sanitize_text_for_evidence(exc)}. "
            "Returned raw HTML only; rendered evidence is Not Run."
        )
        return AdapterResult(source="rendered_page", status="partial", data=data, warnings=warnings)

    merge_rendered(data, rendered, raw_html)
    return AdapterResult(source="rendered_page", status="ok", data=data, warnings=warnings)


class RenderedPageAdapter:
    name = "rendered_page"

    def fetch(self, url: str, mode: str = "auto", **kwargs: Any) -> AdapterResult:
        return fetch(url, mode=mode, **kwargs)
