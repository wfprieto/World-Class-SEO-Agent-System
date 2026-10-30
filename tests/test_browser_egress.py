"""Controlled socket and framing proofs for the authenticated browser proxy."""

from __future__ import annotations

import io
import socket
import threading
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from security import browser_proxy, url_safety
from security.browser_proxy import BrowserEgress

PUBLIC_ADDRESS = "93.184.216.34"


def _exchange(proxy, request):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(("127.0.0.1", proxy.server_port))
        client.sendall(request)
        response = bytearray()
        while True:
            try:
                chunk = client.recv(65_536)
            except ConnectionResetError:
                break
            if not chunk:
                break
            response.extend(chunk)
        return bytes(response)


def _request(proxy, *, method="GET", target="http://public.test/", headers=(), body=b""):
    authority = target.removeprefix("http://").split("/", 1)[0]
    lines = [f"{method} {target} HTTP/1.1", f"Host: {authority}",
             f"Proxy-Authorization: {proxy.authorization}", *headers]
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body


def _wait_for(predicate):
    deadline = time.monotonic() + 2
    while not predicate() and time.monotonic() < deadline:
        threading.Event().wait(0.01)
    assert predicate(), "proxy fixture did not reach its bounded terminal state"


def _read_fixture_chunked(stream):
    body, framing = bytearray(), bytearray()
    while True:
        line = stream.readline(8193)
        if not line.endswith(b"\r\n"):
            raise ValueError("incomplete fixture chunk line")
        framing.extend(line)
        size = int(line.strip(), 16)
        if not size:
            while True:
                trailer = stream.readline(8193)
                if not trailer:
                    raise ValueError("incomplete fixture trailer")
                framing.extend(trailer)
                if trailer == b"\r\n":
                    return bytes(body), bytes(framing)
        chunk = stream.read(size)
        body.extend(chunk)
        framing.extend(chunk + stream.read(2))


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        self._respond()

    def do_GET(self):
        self._respond()

    def _respond(self):
        self.connection.settimeout(2)
        try:
            if self.headers.get("Transfer-Encoding") == "chunked":
                body, framing = _read_fixture_chunked(self.rfile)
            else:
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                framing = b""
        except (OSError, ValueError):
            return
        self.server.observed.append({"method": self.command, "path": self.path,
            "headers": dict(self.headers), "body": body, "framing": framing})
        payload = b"upstream-ok" if self.path != "/large" else b"x" * 4096
        self.send_response(200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        with suppress(OSError):
            self.wfile.write(payload)

    def log_message(self, *_args):
        pass


class _FixtureServer(ThreadingHTTPServer):
    daemon_threads = True

    def get_request(self):
        client, address = super().get_request()
        self.accepted.append(client)
        return client, address


@pytest.fixture
def public_http(monkeypatch):
    observed, attempts, accepted = [], [], []
    server = _FixtureServer(("127.0.0.1", 0), _FixtureHandler)
    server.observed, server.accepted = observed, accepted
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    monkeypatch.setattr(url_safety, "ALLOWED_TARGET_PORTS",
                        url_safety.ALLOWED_TARGET_PORTS | {server.server_port})
    real_connect = socket.socket.connect

    def fixture_connect(sock, address):
        if address[0] == "127.0.0.1":
            return real_connect(sock, address)  # Explicit raw proxy-fixture clients only.
        attempts.append(address)
        if address == (PUBLIC_ADDRESS, server.server_port):
            return real_connect(sock, ("127.0.0.1", server.server_port))
        raise OSError("proxy fixture forbids unplanned network destinations")

    monkeypatch.setattr(socket.socket, "connect", fixture_connect)
    try:
        yield f"http://public.test:{server.server_port}", observed, attempts, accepted
    finally:
        for client in accepted:
            with suppress(OSError):
                client.shutdown(socket.SHUT_RDWR)
            client.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


@pytest.mark.parametrize("method,target", [("GET", "http://public.test/"),
                                           ("CONNECT", "public.test:443")])
@pytest.mark.parametrize("auth", [(), ("Proxy-Authorization: Basic invalid",),
                                  ("Proxy-Authorization: Basic invalid",) * 2])
def test_proxy_requires_one_valid_authorization_before_upstream_dial(monkeypatch, method, target, auth):
    dials = []

    def never_dial(*args, **kwargs):
        dials.append((args, kwargs))
        raise OSError("test prohibits upstream dialing")

    monkeypatch.setattr(browser_proxy, "public_connection", never_dial)
    with BrowserEgress(timeout=3) as proxy:
        request = ("\r\n".join([f"{method} {target} HTTP/1.1", "Host: public.test", *auth])
                   + "\r\n\r\n").encode()
        response = _exchange(proxy, request)
        assert b" 407 " in response.split(b"\r\n", 1)[0]
        assert b"Proxy-Authenticate: Basic" in response
        assert proxy.requests_seen == 0
    assert dials == []


def test_duplicate_valid_or_other_context_credentials_are_rejected(monkeypatch):
    dials = []
    monkeypatch.setattr(browser_proxy, "public_connection", lambda *args, **_: dials.append(args))
    with BrowserEgress(timeout=3) as first, BrowserEgress(timeout=3) as second:
        assert first.authorization != second.authorization
        duplicate = _request(first, headers=(f"Proxy-Authorization: {first.authorization}",))
        assert b" 407 " in _exchange(first, duplicate).split(b"\r\n", 1)[0]
        foreign = _request(first)
        assert b" 407 " in _exchange(second, foreign).split(b"\r\n", 1)[0]
    assert dials == []


@pytest.mark.parametrize("method,target,headers", [
    ("GET", "http://127.0.0.1/private", ()),
    ("GET", "http://169.254.169.254/latest/", ()),
    ("GET", "http://[::1]/private", ()),
    ("GET", "http://user:pass@public.test/", ()),
    ("GET", "http://public.test:8080/", ()),
    ("GET", "http://public.test/", ("Host: other.test",)),
    ("GET", "http://public.test/", ("Upgrade: websocket",)),
    ("GET", "http://public.test/", ("Content-Length: 0", "Content-Length: 0")),
    ("GET", "http://public.test/", ("Transfer-Encoding: chunked", "Content-Length: 0")),
    ("CONNECT", "127.0.0.1:443", ()),
    ("CONNECT", "[::1]:443", ()),
    ("CONNECT", "public.test:443/path", ()),
    ("CONNECT", "public.test:443@other.test", ()),
])
def test_private_malformed_and_ambiguous_targets_fail_before_dial(monkeypatch, method, target, headers):
    dials = []

    def never_dial(*args, **kwargs):
        dials.append((args, kwargs))
        raise OSError("test prohibits upstream dialing")

    monkeypatch.setattr(browser_proxy, "public_connection", never_dial)
    with BrowserEgress(timeout=3) as proxy:
        assert _exchange(proxy, _request(proxy, method=method, target=target, headers=headers)) == b""
        _wait_for(lambda: proxy.blocked_requests == 1)
    assert dials == []


@pytest.mark.parametrize("headers", [
    ("Content-Length: -1",),
    ("Content-Length: invalid",),
    ("Transfer-Encoding: gzip",),
    ("Transfer-Encoding: chunked", "Transfer-Encoding: chunked"),
])
def test_invalid_body_framing_is_rejected_before_upstream_dial(monkeypatch, headers):
    dials = []

    def never_dial(*args, **kwargs):
        dials.append((args, kwargs))
        raise OSError("test prohibits upstream dialing")

    monkeypatch.setattr(browser_proxy, "public_connection", never_dial)
    with BrowserEgress(timeout=3) as proxy:
        _exchange(proxy, _request(proxy, method="POST", headers=headers))
        _wait_for(lambda: proxy.blocked_requests == 1)
    assert dials == [], "invalid framing must be rejected before an upstream sees headers"


@pytest.mark.parametrize("chunked", [False, True])
def test_actual_http_post_preserves_body_host_and_strips_proxy_headers(public_http, chunked):
    url, observed, attempts, _ = public_http
    body = b"3\r\nabc\r\n2\r\nde\r\n0\r\nX-Trailer: fixture\r\n\r\n" if chunked else b"abcde"
    framing = "Transfer-Encoding: chunked" if chunked else "Content-Length: 5"
    with BrowserEgress(timeout=3) as proxy:
        response = _exchange(proxy, _request(proxy, method="POST", target=url + "/echo",
            headers=(framing, "Proxy-Connection: keep-alive", "Connection: X-Hop", "X-Hop: remove"),
            body=body))
        assert response.endswith(b"upstream-ok")
        assert b" 200 " in response.split(b"\r\n", 1)[0]
    assert len(observed) == 1
    assert observed[0]["method"] == "POST"
    assert observed[0]["path"] == "/echo"
    assert observed[0]["body"] == b"abcde"
    assert observed[0]["headers"]["Host"] == url.removeprefix("http://")
    assert observed[0]["headers"]["Connection"] == "close"
    assert not {"proxy-authorization", "proxy-connection", "x-hop"} & {
        key.lower() for key in observed[0]["headers"]
    }
    assert observed[0]["framing"] == (body if chunked else b"")
    assert attempts == [(PUBLIC_ADDRESS, int(url.rsplit(":", 1)[1]))]


def test_actual_public_websocket_upgrade_preserves_required_upstream_headers(public_http):
    url, observed, attempts, _ = public_http
    with BrowserEgress(timeout=3) as proxy:
        _exchange(proxy, _request(proxy, target=url + "/upgrade", headers=(
            "Upgrade: websocket", "Connection: Upgrade", "Sec-WebSocket-Version: 13",
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==",
        )))
    assert len(observed) == len(attempts) == 1
    assert observed[0]["headers"].get("Upgrade", "").lower() == "websocket"
    assert observed[0]["headers"]["Connection"].lower() == "upgrade"
    assert observed[0]["headers"]["Sec-WebSocket-Version"] == "13"
    assert observed[0]["headers"]["Sec-WebSocket-Key"] == "dGhlIHNhbXBsZSBub25jZQ=="
    assert "Proxy-Authorization" not in observed[0]["headers"]


def test_request_ceiling_blocks_second_authenticated_request(public_http):
    url, observed, attempts, _ = public_http
    with BrowserEgress(timeout=3, max_requests=1) as proxy:
        assert _exchange(proxy, _request(proxy, target=url + "/one")).endswith(b"upstream-ok")
        assert _exchange(proxy, _request(proxy, target=url + "/two")) == b""
        assert proxy.requests_seen == 2
        with pytest.raises(ValueError, match="request limit"):
            proxy.assert_budget()
    assert len(observed) == len(attempts) == 1


def test_response_byte_ceiling_fails_closed(public_http):
    url, observed, _, _ = public_http
    with BrowserEgress(timeout=3, max_bytes=256) as proxy:
        response = _exchange(proxy, _request(proxy, target=url + "/large"))
        assert b"x" * 4096 not in response
        assert proxy.bytes_seen > proxy.max_bytes
        with pytest.raises(ValueError, match="byte limit"):
            proxy.assert_budget()
    assert len(observed) == 1


def test_oversized_request_body_is_not_forwarded(public_http):
    url, observed, attempts, _ = public_http
    with BrowserEgress(timeout=3, max_bytes=256) as proxy:
        response = _exchange(proxy, _request(proxy, method="POST", target=url + "/echo",
            headers=("Content-Length: 1024",), body=b"x" * 1024))
        assert response == b""
        _wait_for(lambda: proxy.blocked_requests == 1)
    assert observed == []
    assert attempts == []


def test_request_headers_and_body_share_one_byte_budget(public_http):
    url, observed, _, _ = public_http
    with BrowserEgress(timeout=3, max_bytes=256) as proxy:
        response = _exchange(proxy, _request(proxy, method="POST", target=url + "/echo",
            headers=("Content-Length: 220",), body=b"x" * 220))
        assert response == b""
        with pytest.raises(ValueError, match="byte limit"):
            proxy.assert_budget()
    _wait_for(lambda: bool(observed))
    assert observed[0]["body"] == b""


@pytest.mark.parametrize("wire", [
    b"+5\r\nabcde\r\n0\r\n\r\n", b"0x5\r\nabcde\r\n0\r\n\r\n",
    b"-1\r\n", b"invalid\r\n", b"5\nabcde\r\n0\r\n\r\n",
    b"5\r\nabcdeXX0\r\n\r\n", b"0\r\nX-Trailer: incomplete",
])
def test_chunked_parser_rejects_non_rfc_or_incomplete_framing(wire):
    sent = []
    handler = object.__new__(browser_proxy._Handler)
    handler.rfile = io.BytesIO(wire)
    handler.connection = SimpleNamespace(settimeout=lambda _: None)
    handler.server = SimpleNamespace(max_bytes=1000, remaining=lambda: 1,
                                     consume=lambda _: None)
    upstream = SimpleNamespace(sendall=sent.append)
    with pytest.raises(ValueError):
        handler._copy_chunked(upstream)


def test_proxy_deadline_and_cancellation_fail_closed():
    proxy = BrowserEgress(timeout=1)
    try:
        proxy.deadline = time.monotonic() - 1
        with pytest.raises(ValueError, match="deadline"):
            proxy.remaining()
    finally:
        proxy.server_close()
    cancelled = BrowserEgress(timeout=3)
    try:
        cancelled.stopping.set()
        with pytest.raises(ValueError, match="deadline"):
            cancelled.remaining()
    finally:
        cancelled.server_close()


def test_partial_request_headers_time_out_without_upstream_dial(monkeypatch):
    dials = []
    monkeypatch.setattr(browser_proxy, "public_connection", lambda *args, **_: dials.append(args))
    started = time.monotonic()
    with BrowserEgress(timeout=1) as proxy, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(("127.0.0.1", proxy.server_port))
        client.sendall(b"GET http://public.test/ HTTP/1.1\r\nHost:")
        assert client.recv(1) == b""
        _wait_for(lambda: not proxy.connections)
    assert time.monotonic() - started < 2.5
    assert dials == []


def test_proxy_exit_closes_active_connect_tunnel_and_threads(public_http):
    url, _, _, _ = public_http
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(3)
    try:
        with BrowserEgress(timeout=3) as proxy:
            port = proxy.server_port
            client.connect(("127.0.0.1", port))
            target = url.removeprefix("http://")
            client.sendall(_request(proxy, method="CONNECT", target=target))
            assert b" 200 " in client.recv(4096).split(b"\r\n", 1)[0]
            _wait_for(lambda: len(proxy.connections) == 2)
        assert proxy.stopping.is_set()
        assert not proxy.thread.is_alive()
        _wait_for(lambda: not proxy.connections)
        with suppress(ConnectionResetError):
            assert client.recv(1) == b""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as closed_listener:
            closed_listener.settimeout(1)
            with pytest.raises(OSError):
                closed_listener.connect(("127.0.0.1", port))
    finally:
        client.close()
