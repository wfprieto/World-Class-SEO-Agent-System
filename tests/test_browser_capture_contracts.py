"""Offline SDK-contract characterization, not real Chromium/egress certification.

The fixture replaces Playwright and the socket-owning egress lifecycle only. URL
validation, route guards, evidence sanitizers, capture limits, and orchestration
remain production code. The tests deliberately work without Playwright installed.
"""

from __future__ import annotations

import json
import sys
from importlib.machinery import ModuleSpec
from types import ModuleType, SimpleNamespace

import pytest

from security import browser_capture


class FakeSdkLifecycle:
    """Records SDK/budget context-manager ownership without starting any process."""

    def __init__(self, contract, name, result):
        self.contract, self.name, self.result = contract, name, result

    def __enter__(self):
        self.contract.step(self.name + ".enter")
        return self.result

    def __exit__(self, exc_type, _exc, _traceback):
        self.contract.exit_errors[self.name] = exc_type
        self.contract.step(self.name + ".exit")


class FakeCaptureSdkContract:
    """Mutable, inspected SDK fixtures; no browser, resolver, proxy, or socket."""

    def __init__(self):
        self.events, self.options, self.exit_errors = [], {}, {}
        self.handlers = {"page": {}, "context": {}}
        self.failure_at = None
        self.html, self.text, self.title = "<html><body>Fixture</body></html>", "Fixture text", "Fixture title"
        self.body_count = 1
        self.image = b"\x89PNG\r\n\x1a\nSDK-fixture"
        self.dimensions = {"w": 1000, "h": 700}
        self.tree = {"nodes": [{"nodeId": "fixture-node"}]}
        self.final_url = "https://example.com/final?view=fixture"
        self.response = SimpleNamespace(status=207)
        self.console, self.page_errors, self.requests, self.routes = [], [], [], []
        self.route_handler = None
        self.proxy = {"server": "http://127.0.0.1:54321", "bypass": "<-loopback>",
                      "username": "fixture-user", "password": "fixture-proxy-password"}
        self.policy = {"fixture_only": True, "transport": "sdk-contract-fixture",
                       "requests": 7, "bytes": 321, "blocked_connections": 2}
        self.body = SimpleNamespace(
            count=lambda: self.step("body.count", result=self.body_count),
            inner_text=lambda **kw: self.step("body.inner_text", result=self.text, **kw),
        )
        self.session = SimpleNamespace(
            send=lambda command: self.step("cdp.send", result=self.tree, command=command),
            detach=lambda: self.step("cdp.detach"),
        )
        self.page = SimpleNamespace(
            url="https://example.com/initial", goto=self.goto,
            content=lambda: self.step("page.content", result=self.html),
            locator=self.locator, title=lambda: self.step("page.title", result=self.title),
            evaluate=lambda expression: self.step("page.evaluate", result=self.dimensions, expression=expression),
            screenshot=lambda **kw: self.step("page.screenshot", result=self.image, **kw),
            on=lambda event, callback: self.on("page", event, callback),
        )
        self.context = SimpleNamespace(
            set_default_timeout=lambda timeout: self.step("context.timeout", timeout=timeout),
            route=self.route, new_page=lambda: self.step("page.create", result=self.page),
            new_cdp_session=lambda page: self.step("cdp.create", result=self.session, page=page),
            on=lambda event, callback: self.on("context", event, callback),
            close=lambda: self.step("context.close"),
        )
        self.browser = SimpleNamespace(
            new_context=lambda **kw: self.step("context.create", result=self.context, **kw),
            close=lambda: self.step("browser.close"),
        )
        self.sdk = SimpleNamespace(chromium=SimpleNamespace(
            launch=lambda **kw: self.step("browser.launch", result=self.browser, **kw),
        ))
        self.egress = SimpleNamespace(
            proxy=self.proxy, assert_budget=lambda: self.step("egress.assert_budget"),
            evidence=lambda: self.step("egress.evidence", result=dict(self.policy)),
        )

    def step(self, name, *, result=None, **options):
        self.events.append(name)
        self.options[name] = options
        if self.failure_at == name:
            error = ValueError if name == "egress.assert_budget" else RuntimeError
            raise error("SDK-contract fixture failure: " + name)
        return result

    def on(self, owner, event, callback):
        self.step(owner + ".on." + event)
        self.handlers[owner][event] = callback

    def route(self, pattern, callback):
        self.step("context.route", pattern=pattern)
        self.route_handler = callback

    def locator(self, selector):
        self.step("page.locator", selector=selector)
        assert selector == "body"
        return self.body

    def goto(self, url, **options):
        self.step("page.goto", url=url, **options)
        self.page.url = self.final_url
        for event, values in (("console", self.console), ("pageerror", self.page_errors)):
            for value in values:
                self.handlers["page"][event](value)
        for request in self.requests:
            self.handlers["context"]["requestfailed"](request)
        for route in self.routes:
            self.route_handler(route)
        return self.response

    def egress_factory(self, **options):
        self.step("egress.create", **options)
        return FakeSdkLifecycle(self, "egress", self.egress)

    def sdk_factory(self):
        self.step("sdk.create")
        return FakeSdkLifecycle(self, "sdk", self.sdk)


