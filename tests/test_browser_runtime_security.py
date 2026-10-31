"""Opt-in real Chromium proofs, exclusively against controlled loopback fixtures.

The test boundary maps vetted public numeric sockets to the local fixture. No
production URL policy is weakened and no external/private host is contacted.
Run with WCSEO_BROWSER_SECURITY=1 after installing the locked browser runtime.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from adapters import rendered_page
from integrations.technical.browser import PlaywrightRenderer, RenderedPageService
from security import url_safety
from seoctl.composition import build_raw_fetch


@pytest.fixture(autouse=True)
def require_browser_runtime(request):
    if (
        not request.config.getoption("--browser-security")
        and os.environ.get("WCSEO_BROWSER_SECURITY") != "1"
    ):
        pytest.skip("opt-in actual Chromium security certification")


def _private_fixture_server(forbidden: list[str]) -> ThreadingHTTPServer:
    class PrivateHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            forbidden.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"forbidden fixture")

        def log_message(self, *args):
            pass

    class PrivateServer(ThreadingHTTPServer):
        def get_request(self):
            connection = super().get_request()
            forbidden.append("tcp-connection")
            return connection

    private = PrivateServer(("127.0.0.1", 0), PrivateHandler)
    return private


def _write_fixture_websocket(handler: BaseHTTPRequestHandler) -> None:
    key = handler.headers["Sec-WebSocket-Key"]
    accept = base64.b64encode(
        hashlib.sha1(
            (key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode(),
            usedforsecurity=False,
        ).digest()
    ).decode()
    handler.send_response(101)
    handler.send_header("Upgrade", "websocket")
    handler.send_header("Connection", "Upgrade")
    handler.send_header("Sec-WebSocket-Accept", accept)
    handler.end_headers()
    message = b"public-websocket-active"
    handler.wfile.write(bytes([0x81, len(message)]) + message)
    handler.connection.settimeout(5)
    handler.rfile.read(1)
    return


def _fixture_page_body(path: str, private_url: str) -> bytes:
    body = b'<html><title>Fixture</title><body><h1 id="ready">Loading</h1><script>document.querySelector("h1").textContent="Rendered fixture"</script></body></html>'
    if path == "/post":
        body = b'<h1>Loading</h1><script>document.cookie="fixture=kept";fetch("/echo",{method:"POST",body:"fixture-body"}).then(r=>r.text()).then(t=>document.querySelector("h1").textContent=t)</script>'
    if path == "/spa":
        body = b'<div id="root"></div><script>document.querySelector("#root").innerHTML="<h1>Hydrated fixture</h1>"</script>'
    if path == "/worker.js":
        body = f'fetch({json.dumps(private_url)}).catch(()=>{{}});fetch("/worker-ok").then(()=>postMessage("worker-active"))'.encode()
    if path == "/threats":
        body = f"""<h1>Loading</h1><img src="/resource-redirect"><iframe src="/resource-redirect"></iframe><script>
