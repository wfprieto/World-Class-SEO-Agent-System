"""Numeric-only public sockets with original HTTP Host and verified TLS identity."""

from __future__ import annotations

import http.client
import socket
import ssl
import time
import urllib.request
from collections.abc import Callable
from typing import Any, cast

from security.http_deadline import register_socket, remaining_timeout, validate_timeout
from security.url_safety import resolve_public_addresses


def _connection_timeout(timeout: Any) -> float:
    if timeout is cast(Any, socket)._GLOBAL_DEFAULT_TIMEOUT:
        timeout = socket.getdefaulttimeout()
    return validate_timeout(30 if timeout is None else timeout)


def public_connection(
    host: str,
    port: int,
    *,
    timeout: float = 30,
    source_address: tuple | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> socket.socket:
    """Dial only a freshly vetted address, with one overall connection deadline."""
    deadline = time.monotonic() + remaining_timeout(timeout)
    destinations = resolve_public_addresses(host, port)
    last_error: OSError | None = None
    for family, address in destinations:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or (cancelled is not None and cancelled()):
            raise TimeoutError("public connection deadline exceeded")
        sock = register_socket(socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP))
        try:
            sock.settimeout(remaining)
            if source_address is not None:
                sock.bind(source_address)
            sock.connect(address)
            if cancelled is not None and cancelled():
                raise TimeoutError("public connection was cancelled")
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            return sock
        except OSError as exc:
            sock.close()
            last_error = exc
    assert last_error is not None
    raise last_error


class PinnedHTTPConnection(http.client.HTTPConnection):
    def connect(self) -> None:
        if getattr(self, "_tunnel_host", None):
            raise ValueError("ambient HTTP tunnels are not supported")
        self.sock = register_socket(public_connection(
            self.host,
            self.port,
            timeout=_connection_timeout(self.timeout),
            source_address=getattr(self, "source_address", None),
        ))


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    _context: ssl.SSLContext

    def connect(self) -> None:
        if getattr(self, "_tunnel_host", None):
            raise ValueError("ambient HTTPS tunnels are not supported")
        sock = public_connection(
            self.host,
            self.port,
            timeout=_connection_timeout(self.timeout),
            source_address=getattr(self, "source_address", None),
        )
        try:
            self.sock = register_socket(self._context.wrap_socket(
                sock, server_hostname=self.host, do_handshake_on_connect=False,
            ))
            self.sock.settimeout(remaining_timeout(_connection_timeout(self.timeout)))
            self.sock.do_handshake()
        except BaseException:
            if self.sock is not None:
                self.sock.close()
            sock.close()
            raise


class PinnedHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req: urllib.request.Request) -> Any:
        return self.do_open(PinnedHTTPConnection, req)


class PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    _context: ssl.SSLContext | None

    def https_open(self, req: urllib.request.Request) -> Any:
        return self.do_open(PinnedHTTPSConnection, req, context=self._context)