@pytest.fixture
def sdk_contract(monkeypatch):
    contract = FakeCaptureSdkContract()
    package = ModuleType("playwright")
    package.__path__ = []
    package.__spec__ = ModuleSpec("playwright", loader=None, is_package=True)
    sdk = ModuleType("playwright.sync_api")
    sdk.__spec__ = ModuleSpec("playwright.sync_api", loader=None)
    sdk.sync_playwright = contract.sdk_factory
    package.sync_api = sdk
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sdk)
    monkeypatch.setattr(browser_capture, "BrowserEgress", contract.egress_factory)
    return contract


@pytest.mark.parametrize("timeout_ms", [5000, 30_000])
def test_render_enforces_sdk_isolation_options_before_navigation(sdk_contract, timeout_ms):
    result = browser_capture.render_browser(
        "HTTPS://Example.COM:443/start?view=fixture#fragment", timeout_ms=timeout_ms,
        wait_until="domcontentloaded", width=1000, height=700, user_agent="SDK-contract-UA",
        include_screenshot=True, full_page=True, accessibility=True,
    )
    state = sdk_contract
    assert state.options["egress.create"] == {"timeout": timeout_ms / 1000}
    launch = state.options["browser.launch"]
    assert launch["headless"] is True and launch["timeout"] == timeout_ms
    assert launch["proxy"] == state.proxy
    assert set(launch["args"]) >= {
        "--proxy-bypass-list=<-loopback>", "--disable-quic",
        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
    }
    assert state.options["context.create"] == {
        "viewport": {"width": 1000, "height": 700}, "user_agent": "SDK-contract-UA",
        "ignore_https_errors": False, "java_script_enabled": True,
        "service_workers": "block", "accept_downloads": False,
    }
    assert state.events.count("context.create") == 1
    assert state.options["context.timeout"] == {"timeout": min(timeout_ms, 10_000)}
    assert state.options["context.route"] == {"pattern": "**/*"}
    assert state.options["page.goto"] == {
        "url": "https://example.com/start?view=fixture", "wait_until": "domcontentloaded", "timeout": timeout_ms,
    }
    for event in ("context.route", "page.on.console", "page.on.pageerror", "context.on.requestfailed"):
        assert state.events.index(event) < state.events.index("page.goto")
    assert state.events.index("cdp.detach") < state.events.index("egress.assert_budget")
    assert state.events[-4:] == ["context.close", "browser.close", "sdk.exit", "egress.exit"]
    assert state.exit_errors == {"sdk": None, "egress": None}
    assert result["screenshot_bytes"] == state.image and result["accessibility_tree"] == state.tree


@pytest.mark.parametrize(("status", "counts"), [
    (207, {"requests": 7, "bytes": 321, "blocked_connections": 2}),
    (503, {"requests": 12, "bytes": 4096, "blocked_connections": 3}),
    (None, {"requests": 0, "bytes": 0, "blocked_connections": 0}),
])
def test_render_returns_fixture_status_policy_and_captured_outputs(sdk_contract, status, counts):
    sdk_contract.response = SimpleNamespace(status=status) if status is not None else None
    sdk_contract.policy.update(counts)
    result = browser_capture.render_browser("https://example.com/start")
    assert result["status_code"] == status
    assert result["html"] == sdk_contract.html and result["text"] == sdk_contract.text
    assert result["title"] == sdk_contract.title
    assert result["url"] == "https://example.com/start" and result["final_url"] == sdk_contract.final_url
    assert result["network_policy"] == sdk_contract.policy
    assert result["render_engine"] == "playwright-chromium"
    assert result["viewport"] == {"width": 1440, "height": 900}
    assert isinstance(result["render_ms"], int) and result["render_ms"] >= 0
    assert "fixture-proxy-password" not in json.dumps(result)
    assert sdk_contract.events.index("page.content") < sdk_contract.events.index("egress.assert_budget")
    assert sdk_contract.events.index("egress.assert_budget") < sdk_contract.events.index("egress.evidence")


