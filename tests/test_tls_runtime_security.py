"""Actual TLS identity verification against ephemeral loopback fixtures only."""

from __future__ import annotations

import http.client
import os
import shutil
import socket
import ssl
import subprocess
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from integrations.technical.browser import PlaywrightRenderer
from integrations.technical.http import BoundedHttpClient
from security import url_safety
from security.browser_proxy import BrowserEgress

PUBLIC_ADDRESS = "93.184.216.34"


def _browser_enabled(request):
    return request.config.getoption("--browser-security") or os.environ.get(
        "WCSEO_BROWSER_SECURITY"
    ) == "1"


def _openssl(request):
    openssl = shutil.which("openssl")
    git_openssl = Path("C:/Program Files/Git/usr/bin/openssl.exe")
    if openssl is None and git_openssl.is_file():
        openssl = str(git_openssl)
    if openssl is None:
        if _browser_enabled(request):
            pytest.fail("explicit TLS/browser certification requires OpenSSL")
        pytest.skip("optional local TLS fixture requires OpenSSL")
    return openssl


@pytest.fixture
def tls_certificate(tmp_path, request):
    openssl = _openssl(request)
    certificate, key = tmp_path / "fixture-ca.pem", tmp_path / "fixture-key.pem"
    try:
        subprocess.run(
            [
                openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                "-subj", "/CN=public.test", "-addext", "subjectAltName=DNS:public.test",
                "-keyout", str(key), "-out", str(certificate),
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            timeout=30,
        )
        yield certificate, key
    finally:
        certificate.unlink(missing_ok=True)
        key.unlink(missing_ok=True)


@pytest.fixture
def tls_site(tls_certificate, monkeypatch):
    certificate, key = tls_certificate
    observations = {"sni": [], "gets": [], "attempts": []}
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(str(certificate), str(key))
    server_context.set_servername_callback(
        lambda _socket, name, _context: observations["sni"].append(name)
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            observations["gets"].append((self.path, self.headers.get("Host")))
            body = b"verified tls fixture"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    class TLSServer(ThreadingHTTPServer):
        daemon_threads = True

        def get_request(self):
            raw, address = super().get_request()
            raw.settimeout(2)
            try:
                return server_context.wrap_socket(raw, server_side=True), address
            except BaseException:
                raw.close()
                raise

    server = TLSServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    monkeypatch.setattr(
        url_safety, "ALLOWED_TARGET_PORTS",
        url_safety.ALLOWED_TARGET_PORTS | {server.server_port},
    )
    real_connect = socket.socket.connect

    def fixture_connect(sock, address):
        if address[0] == "127.0.0.1":
            return real_connect(sock, address)  # Windows asyncio's internal socketpair.
        observations["attempts"].append(address)
        if address == (PUBLIC_ADDRESS, server.server_port):
            return real_connect(sock, ("127.0.0.1", server.server_port))
        raise OSError("TLS fixture forbids every unplanned socket destination")

    monkeypatch.setattr(socket.socket, "connect", fixture_connect)
    try:
        yield server.server_port, certificate, observations
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def _trust_fixture(monkeypatch, certificate):
    context = ssl.create_default_context(cafile=str(certificate))
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED
    monkeypatch.setattr(ssl, "_create_default_https_context", lambda: context)


def test_actual_pinned_tls_preserves_host_sni_and_certificate_verification(tls_site, monkeypatch):
    port, certificate, observations = tls_site
    _trust_fixture(monkeypatch, certificate)

    result = BoundedHttpClient(timeout=3).get(f"https://public.test:{port}/verified")

    assert result.status_code == 200
    assert result.body == b"verified tls fixture"
    assert observations["gets"] == [("/verified", f"public.test:{port}")]
    assert observations["sni"] == ["public.test"]
    assert observations["attempts"] == [(PUBLIC_ADDRESS, port)]


def test_actual_pinned_tls_rejects_wrong_hostname_before_get(tls_site, monkeypatch):
    port, certificate, observations = tls_site
    _trust_fixture(monkeypatch, certificate)

    with pytest.raises(urllib.error.URLError) as caught:
        BoundedHttpClient(timeout=3).get(f"https://wrong.test:{port}/must-not-run")

    assert isinstance(caught.value.reason, ssl.SSLCertVerificationError)
    assert "hostname mismatch" in str(caught.value.reason).lower()
    assert observations["gets"] == []
    assert observations["sni"] == ["wrong.test"]
    assert observations["attempts"] == [(PUBLIC_ADDRESS, port)]


def test_actual_pinned_tls_rejects_untrusted_certificate_before_get(tls_site):
    port, _, observations = tls_site

    with pytest.raises(urllib.error.URLError) as caught:
        BoundedHttpClient(timeout=3).get(f"https://public.test:{port}/must-not-run")

    assert isinstance(caught.value.reason, ssl.SSLCertVerificationError)
    assert observations["gets"] == []
    assert observations["sni"] == ["public.test"]
    assert observations["attempts"] == [(PUBLIC_ADDRESS, port)]


def test_actual_connect_preserves_end_to_end_verified_tls_and_host(tls_site):
    port, certificate, observations = tls_site
    context = ssl.create_default_context(cafile=str(certificate))
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    with BrowserEgress(timeout=3) as proxy, socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(("127.0.0.1", proxy.server_port))
        client.sendall((f"CONNECT public.test:{port} HTTP/1.1\r\n"
                        f"Host: public.test:{port}\r\n"
                        f"Proxy-Authorization: {proxy.authorization}\r\n\r\n").encode())
        headers = bytearray()
        while not headers.endswith(b"\r\n\r\n"):
            chunk = client.recv(1)
            assert chunk, "CONNECT closed before establishing the tunnel"
            headers.extend(chunk)
        assert b" 200 " in bytes(headers).split(b"\r\n", 1)[0]
        with context.wrap_socket(client, server_hostname="public.test") as tls:
            tls.sendall((f"GET /connect-verified HTTP/1.1\r\nHost: public.test:{port}\r\n"
                         "Connection: close\r\n\r\n").encode())
            response = http.client.HTTPResponse(tls)
            response.begin()
            assert response.status == 200
            assert response.read() == b"verified tls fixture"
            response.close()
        assert proxy.requests_seen == 1
        assert proxy.bytes_seen > 0
    assert observations["gets"] == [("/connect-verified", f"public.test:{port}")]
    assert observations["sni"] == ["public.test"]
    assert observations["attempts"] == [(PUBLIC_ADDRESS, port)]


def test_actual_chromium_rejects_untrusted_tls_through_connect(tls_site, request):
    if not _browser_enabled(request):
        pytest.skip("opt-in actual Chromium TLS certification")
    port, _, observations = tls_site
    renderer = PlaywrightRenderer()
    assert renderer.health().state == "AVAILABLE", "explicit certification requires Chromium"

    with pytest.raises(Exception, match="ERR_CERT_AUTHORITY_INVALID"):
        renderer.render(f"https://public.test:{port}/must-not-run", timeout_ms=5_000)

    assert observations["gets"] == []
    assert "public.test" in observations["sni"]
    assert (PUBLIC_ADDRESS, port) in observations["attempts"]
