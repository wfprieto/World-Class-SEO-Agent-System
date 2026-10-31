"""Finite GitHub CLI requests without leaking credentials or raw provider errors."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import BinaryIO

from scripts.publication_credentials import execution_token, primary_token, readonly_operation
from scripts.publication_policy import MAX_API_BYTES
from scripts.publication_process import bounded_process


def _read_bounded(stream: BinaryIO, limit: int) -> bytes:
    if limit < 1:
        raise ValueError("Response limit must be positive")
    result = bytearray()
    while block := stream.read(min(65536, limit + 1 - len(result))):
        result.extend(block)
        if len(result) > limit:
            raise ValueError("Provider response exceeded its byte limit")
    return bytes(result)


def run_bounded(args: list[str], *, limit: int, cwd: Path | None = None,
                body: bytes | None = None, timeout: float = 60,
                github_token: str | None = None) -> bytes:
    return bounded_process(args, limit=limit, cwd=cwd, body=body, timeout=timeout,
                           github_token=github_token)


class GitHubCLI:
    def __init__(self, root: Path, executable: str | None = None) -> None:
        found = executable or shutil.which("gh")
        if found is None:
            raise ValueError("GitHub CLI is unavailable")
        selected = Path(found).resolve()
        if not selected.is_file() or selected.is_relative_to(root.resolve()):
            raise ValueError("GitHub CLI must be a trusted executable outside source")
        self.executable = str(selected)
        self._root = root
        self._read_repository: str | None = None
        self._read_token: str | None = None

    def for_execution(self, gate: str, repository: str) -> GitHubCLI:
        if self._read_repository is not None:
            raise ValueError("Execution-read client cannot select a different execution scope")
        token = execution_token(gate, repository)
        selected = GitHubCLI(self._root, executable=self.executable)
        selected._read_repository, selected._read_token = repository, token
        return selected

    @staticmethod
    def _path(path: str) -> str:
        if (not re.fullmatch(r"/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^\s#\\]+)?", path)
                or "//" in path or any(part in {".", ".."} for part in path.split("/"))):
            raise ValueError("GitHub path is outside the repository API boundary")
        return path.removeprefix("/")

    def command(self, args: list[str], *, limit: int = MAX_API_BYTES,
                body: bytes | None = None) -> bytes:
        if self._read_repository is not None:
            readonly_operation(args, repository=self._read_repository, body=body, limit=limit)
            token = self._read_token
        else:
            token = primary_token()
        return run_bounded([self.executable, *args], limit=limit, body=body, github_token=token)

    def json(self, path: str) -> object:
        return json.loads(self.binary(path, MAX_API_BYTES))

    def graphql(self, query: str, variables: dict[str, object]) -> object:
        from scripts.publication_reviews import OWNER_QUERY

        node = variables.get("id")
        if (query != OWNER_QUERY or set(variables) != {"id"} or not isinstance(node, str)
                or not 1 <= len(node) <= 2048 or any(character.isspace() for character in node)):
            raise ValueError("Only the canonical owner edit-history query is permitted")
        return json.loads(self.command(
            ["api", "--hostname", "github.com", "graphql", "--method", "POST", "--input", "-"],
            body=json.dumps({"query": query, "variables": variables}).encode(),
        ))

    def binary(self, path: str, limit: int) -> bytes:
        return self.command(["api", "--hostname", "github.com", self._path(path)], limit=limit)

    def write(self, path: str, payload: dict[str, object], *, method: str = "POST") -> object:
        endpoint = self._path(path)
        if method not in {"POST", "PATCH"} or endpoint.count("/") < 3:
            raise ValueError("Publication mutation method is not permitted")
        return json.loads(self.command(
            ["api", "--hostname", "github.com", endpoint, "--method", method,
             "--input", "-"], body=json.dumps(payload).encode(),
        ))