@pytest.mark.parametrize("options", [{"wait_until": "unsupported"}, {"block_resource_types": ("websocket",)}])
def test_unsupported_browser_modes_fail_before_sdk_or_egress_start(sdk_contract, options):
    with pytest.raises(ValueError, match="unsupported"):
        browser_capture.render_browser("https://example.com", **options)
    assert sdk_contract.events == []


def test_private_initial_url_is_rejected_before_any_sdk_lifecycle(sdk_contract):
    with pytest.raises(ValueError, match="non-public"):
        browser_capture.render_browser("http://127.0.0.1/private")
    assert sdk_contract.events == []


def test_private_final_url_cannot_produce_successful_capture(sdk_contract):
    sdk_contract.final_url = "http://127.0.0.1/private"
    with pytest.raises(ValueError, match="non-public"):
        browser_capture.render_browser("https://example.com")
    assert "page.content" not in sdk_contract.events and "egress.evidence" not in sdk_contract.events
    assert sdk_contract.events[-4:] == ["context.close", "browser.close", "sdk.exit", "egress.exit"]


@pytest.mark.parametrize("stage", [
    "sdk.create", "sdk.enter", "browser.launch", "context.create", "context.route",
    "page.create", "page.goto", "page.content", "body.inner_text", "page.screenshot",
    "cdp.create", "cdp.send", "egress.assert_budget", "context.close", "browser.close",
])
def test_sdk_failures_propagate_and_release_every_acquired_owner(sdk_contract, stage):
    sdk_contract.failure_at = stage
    with pytest.raises((ValueError, RuntimeError), match="SDK-contract fixture failure"):
        browser_capture.render_browser("https://example.com", include_screenshot=True,
                                       full_page=True, accessibility=True)
    events = sdk_contract.events
    assert events[-1] == "egress.exit"
    if stage not in {"sdk.create", "sdk.enter"}:
        assert "sdk.exit" in events
    if stage not in {"sdk.create", "sdk.enter", "browser.launch"}:
        assert "browser.close" in events
    if stage not in {"sdk.create", "sdk.enter", "browser.launch", "context.create"}:
        assert "context.close" in events
        assert events.index("context.close") < events.index("browser.close")
    if stage == "cdp.send":
        assert events.index("cdp.detach") < events.index("context.close")
    if stage == "egress.assert_budget":
        assert "egress.evidence" not in events


def test_browser_diagnostic_logs_are_bounded_and_sanitized(sdk_contract):
    message = "token=console-sensitive https://user:password@example.com/path?token=query-sensitive#private " + "x" * 17_000 + "TRUNCATED_TAIL"
    sdk_contract.console = [SimpleNamespace(type="info", text="not-an-error")]
    sdk_contract.console += [SimpleNamespace(type="error", text=message)] * 500
    sdk_contract.console += [SimpleNamespace(type="error", text="overflow-console")]
    sdk_contract.page_errors = [RuntimeError(message)] * 500 + [RuntimeError("overflow-page")]
    failed = SimpleNamespace(url="https://user:password@example.com/resource?token=url-sensitive#private",
                             resource_type="fetch", failure="token=failure-sensitive " + "x" * 17_000 + "TRUNCATED_TAIL")
    sdk_contract.requests = [failed] * 1000 + [SimpleNamespace(url="https://example.com/overflow", resource_type="fetch", failure="overflow-request")]
    result = browser_capture.render_browser("https://example.com")
    assert len(result["console_errors"]) == len(result["page_errors"]) == 500
    assert len(result["failed_requests"]) == 1000
    assert result["failed_requests"][0]["url"] == "https://example.com/resource"
    sample = result["console_errors"][:1] + result["page_errors"][:1] + result["failed_requests"][:1]
    serialized = json.dumps(sample)
    assert "[REDACTED]" in serialized
    assert all(marker not in serialized for marker in (
        "console-sensitive", "query-sensitive", "url-sensitive", "failure-sensitive", "TRUNCATED_TAIL", "user:password",
    ))
    assert len(result["console_errors"][0]) <= 16_384
    assert len(result["page_errors"][0]) <= 16_384
    assert len(result["failed_requests"][0]["failure"]) <= 16_384
    assert "overflow-console" not in result["console_errors"]
    assert "overflow-page" not in result["page_errors"]
    assert result["failed_requests"][-1]["url"] != "https://example.com/overflow"


