"""Short-lived authenticated Chromium egress with vetted numeric upstream sockets.

HTTPS remains end-to-end TLS: CONNECT inspects the destination, not encrypted
paths, queries, or content. URL interception is a separate defense, not the SSRF
boundary. This proxy never uses environment/system upstream proxies.
"""

from __future__ import annotations

import base64
import hmac
import re
import secrets
import select
import socket
import threading
import time
import urllib.parse
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from security.pinned_http import public_connection
from security.url_safety import validate_public_url


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Do not log URLs, proxy credentials, request bodies, or headers.

    @property
    def boundary(self) -> Any:
        return self.server

    def _authorize(self) -> bool:
        self.close_connection = True
        values = self.headers.get_all("Proxy-Authorization", [])
        if len(values) == 1 and hmac.compare_digest(
            values[0].encode("latin-1"), self.boundary.authorization.encode("ascii")
        ):
            self.boundary.begin_request()
            return True
        self.send_response(407)
        self.send_header("Proxy-Authenticate", 'Basic realm="isolated-browser"')
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        return False

    def do_CONNECT(self) -> None:
        try:
            if not self._authorize():
                return
            if any(char in self.path for char in "/\\?#@\r\n"):
                raise ValueError("invalid CONNECT authority")
            target = urllib.parse.urlsplit(validate_public_url(f"https://{self.path}/"))
            with public_connection(
                target.hostname or "",
                target.port or 443,
                timeout=self.boundary.remaining(),
                cancelled=self.boundary.stopping.is_set,
            ) as upstream:
                self.send_response(200, "Connection established")
                self.end_headers()
                self.boundary.relay(self.connection, upstream)
        except (OSError, ValueError):
            self.boundary.blocked()
            self.close_connection = True
            # A tunnel may already be established; closing it is fail-closed.
            self.connection.close()

    def _copy_exact(self, upstream: socket.socket, size: int) -> None:
        if size < 0 or size > self.boundary.max_bytes:
            raise ValueError("browser request body exceeds limit")
        while size:
            self.connection.settimeout(self.boundary.remaining())
            chunk = self.rfile.read(min(size, 65_536))
            if not chunk:
                raise ValueError("incomplete browser request body")
            self.boundary.consume(len(chunk))
            upstream.sendall(chunk)
            size -= len(chunk)

    def _copy_chunked(self, upstream: socket.socket) -> None:
        while True:
            line = self.rfile.readline(8193)
            if not line.endswith(b"\r\n") or len(line) > 8192:
                raise ValueError("invalid chunk framing")
            token = line[:-2].split(b";", 1)[0]
            if not re.fullmatch(rb"[0-9A-Fa-f]+", token):
                raise ValueError("invalid chunk size")
            size = int(token, 16)
            self.boundary.consume(len(line))
            upstream.sendall(line)
            if size == 0:
                trailer_bytes = 0
                while True:
                    trailer = self.rfile.readline(8193)
                    trailer_bytes += len(trailer)
                    if not trailer.endswith(b"\r\n") or trailer_bytes > 65_536:
                        raise ValueError("invalid chunk trailers")
                    self.boundary.consume(len(trailer))
                    upstream.sendall(trailer)
                    if trailer == b"\r\n":
                        return
            self._copy_exact(upstream, size)
            ending = self.rfile.read(2)
            if ending != b"\r\n":
                raise ValueError("invalid chunk ending")
            self.boundary.consume(2)
            upstream.sendall(ending)

    def _copy_body(self, upstream: socket.socket) -> None:
        encoding = self.headers.get("Transfer-Encoding")
        if encoding:
            if (
                encoding.lower() != "chunked"
                or len(self.headers.get_all("Transfer-Encoding", [])) != 1
            ):
                raise ValueError("unsupported transfer encoding")
            self._copy_chunked(upstream)
        else:
            self._copy_exact(upstream, int(self.headers.get("Content-Length", "0")))

    def _validate_framing(self) -> None:
        lengths = self.headers.get_all("Content-Length", [])
        encodings = self.headers.get_all("Transfer-Encoding", [])
        if len(lengths) > 1 or len(encodings) > 1 or (lengths and encodings):
            raise ValueError("ambiguous request framing")
        if encodings and encodings[0].strip().lower() != "chunked":
            raise ValueError("unsupported transfer encoding")
        if lengths:
            value = lengths[0].strip()
            if not value.isascii() or not value.isdigit() or len(value) > 20:
                raise ValueError("invalid Content-Length")
            if int(value) > self.boundary.max_bytes:
                raise ValueError("browser request body exceeds limit")
        connection = {
            value.strip().lower() for value in self.headers.get("Connection", "").split(",")
        }
        if connection & {"host", "content-length", "transfer-encoding"}:
            raise ValueError("ambiguous connection headers")

    def _upgrade(self) -> bool:
        upgrade = self.headers.get("Upgrade", "").lower()
        if not upgrade:
            return False
        if upgrade != "websocket" or self.command != "GET":
            raise ValueError("unsupported browser upgrade")
        if "upgrade" not in {
            value.strip().lower() for value in self.headers.get("Connection", "").split(",")
        }:
            raise ValueError("missing upgrade connection header")
        if self.headers.get("Sec-WebSocket-Version") != "13":
            raise ValueError("unsupported WebSocket version")
        if len(base64.b64decode(self.headers.get("Sec-WebSocket-Key", ""), validate=True)) != 16:
            raise ValueError("invalid WebSocket handshake key")
        return True

    def _host_authority(self) -> tuple[str, int]:
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1:
            raise ValueError("one Host header is required")
        authority = urllib.parse.urlsplit("http://" + hosts[0])
        if any(
            (
                authority.username,
                authority.password,
                authority.path,
                authority.query,
                authority.fragment,
            )
        ):
            raise ValueError("invalid Host header")
        host = (authority.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
        return host, authority.port or 80

    def _forward_target(self) -> urllib.parse.SplitResult:
        candidate = self.path
        parsed = urllib.parse.urlsplit(candidate)
        if parsed.scheme == "ws":
            candidate = urllib.parse.urlunsplit(
                ("http", parsed.netloc, parsed.path, parsed.query, "")
            )
        target = urllib.parse.urlsplit(validate_public_url(candidate))
        if target.scheme != "http":
            raise ValueError("HTTPS requires a verified CONNECT tunnel")
        if self._host_authority() != (target.hostname, target.port or 80):
            raise ValueError("Host and request target differ")
        self._validate_framing()
        return target

    def _forward(self) -> None:
        try:
            if not self._authorize():
                return
            target = self._forward_target()
            upgrade = self._upgrade()
            path = urllib.parse.urlunsplit(("", "", target.path or "/", target.query, ""))
            excluded = {"proxy-authorization", "proxy-connection", "connection"}
            excluded.update(
                value.strip().lower() for value in self.headers.get("Connection", "").split(",")
            )
            if upgrade:
                excluded.discard("upgrade")
            headers = "".join(
                f"{key}: {value}\r\n"
                for key, value in self.headers.items()
                if key.lower() not in excluded
            )
            connection = "Upgrade" if upgrade else "close"
            message = f"{self.command} {path} HTTP/1.1\r\n{headers}Connection: {connection}\r\n\r\n".encode(
                "latin-1"
            )
            if len(message) > 65_536:
                raise ValueError("browser request headers exceed limit")
            with public_connection(
                target.hostname or "",
                target.port or 80,
                timeout=self.boundary.remaining(),
                cancelled=self.boundary.stopping.is_set,
            ) as upstream:
                self.boundary.consume(len(message))
                upstream.sendall(message)
                self._copy_body(upstream)
                self.boundary.relay(self.connection, upstream)
        except (OSError, ValueError):
            self.boundary.blocked()
            self.close_connection = True
            self.connection.close()

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = _forward


class BrowserEgress(ThreadingHTTPServer):
    """One context's finite egress budget; always bind only the loopback listener."""

    daemon_threads = True
    allow_reuse_address = False

    def __init__(
        self, *, timeout: float = 30, max_bytes: int = 50_000_000, max_requests: int = 1000
    ) -> None:
        if (
            not 1 <= timeout <= 120
            or not 1 <= max_bytes <= 50_000_000
            or not 1 <= max_requests <= 1000
        ):
            raise ValueError("browser egress limits are outside supported bounds")
        self.deadline = time.monotonic() + timeout
        self.max_bytes, self.max_requests = max_bytes, max_requests
        self.bytes_seen = self.requests_seen = self.blocked_requests = 0
        self.failure: str | None = None
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(64)
        self.connections: set[socket.socket] = set()
        password = secrets.token_urlsafe(32)
        self.authorization = "Basic " + base64.b64encode(f"wcseo:{password}".encode()).decode()
        super().__init__(("127.0.0.1", 0), _Handler)
        self.proxy = {
            "server": f"http://127.0.0.1:{self.server_port}",
            "bypass": "<-loopback>",
            "username": "wcseo",
            "password": password,
        }
        self.thread = threading.Thread(
            target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )

    def __enter__(self) -> BrowserEgress:
        self.thread.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stopping.set()
        with self.lock:
            connections = tuple(self.connections)
        for connection in connections:
            with suppress(OSError):
                connection.shutdown(socket.SHUT_RDWR)
            connection.close()
        self.shutdown()
        self.server_close()
        self.thread.join(timeout=2)

    def process_request(
        self, request: socket.socket | tuple[bytes, socket.socket], client_address: Any
    ) -> None:
        if not isinstance(request, socket.socket):
            raise TypeError("browser proxy requires a TCP socket")
        if not self.slots.acquire(blocking=False):
            self.failure = "browser concurrent connection limit exceeded"
            self.shutdown_request(request)
            return
        request.settimeout(min(2, max(0.1, self.deadline - time.monotonic())))
        with self.lock:
            self.connections.add(request)
        super().process_request(request, client_address)

    def process_request_thread(
        self, request: socket.socket | tuple[bytes, socket.socket], client_address: Any
    ) -> None:
        if not isinstance(request, socket.socket):
            raise TypeError("browser proxy requires a TCP socket")
        try:
            super().process_request_thread(request, client_address)
        finally:
            with self.lock:
                self.connections.discard(request)
            self.slots.release()

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if self.stopping.is_set() or remaining <= 0:
            self.failure = "browser network deadline exceeded"
        self.assert_budget()
        return remaining

    def assert_budget(self) -> None:
        if self.failure:
            raise ValueError(self.failure)

    def begin_request(self) -> None:
        self.remaining()
        with self.lock:
            self.requests_seen += 1
            if self.requests_seen > self.max_requests:
                self.failure = "browser request limit exceeded"
        self.assert_budget()

    def consume(self, size: int) -> None:
        with self.lock:
            self.bytes_seen += size
            if self.bytes_seen > self.max_bytes:
                self.failure = "browser network byte limit exceeded"
        self.assert_budget()

    def blocked(self) -> None:
        with self.lock:
            self.blocked_requests += 1

    def relay(self, client: socket.socket, upstream: socket.socket) -> None:
        with self.lock:
            self.connections.add(upstream)
        try:
            while not self.stopping.is_set():
                readable, _, _ = select.select(
                    [client, upstream], [], [], min(0.1, self.remaining())
                )
                for source in readable:
                    chunk = source.recv(65_536)
                    if not chunk:
                        return
                    self.consume(len(chunk))
                    destination = upstream if source is client else client
                    destination.settimeout(self.remaining())
                    destination.sendall(chunk)
        finally:
            with self.lock:
                self.connections.discard(upstream)

    def evidence(self) -> dict[str, Any]:
        return {
            "transport": "vetted-numeric-egress",
            "requests": self.requests_seen,
            "bytes": self.bytes_seen,
            "blocked_connections": self.blocked_requests,
            "service_workers": "blocked",
            "websockets": "public-address-egress",
            "https_url_visibility": "destination-only-inside-CONNECT",
        }