window.open({json.dumps(private_url)});
fetch({json.dumps(private_url)}).catch(()=>{{}});
try{{new WebSocket({json.dumps(private_url.replace("http://", "ws://"))});}}catch(e){{}}
try{{new WebSocket({json.dumps(private_url.replace("http://", "wss://"))});}}catch(e){{}}
let socket=new WebSocket(location.origin.replace("http://","ws://")+"/websocket");socket.onmessage=e=>document.body.dataset.ws=e.data;
let worker=new Worker("/worker.js");worker.onmessage=e=>document.querySelector("h1").textContent=e.data;
if(navigator.serviceWorker)navigator.serviceWorker.register("/sw.js").catch(()=>{{}});
</script>""".encode()
    return body


def _write_fixture_page(handler: BaseHTTPRequestHandler, private_url: str) -> None:
    body = _fixture_page_body(handler.path, private_url)
    handler.send_response(200)
    handler.send_header(
        "Content-Type",
        "application/javascript" if handler.path.endswith(".js") else "text/html",
    )
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _public_fixture_server(
    requests: list[tuple[str, str | None]], private_url: str
) -> ThreadingHTTPServer:
    class PublicHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append(("POST:" + body.decode(), self.headers.get("Cookie")))
            self.send_response(200)
            self.send_header("Content-Length", "14")
            self.end_headers()
            self.wfile.write(b"POST preserved")

        def do_GET(self):
            requests.append((self.path, self.headers.get("Host")))
            if self.path == "/fqdn-redirect":
                self.send_response(302)
                self.send_header("Location", f"http://public.test.:{self.server.server_port}/final")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path == "/websocket":
                _write_fixture_websocket(self)
                return
            if self.path in {"/redirect", "/public-redirect"}:
                self.send_response(302)
                self.send_header("Location", private_url if self.path == "/redirect" else "/final")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path == "/resource-redirect":
                self.send_response(302)
                self.send_header("Location", private_url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            _write_fixture_page(self, private_url)

        def log_message(self, *args):
            pass

    public = ThreadingHTTPServer(("127.0.0.1", 0), PublicHandler)
    return public


def _patch_fixture_connect(
    monkeypatch: pytest.MonkeyPatch, public: ThreadingHTTPServer, private: ThreadingHTTPServer
) -> None:
    monkeypatch.setattr(
        url_safety,
        "ALLOWED_TARGET_PORTS",
        frozenset({80, 443, public.server_port, private.server_port}),
    )
    original_connect = socket.socket.connect

    def fixture_connect(sock, address):
        if address[0] == "93.184.216.34":
            assert address[1] == public.server_port
            return original_connect(sock, ("127.0.0.1", public.server_port))
        return original_connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", fixture_connect)


def _patch_fixture_browser(monkeypatch, BrowserType, public: ThreadingHTTPServer) -> None:
    original_launch = BrowserType.launch

    def fixture_launch(browser_type, **kwargs):
        kwargs["args"] = [*kwargs.get("args", []), "--host-resolver-rules=MAP *.test 127.0.0.1"]
        kwargs["args"].append(
            f"--unsafely-treat-insecure-origin-as-secure=http://public.test:{public.server_port}"
        )
        return original_launch(browser_type, **kwargs)

    monkeypatch.setattr(BrowserType, "launch", fixture_launch)


@pytest.fixture
def browser_site(monkeypatch):
    from playwright.sync_api import BrowserType

    requests = []
    forbidden = []

    private = _private_fixture_server(forbidden)
    private_url = f"http://127.0.0.1:{private.server_port}/sentinel"

    public = _public_fixture_server(requests, private_url)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True) for server in (public, private)
    ]
    for thread in threads:
        thread.start()
    _patch_fixture_connect(monkeypatch, public, private)
    _patch_fixture_browser(monkeypatch, BrowserType, public)
    try:
        yield f"http://public.test:{public.server_port}", requests, forbidden
    finally:
        for server in (public, private):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=2)


def test_real_browser_blocks_private_redirect_before_connection(browser_site):
    from playwright.sync_api import Error as PlaywrightError

    url, requests, forbidden = browser_site
    renderer = PlaywrightRenderer()
    assert renderer.health().state == "AVAILABLE"
    with pytest.raises(PlaywrightError, match="ERR_EMPTY_RESPONSE"):
        renderer.render(url + "/redirect", timeout_ms=5_000)
    assert any(path == "/redirect" for path, _ in requests)
    assert forbidden == []


def test_real_browser_preserves_public_redirect_and_javascript(browser_site):
    url, requests, forbidden = browser_site
    result = PlaywrightRenderer().render(url + "/public-redirect", timeout_ms=5_000)
    assert result["status_code"] == 200
    assert result["final_url"] == url + "/final"
    assert "Rendered fixture" in result["text"]
    assert [path for path, _ in requests] == ["/public-redirect", "/final"]
    assert all(host == url.removeprefix("http://") for _, host in requests)
    assert forbidden == []


def test_real_browser_preserves_post_body_and_cookies(browser_site):
    url, requests, forbidden = browser_site
    result = PlaywrightRenderer().render(url + "/post", timeout_ms=3_000)
    assert "POST preserved" in result["text"]
    assert ("POST:fixture-body", "fixture=kept") in requests
    assert forbidden == []


def test_real_browser_preserves_terminal_dot_public_redirect(browser_site):
    url, requests, forbidden = browser_site
    result = PlaywrightRenderer().render(url + "/fqdn-redirect", timeout_ms=5_000)
    assert result["status_code"] == 200
    assert result["final_url"] == url + "/final"
    assert ("/final", url.removeprefix("http://").replace(".test:", ".test.:")) in requests
    assert forbidden == []


def test_real_browser_blocks_subresource_popup_worker_and_websocket_egress(browser_site):
    url, requests, forbidden = browser_site
    result = PlaywrightRenderer().render(url + "/threats", timeout_ms=5_000)
    assert "worker-active" in result["text"]
    assert any(path == "/worker-ok" for path, _ in requests)
    assert not any(path == "/sw.js" for path, _ in requests)
    assert result["network_policy"]["service_workers"] == "blocked"
    assert result["network_policy"]["websockets"] == "public-address-egress"
    assert "public-websocket-active" in result["html"]
    assert forbidden == []


def test_real_legacy_renderer_captures_accessibility(browser_site):
    url, _, forbidden = browser_site
    result = rendered_page.playwright_render(url + "/final")
    assert result["status_code"] == 200
    assert "Rendered fixture" in result["content"]
    nodes = result["accessibility_tree"]["nodes"]
    assert any(node.get("name", {}).get("value") == "Rendered fixture" for node in nodes)
    assert result["network_policy"]["transport"] == "vetted-numeric-egress"
    assert forbidden == []


@pytest.mark.parametrize("viewport", [(390, 844), (1440, 900)])
def test_real_screenshot_service_writes_valid_responsive_png(browser_site, tmp_path, viewport):
    url, _, forbidden = browser_site
    output = tmp_path / "fixture.png"
    result = RenderedPageService().screenshot(
        url + "/final", output=output, width=viewport[0], height=viewport[1], timeout_ms=5_000
    )
    assert result.status == "ok"
    assert result.data["evidence"]["screenshot"] == "VERIFIED"
    png = output.read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", png[16:24]) == viewport
    assert forbidden == []


@pytest.mark.parametrize("mode", ["auto", "always", "never"])
def test_real_legacy_fetch_modes_preserve_truthful_evidence(browser_site, mode):
    url, _, forbidden = browser_site
    result = rendered_page.fetch(url + "/spa", mode=mode, raw_fetch=build_raw_fetch())
    assert result.status == "ok"
    assert result.data["mode_used"] == ("raw" if mode == "never" else "rendered")
    assert result.data["evidence"]["rendered"] == ("Not Run" if mode == "never" else "Verified")
    assert forbidden == []


@pytest.mark.parametrize("mode", ["auto", "always", "never"])
def test_real_legacy_fetch_modes_never_disclose_private_redirect(browser_site, mode):
    url, requests, forbidden = browser_site
    result = rendered_page.fetch(url + "/redirect", mode=mode, raw_fetch=build_raw_fetch())
    assert result.status == "partial"
    assert result.data["evidence"]["rendered"] == "Not Run"
    assert any(path == "/redirect" for path, _ in requests)
    assert "forbidden fixture" not in json.dumps(result.data)
    assert forbidden == []


def test_real_missing_optional_renderer_returns_raw_partial(browser_site, monkeypatch):
    url, _, forbidden = browser_site
    monkeypatch.setattr(rendered_page, "_playwright_available", lambda: False)
    result = rendered_page.fetch(url + "/spa", mode="always", raw_fetch=build_raw_fetch())
    assert result.status == "partial"
    assert result.data["raw_content"]
    assert result.data["evidence"]["rendered"] == "Not Run"
    assert any("dependency_missing" in warning for warning in result.warnings)
    assert forbidden == []


def test_real_browser_dns_rebinding_is_blocked_before_socket(browser_site, monkeypatch):
    from playwright.sync_api import Error as PlaywrightError

    url, requests, forbidden = browser_site
    original = socket.getaddrinfo
    calls = []

    def rebinding(host, port, *args, **kwargs):
        if host == "public.test":
            calls.append(host)
            if len(calls) > 3:
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", rebinding)
    with pytest.raises(PlaywrightError, match="ERR_EMPTY_RESPONSE"):
        PlaywrightRenderer().render(url + "/final", timeout_ms=5_000)
    assert len(calls) >= 4
    assert requests == []
    assert forbidden == []
