"""Hermetic network boundary for unit and integration tests.

Production SSRF rules remain unchanged. Tests may override this fixture explicitly when
validating resolver behavior. Any unplanned hostname resolves to a stable public test
address instead of using live DNS.
"""
from __future__ import annotations

import socket

import pytest

_PUBLIC_TEST_ADDRESS = "93.184.216.34"
_PRIVATE_HOSTS = {
    "localhost": "127.0.0.1",
    "metadata.google.internal": "169.254.169.254",
    "169.254.169.254": "169.254.169.254",
}


@pytest.fixture(autouse=True)
def hermetic_dns(monkeypatch: pytest.MonkeyPatch):
    """Prevent accidental DNS egress while preserving public/private address tests."""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        value = str(host).rstrip(".").lower()
        address = _PRIVATE_HOSTS.get(value, "127.0.0.1" if value.endswith(".local") else _PUBLIC_TEST_ADDRESS)
        socktype = kwargs.get("type", socket.SOCK_STREAM)
        return [(socket.AF_INET, socktype, 6, "", (address, port or 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
