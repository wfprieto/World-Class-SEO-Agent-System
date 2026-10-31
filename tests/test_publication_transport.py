"""Bounded transport primitives exercise rejection without any network calls."""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import pytest

from scripts.publication_reviews import OWNER_QUERY
from scripts.publication_transport import GitHubCLI, _read_bounded, run_bounded


def test_transport_preserves_exact_bytes_at_limit() -> None:
    assert _read_bounded(BytesIO(b"abc"), 3) == b"abc"


def test_transport_rejects_excess_bytes() -> None:
    with pytest.raises(ValueError):
        _read_bounded(BytesIO(b"abcd"), 3)


@pytest.mark.parametrize("path", [
    "https://evil.invalid/", "/repos/a/b/../secrets", "/repos/a/b/evil\\path",
    "/repos/a/b/evil#fragment", "/repos/a/b/evil\nheader", "//evil.invalid/repos/a/b/x",
])
def test_transport_rejects_off_host_or_ambiguous_paths(path: str) -> None:
    with pytest.raises(ValueError):
        GitHubCLI._path(path)


def test_transport_preserves_fixed_repo_pagination_path() -> None:
    path = "/repos/wfprieto/World-Class-SEO-Agent-System/actions/runs/12/jobs?per_page=100&page=2"
    assert GitHubCLI._path(path) == path.removeprefix("/")


def test_bounded_process_returns_exact_output() -> None:
    result = run_bounded([sys.executable, "-B", "-c", "import sys;sys.stdout.write('ok')"],
                         limit=2, timeout=5)
    assert result == b"ok"


def test_bounded_process_kills_oversized_output_without_returning_it() -> None:
    with pytest.raises(ValueError, match="boundary"):
        run_bounded([sys.executable, "-B", "-c", "print('not-a-real-secret-'*1000)"],
                    limit=4, timeout=5)


def test_bounded_process_kills_timeout() -> None:
    with pytest.raises(ValueError, match="boundary"):
        run_bounded([sys.executable, "-B", "-c", "import time;time.sleep(5)"],
                    limit=4, timeout=0.2)


def test_owner_graph_query_uses_fixed_host_and_json_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = GitHubCLI(tmp_path, executable=sys.executable)
    calls: list[object] = []

    def command(args: list[str], *, body: bytes) -> bytes:
        calls.append((args, json.loads(body)))
        return b'{"data":{"node":{"lastEditedAt":null}}}'

    monkeypatch.setattr(api, "command", command)
    assert api.graphql(OWNER_QUERY, {"id": "IC_fixture"}) == {
        "data": {"node": {"lastEditedAt": None}},
    }
    assert calls == [(["api", "--hostname", "github.com", "graphql", "--method", "POST",
                      "--input", "-"], {"query": OWNER_QUERY, "variables": {"id": "IC_fixture"}})]


@pytest.mark.parametrize("query", ["mutation{deleteIssue{id}}", "query{viewer{login}}", ""])
def test_graphql_cannot_be_used_for_other_reads_or_mutations(tmp_path: Path, query: str) -> None:
    api = GitHubCLI(tmp_path, executable=sys.executable)
    with pytest.raises(ValueError):
        api.graphql(query, {"id": "IC_fixture"})
