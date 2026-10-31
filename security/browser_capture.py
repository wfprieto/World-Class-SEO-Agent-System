"""Shared isolated Chromium capture for both supported renderer interfaces."""

from __future__ import annotations

import time
import urllib.parse
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from security.browser_proxy import BrowserEgress, validate_egress_limits
from security.url_safety import (
    sanitize_text_for_evidence,
    sanitize_url_for_evidence,
    validate_public_url,
)


def guard_request(route: Any, block: tuple[str, ...]) -> Any:
    if urllib.parse.urlsplit(route.request.url).scheme in {"data", "blob", "about"}:
        return route.continue_()
    try:
        validate_public_url(route.request.url)
    except ValueError:
        return route.abort()
    if route.request.resource_type in block:
        return route.abort()
    return route.continue_()


def _append(items: list, value: Any, limit: int) -> None:
    if len(items) < limit:
        items.append(value)


def _capture(
    page: Any, context: Any, *, screenshot: bool, full_page: bool, accessibility: bool
) -> dict[str, Any]:
    html = page.content()
    if len(html.encode("utf-8")) > 12_000_000:
        raise ValueError("rendered HTML exceeds 12 MB output ceiling")
    text = page.locator("body").inner_text(timeout=5_000) if page.locator("body").count() else ""
    if len(text.encode("utf-8")) > 12_000_000:
        raise ValueError("rendered text exceeds 12 MB output ceiling")
    result: dict[str, Any] = {
        "html": html,
        "title": page.title(),
        "text": text,
        "screenshot_bytes": None,
    }
    if screenshot:
        if full_page:
            dimensions = page.evaluate(
                "({w:document.documentElement.scrollWidth,h:document.documentElement.scrollHeight})"
            )
            if dimensions["w"] * dimensions["h"] > 50_000_000:
                raise ValueError("full-page screenshot exceeds 50 million pixel ceiling")
        image = page.screenshot(
            full_page=full_page, type="png", animations="disabled", timeout=10_000
        )
        if len(image) > 25_000_000:
            raise ValueError("screenshot exceeds 25 MB output ceiling")
        result["screenshot_bytes"] = image
    if accessibility:
        session = context.new_cdp_session(page)
        try:
            tree = session.send("Accessibility.getFullAXTree")
            if len(tree.get("nodes", [])) > 20_000:
                raise ValueError("accessibility tree exceeds 20000 node ceiling")
            result["accessibility_tree"] = tree
        finally:
            session.detach()
    return result


@contextmanager
def _browser_context(
    playwright: Any,
    egress: BrowserEgress,
    *,
    timeout_ms: int,
    width: int,
    height: int,
    user_agent: str,
    block: tuple[str, ...],
) -> Iterator[Any]:
    browser = playwright.chromium.launch(
        headless=True,
        timeout=timeout_ms,
        proxy={key: egress.proxy[key] for key in ("server", "bypass", "username", "password")},
        args=[
            "--proxy-bypass-list=<-loopback>",
            "--disable-quic",
            "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
        ],
    )
    try:
        context = browser.new_context(
            viewport={"width": width, "height": height},
            user_agent=user_agent,
            ignore_https_errors=False,
            java_script_enabled=True,
            service_workers="block",
            accept_downloads=False,
        )
        try:
            context.set_default_timeout(min(timeout_ms, 10_000))
            context.route("**/*", lambda route: guard_request(route, block))
            yield context
        finally:
            context.close()
    finally:
        browser.close()


def _events(context: Any, page: Any) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    console_errors: list[str] = []
    page_errors: list[str] = []
    failures: list[dict[str, Any]] = []
    page.on(
        "console",
        lambda m: (
            _append(console_errors, sanitize_text_for_evidence(m.text[:16_384]), 500)
            if m.type == "error"
            else None
        ),
    )
    page.on(
        "pageerror",
        lambda error: _append(page_errors, sanitize_text_for_evidence(str(error)[:16_384]), 500),
    )
    context.on(
        "requestfailed",
        lambda request: _append(
            failures,
            {
                "url": sanitize_url_for_evidence(request.url),
                "resource_type": request.resource_type,
                "failure": sanitize_text_for_evidence(str(request.failure)[:16_384]),
            },
            1000,
        ),
    )
    return console_errors, page_errors, failures


def _page_result(
    context: Any,
    egress: BrowserEgress,
    url: str,
    *,
    timeout_ms: int,
    wait_until: str,
    started: float,
    width: int,
    height: int,
    include_screenshot: bool,
    full_page: bool,
    accessibility: bool,
) -> dict[str, Any]:
    page = context.new_page()
    console_errors, page_errors, failures = _events(context, page)
    response = page.goto(url, wait_until=wait_until, timeout=timeout_ms)
    final_url = validate_public_url(page.url)
    result = _capture(
        page,
        context,
        screenshot=include_screenshot,
        full_page=full_page,
        accessibility=accessibility,
    )
    egress.assert_budget()
    result.update(
        {
            "url": url,
            "final_url": final_url,
            "status_code": response.status if response else None,
            "console_errors": console_errors,
            "page_errors": page_errors,
            "failed_requests": failures,
            "render_ms": round((time.monotonic() - started) * 1000),
            "render_engine": "playwright-chromium",
            "viewport": {"width": width, "height": height},
            "network_policy": egress.evidence(),
        }
    )
    return result


def render_browser(
    url: str,
    *,
    timeout_ms: int = 30_000,
    wait_until: str = "networkidle",
    width: int = 1440,
    height: int = 900,
    include_screenshot: bool = False,
    full_page: bool = False,
    block_resource_types: tuple[str, ...] = (),
    user_agent: str = "World-Class-SEO-Render/1.0",
    accessibility: bool = False,
) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    if wait_until not in {"commit", "domcontentloaded", "load", "networkidle"}:
        raise ValueError("unsupported browser wait state")
    if "websocket" in block_resource_types:
        raise ValueError(
            "individual WebSocket blocking is unsupported; public-address egress is enforced"
        )
    safe_url = validate_public_url(url)
    started = time.monotonic()
    network_timeout = timeout_ms / 1000
    validate_egress_limits(timeout=network_timeout)
    with (
        sync_playwright() as playwright,
        BrowserEgress(timeout=network_timeout) as egress,
        _browser_context(
            playwright,
            egress,
            timeout_ms=timeout_ms,
            width=width,
            height=height,
            user_agent=user_agent,
            block=block_resource_types,
        ) as context,
    ):
        return _page_result(
            context,
            egress,
            safe_url,
            timeout_ms=timeout_ms,
            wait_until=wait_until,
            started=started,
            width=width,
            height=height,
            include_screenshot=include_screenshot,
            full_page=full_page,
            accessibility=accessibility,
        )