@pytest.mark.parametrize(("url", "resource", "blocked", "expected"), [
    ("https://example.com/app.js", "script", (), "continue"),
    ("https://example.com/picture.png", "image", ("image",), "abort"),
    ("http://127.0.0.1/private", "fetch", (), "abort"),
    ("data:image/png;base64,AAAA", "image", ("image",), "continue"),
])
def test_registered_sdk_route_uses_real_admission_and_resource_guards(sdk_contract, url, resource, blocked, expected):
    decisions = []
    sdk_contract.routes = [SimpleNamespace(
        request=SimpleNamespace(url=url, resource_type=resource),
        continue_=lambda: decisions.append("continue"), abort=lambda: decisions.append("abort"),
    )]
    browser_capture.render_browser("https://example.com", block_resource_types=blocked)
    assert decisions == [expected]


def test_capture_no_body_or_optional_media_does_not_fabricate_outputs(sdk_contract):
    sdk_contract.body_count = 0
    result = browser_capture._capture(sdk_contract.page, sdk_contract.context,
                                     screenshot=False, full_page=True, accessibility=False)
    assert result == {"html": sdk_contract.html, "title": sdk_contract.title, "text": "", "screenshot_bytes": None}
    assert not {"body.inner_text", "page.evaluate", "page.screenshot", "cdp.create"} & set(sdk_contract.events)


@pytest.mark.parametrize("field", ["html", "text"])
def test_capture_rejects_utf8_output_ceiling_not_only_character_count(sdk_contract, field):
    setattr(sdk_contract, field, "é" * 6_000_001)
    with pytest.raises(ValueError, match="12 MB output ceiling"):
        browser_capture._capture(sdk_contract.page, sdk_contract.context,
                                 screenshot=False, full_page=False, accessibility=False)
    assert "page.screenshot" not in sdk_contract.events


def test_capture_fullpage_pixel_ceiling_precedes_screenshot_allocation(sdk_contract):
    sdk_contract.dimensions = {"w": 10_001, "h": 5000}
    with pytest.raises(ValueError, match="50 million pixel"):
        browser_capture._capture(sdk_contract.page, sdk_contract.context,
                                 screenshot=True, full_page=True, accessibility=False)
    assert "page.screenshot" not in sdk_contract.events


def test_capture_rejects_oversized_screenshot_and_skips_ax_request(sdk_contract):
    sdk_contract.image = b"x" * 25_000_001
    with pytest.raises(ValueError, match="25 MB output ceiling"):
        browser_capture._capture(sdk_contract.page, sdk_contract.context,
                                 screenshot=True, full_page=False, accessibility=True)
    assert "cdp.create" not in sdk_contract.events


def test_capture_rejects_oversized_ax_tree_and_always_detaches(sdk_contract):
    sdk_contract.tree = {"nodes": [{}] * 20_001}
    with pytest.raises(ValueError, match="20000 node"):
        browser_capture._capture(sdk_contract.page, sdk_contract.context,
                                 screenshot=False, full_page=False, accessibility=True)
    assert sdk_contract.events[-1] == "cdp.detach"


@pytest.mark.parametrize("field", ["html", "text", "image", "tree", "dimensions"])
def test_capture_accepts_exact_output_ceiling_and_preserves_sdk_capture_options(sdk_contract, field):
    boundaries = {"html": lambda: "x" * 12_000_000, "text": lambda: "x" * 12_000_000,
                  "image": lambda: b"x" * 25_000_000, "tree": lambda: {"nodes": [{}] * 20_000},
                  "dimensions": lambda: {"w": 10_000, "h": 5000}}
    setattr(sdk_contract, field, boundaries[field]())
    result = browser_capture._capture(sdk_contract.page, sdk_contract.context,
                                     screenshot=True, full_page=True, accessibility=True)
    assert result["screenshot_bytes"] == sdk_contract.image and result["accessibility_tree"] == sdk_contract.tree
    assert sdk_contract.options["body.inner_text"] == {"timeout": 5000}
    assert sdk_contract.options["page.screenshot"] == {
        "full_page": True, "type": "png", "animations": "disabled", "timeout": 10_000,
    }
    assert sdk_contract.options["cdp.send"] == {"command": "Accessibility.getFullAXTree"}
    assert sdk_contract.events[-1] == "cdp.detach"
