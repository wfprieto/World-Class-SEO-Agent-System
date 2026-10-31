"""Offline real-pipe joins; the external gh target alone becomes an inert child."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import publication_credentials as credentials
from scripts import publication_policy as policy
from scripts import publication_process as process
from scripts import publication_transport as transport
from scripts.publication_remote import upload_asset
from scripts.publication_transport import GitHubCLI


def _payload(size: int) -> bytes:
    return bytes(range(256)) * (size // 256) + bytes(range(size % 256))


def _upload_args(size: int) -> list[str]:
    return ["api", "--hostname", "github.com",
            f"https://uploads.github.com/repos/{policy.REPOSITORY}/releases/123/assets?name=synthetic.whl",
            "--method", "POST", "--input", "-", "--header",
            "Content-Type: application/octet-stream", "--header", f"Content-Length: {size}"]


class InertProvider:
    """No transport success stubs: launch a real contained stdin/hash process."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.api = GitHubCLI(root, executable=sys.executable)
        self.received = root / "received.bin"
        self.calls: list[list[str]] = []
        self.stdout_bytes: int | None = None
        real_popen = subprocess.Popen

        def spawn(command: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
            prefix = command[:7] if os.name == "nt" else []
            if prefix:
                assert prefix == [sys.executable, "-I", "-S", "-u", "-B", "-c", process._LAUNCHER]
            original = command[len(prefix):]
            assert original[0] == self.api.executable and original[1] == "api"
            self.calls.append(original[1:])
            code = ("import hashlib,json,sys;from pathlib import Path;"
                    "data=sys.stdin.buffer.read();"
                    f"Path({str(self.received)!r}).write_bytes(data);"
                    + (f"sys.stdout.buffer.write(b'x'*{self.stdout_bytes})"
                       if self.stdout_bytes is not None else
                       "print(json.dumps({'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}))"))
            replacement = [sys.executable, "-I", "-S", "-u", "-B", "-c", code]
            return real_popen([*prefix, *replacement], **kwargs)

        monkeypatch.setattr(process.subprocess, "Popen", spawn)
        monkeypatch.setattr(transport, "primary_token", lambda: None)
        monkeypatch.setattr(credentials, "primary_token", lambda: None)

    def assert_received(self, data: bytes, result: object) -> None:
        assert result == {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        assert self.received.read_bytes() == data
        assert len(self.calls) == 1


@pytest.fixture
def inert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> InertProvider:
    return InertProvider(tmp_path, monkeypatch)


@pytest.mark.parametrize("size", [policy.MAX_API_BYTES + 1, policy.MAX_MEMBER_BYTES])
def test_canonical_upload_roundtrips_actual_large_binary_body(inert: InertProvider, size: int) -> None:
    data = _payload(size)
    result = upload_asset(inert.api, 123, "synthetic.whl", data)
    inert.assert_received(data, result)
    assert inert.calls == [_upload_args(size)]


def test_default_metadata_exact_four_mib_remains_allowed(inert: InertProvider) -> None:
    data = b" " * (policy.MAX_API_BYTES - 2) + b"{}"
    result = json.loads(inert.api.command(
        ["api", "--hostname", "github.com", f"repos/{policy.REPOSITORY}/git/refs",
         "--method", "POST", "--input", "-"], body=data,
    ))
    inert.assert_received(data, result)


@pytest.mark.parametrize("endpoint", [f"repos/{policy.REPOSITORY}/git/refs", "graphql"])
@pytest.mark.parametrize("output_limit", [policy.MAX_API_BYTES, policy.MAX_MEMBER_BYTES])
def test_large_output_limit_does_not_widen_metadata_or_graphql_input(
    inert: InertProvider, endpoint: str, output_limit: int,
) -> None:
    with pytest.raises(ValueError, match="boundaries"):
        inert.api.command(["api", "--hostname", "github.com", endpoint,
                           "--method", "POST", "--input", "-"],
                          body=_payload(policy.MAX_API_BYTES + 1), limit=output_limit)
    assert inert.calls == [] and not inert.received.exists()


def _near_miss(args: list[str], mutation: str) -> list[str]:
    positions = {"hostname": (2, "evil.invalid"), "method": (5, "PATCH"),
                 "input": (7, "payload.bin"), "content-type": (9, "Content-Type: application/json"),
                 "header-case": (9, "content-type: application/octet-stream"),
                 "length": (11, "Content-Length: 1"), "length-pad": (11, "Content-Length: 04194305")}
    if mutation in positions:
        index, value = positions[mutation]
        args[index] = value
    elif mutation == "extra":
        args.extend(["--field", "surprise=true"])
    elif mutation == "missing-header":
        del args[10:]
    elif mutation == "reordered-headers":
        args[9], args[11] = args[11], args[9]
    else:
        args[3] = _near_endpoint(args[3], mutation)
    return args


def _near_endpoint(endpoint: str, mutation: str) -> str:
    replacements = {"scheme": ("https://", "http://"),
                    "host": ("uploads.github.com/", "uploads.github.com.evil.invalid/"),
                    "repo": (policy.REPOSITORY, "other/project"),
                    "repo-case": ("wfprieto/", "Wfprieto/"),
                    "id-zero": ("releases/123/", "releases/0/"),
                    "id-leading-zero": ("releases/123/", "releases/0123/"),
                    "id-negative": ("releases/123/", "releases/-123/"),
                    "path": ("/assets?", "/assets/extra?"),
                    "slash-name": ("synthetic.whl", "folder/synthetic.whl"),
                    "escaped-name": ("synthetic.whl", "folder%2Fsynthetic.whl"),
                    "empty-name": ("synthetic.whl", ""),
                    "unicode-name": ("synthetic.whl", "synthétique.whl"),
                    "long-name": ("synthetic.whl", "a" * 257)}
    if mutation in replacements:
        return endpoint.replace(*replacements[mutation])
    return endpoint + {"query": "&overwrite=true", "fragment": "#tail"}[mutation]


@pytest.mark.parametrize("mutation", [
    "hostname", "method", "input", "content-type", "header-case", "length", "length-pad",
    "extra", "missing-header", "reordered-headers", "scheme", "host", "repo", "repo-case",
    "id-zero", "id-leading-zero", "id-negative", "path", "slash-name", "escaped-name",
    "empty-name", "unicode-name", "long-name", "query", "fragment",
])
def test_upload_near_miss_retains_default_four_mib_before_spawn(
    inert: InertProvider, mutation: str,
) -> None:
    data = _payload(policy.MAX_API_BYTES + 1)
    with pytest.raises(ValueError, match="boundaries"):
        inert.api.command(_near_miss(_upload_args(len(data)), mutation), body=data,
                          limit=policy.MAX_MEMBER_BYTES)
    assert inert.calls == [] and not inert.received.exists()


def test_direct_canonical_upload_over_forty_mib_rejects_before_spawn(inert: InertProvider) -> None:
    data = _payload(policy.MAX_MEMBER_BYTES + 1)
    with pytest.raises(ValueError, match="boundaries"):
        inert.api.command(_upload_args(len(data)), body=data)
    assert inert.calls == [] and not inert.received.exists()


def test_upload_helper_over_forty_mib_rejects_before_process(inert: InertProvider) -> None:
    with pytest.raises(ValueError, match="bounded approved asset"):
        upload_asset(inert.api, 123, "synthetic.whl", _payload(policy.MAX_MEMBER_BYTES + 1))
    assert inert.calls == [] and not inert.received.exists()


@pytest.mark.parametrize("size", [0, 1, policy.MAX_API_BYTES, policy.MAX_API_BYTES + 1,
                                 policy.MAX_MEMBER_BYTES])
@pytest.mark.parametrize("operation", ["upload", "get-with-body", "post"])
def test_primary_repository_execution_reader_denies_every_body_before_process(
    inert: InertProvider, size: int, operation: str,
) -> None:
    selected = inert.api.for_execution("live_authorized_smokes", policy.REPOSITORY)
    args = {"upload": _upload_args(size),
            "get-with-body": ["api", "--hostname", "github.com", f"repos/{policy.REPOSITORY}"],
            "post": ["api", "--hostname", "github.com", f"repos/{policy.REPOSITORY}/git/refs",
                     "--method", "POST", "--input", "-"]}[operation]
    with pytest.raises(ValueError, match="permits only"):
        selected.command(args, body=_payload(size))
    assert inert.calls == [] and not inert.received.exists()


def test_large_upload_does_not_widen_default_stdout_limit(inert: InertProvider) -> None:
    inert.stdout_bytes = policy.MAX_API_BYTES + 1
    with pytest.raises(ValueError, match="boundary"):
        upload_asset(inert.api, 123, "synthetic.whl", _payload(policy.MAX_API_BYTES + 1))
    assert len(inert.calls) == 1 and inert.received.stat().st_size == policy.MAX_API_BYTES + 1


@pytest.mark.parametrize("kind", [bytearray, memoryview])
def test_canonical_operation_still_requires_actual_bytes(inert: InertProvider, kind: Any) -> None:
    data = kind(_payload(policy.MAX_API_BYTES + 1))
    with pytest.raises(ValueError, match="boundaries"):
        inert.api.command(_upload_args(len(data)), body=data)
    assert inert.calls == [] and not inert.received.exists()
