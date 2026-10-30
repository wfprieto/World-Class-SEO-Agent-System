"""Offline socket-level contracts for public-web connection binding."""

from __future__ import annotations

import io
import socket
import ssl

import pytest

from integrations.technical.http import BoundedHttpClient
from security import pinned_http


class WireSocket:
    def __init__(self, attempts):
        self.attempts = attempts

    def connect(self, address):
        self.attempts.append(address)

    def settimeout(self, timeout):
        pass

    def setsockopt(self, *args):
        pass

    def sendall(self, body):
        pass

    def makefile(self, *args, **kwargs):
        return io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")

    def close(self):
        pass


def wire_boundary(monkeypatch, resolver):
    attempts = []
    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: WireSocket(attempts))

    def independently_resolving_connection(address, *args, **kwargs):
        host, port = address
        resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        sock = WireSocket(attempts)
        sock.connect(resolved[0][4])
        return sock

    monkeypatch.setattr(socket, "create_connection", independently_resolving_connection)
    return attempts


def test_rebinding_is_rejected_before_any_private_socket(monkeypatch):
    calls = []

    def resolver(host, port, **kwargs):
        calls.append(host)
        address = "93.184.216.34" if len(calls) <= 2 else "127.0.0.1"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))]

    attempts = wire_boundary(monkeypatch, resolver)
    with pytest.raises(ValueError, match="non-public"):
        BoundedHttpClient().get("http://public.example/")
    assert attempts == []


def test_connection_uses_only_a_vetted_numeric_destination(monkeypatch):
    calls = []

    def resolver(host, port, **kwargs):
        calls.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    attempts = wire_boundary(monkeypatch, resolver)
    monkeypatch.setattr(
        socket,
        "create_connection",
        lambda *args, **kwargs: pytest.fail("connection must not perform an independent lookup"),
    )
    assert BoundedHttpClient().get("http://public.example/").body == b"ok"
    assert attempts == [("93.184.216.34", 80)]
    # The connection itself must not delegate another name lookup to a second stack.
    assert len(calls) == 4


def test_dns_latency_cannot_restart_connection_deadline(monkeypatch):
    clock = [0.0]

    def resolver(host, port, **kwargs):
        clock[0] = 5.0
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    attempts = wire_boundary(monkeypatch, resolver)
    monkeypatch.setattr(pinned_http.time, "monotonic", lambda: clock[0])
    with pytest.raises(TimeoutError, match="deadline"):
        pinned_http.public_connection("public.example", 80, timeout=1)
    assert attempts == []


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1", "fe80::1"]
)
def test_mixed_public_private_answers_never_create_a_socket(monkeypatch, address):
    def resolver(host, port, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (value, port))
            for value in ("93.184.216.34", address)
        ]

    attempts = wire_boundary(monkeypatch, resolver)
    with pytest.raises(ValueError, match="non-public"):
        pinned_http.public_connection("public.example", 80)
    assert attempts == []


def test_https_keeps_original_host_sni_and_verification(monkeypatch):
    def resolver(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    attempts = wire_boundary(monkeypatch, resolver)
    identity = []
    messages = []

    def wrap(context, sock, *, server_hostname, do_handshake_on_connect):
        assert do_handshake_on_connect is False
        identity.append((server_hostname, context.check_hostname, context.verify_mode))
        return sock

    monkeypatch.setattr(ssl.SSLContext, "wrap_socket", wrap)
    handshakes = []
    monkeypatch.setattr(WireSocket, 'do_handshake', lambda self: handshakes.append(True), raising=False)
    monkeypatch.setattr(WireSocket, "sendall", lambda self, message: messages.append(message))
    assert BoundedHttpClient().get("https://public.example/path").body == b"ok"
    assert identity == [("public.example", True, ssl.CERT_REQUIRED)]
    assert b"Host: public.example\r\n" in b"".join(messages)
    assert attempts == [("93.184.216.34", 443)]
    assert handshakes == [True]


def test_ambient_proxy_environment_cannot_override_vetted_peer(monkeypatch):
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:12345")
    monkeypatch.setenv("https_proxy", "http://169.254.169.254:80")

    def resolver(host, port, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    attempts = wire_boundary(monkeypatch, resolver)
    assert BoundedHttpClient().get("http://public.example/").body == b"ok"
    assert attempts == [("93.184.216.34", 80)]


def test_public_address_failover_uses_numeric_ipv6_and_closes_failed_socket(monkeypatch):
    attempts = []
    sockets = []

    class FailoverSocket(WireSocket):
        closed = False

        def connect(self, address):
            super().connect(address)
            if address[0] == "93.184.216.34":
                raise OSError("fixture first address unavailable")

        def close(self):
            self.closed = True

    def factory(*args, **kwargs):
        sock = FailoverSocket(attempts)
        sockets.append(sock)
        return sock

    monkeypatch.setattr(socket, "socket", factory)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", port, 0, 0)),
        ],
    )
    result = pinned_http.public_connection("public.example", 443)
    assert result is sockets[1]
    assert attempts == [("93.184.216.34", 443), ("2606:4700:4700::1111", 443, 0, 0)]
    assert sockets[0].closed and not sockets[1].closed
    result.close()


@pytest.mark.parametrize("after_connect", [False, True])
def test_cancelled_public_connections_never_remain_open(monkeypatch, after_connect):
    attempts = []
    closed = []
    calls = []
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: WireSocket(attempts))
    monkeypatch.setattr(WireSocket, "close", lambda self: closed.append(True))

    def cancelled():
        calls.append(True)
        return len(calls) >= (2 if after_connect else 1)

    with pytest.raises(TimeoutError):
        pinned_http.public_connection("public.example", 80, cancelled=cancelled)
    assert len(attempts) == len(closed) == int(after_connect)


@pytest.mark.parametrize(
    "connection", [pinned_http.PinnedHTTPConnection, pinned_http.PinnedHTTPSConnection]
)
def test_ambient_tunnels_are_rejected_before_connecting(monkeypatch, connection):
    attempts = []
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: WireSocket(attempts))
    client = connection("public.example", timeout=1)
    client.set_tunnel("127.0.0.1", port=80)
    with pytest.raises(ValueError, match="ambient"):
        client.connect()
    assert attempts == []
