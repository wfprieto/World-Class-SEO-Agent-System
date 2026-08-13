from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from adapters.base import AdapterNotConfigured
from adapters.redirect_chain import RedirectChainAdapter
from adapters.robots_txt import RobotsTxtAdapter
from integrations.extensions.indexnow import IndexNowService


class Response:
    def __init__(self, status: int, body: bytes = b"accepted") -> None:
        self.status = status
        self._body = body

    def getcode(self) -> int:
        return self.status

    def read(self, size: int) -> bytes:
        return self._body[:size]

    def close(self) -> None:
        return None


def test_redirect_chain_adapter_reports_skipped_and_blocked_rows(tmp_path: Path):
    path = tmp_path / "redirects.csv"
    path.write_text(
        "\n".join(
            [
                "source,target,hops,status,skipped",
                "/a,/b,2,checked,false",
                "/c,/c,1,checked,false",
                "/d,/e,0,skipped,true",
                "/private,/login,0,robots_blocked,false",
            ]
        ),
        encoding="utf-8",
    )
    result = RedirectChainAdapter().fetch(str(path))
    assert result.status == "needs-review"
    assert result.data["chain_count"] == 1
    assert result.data["loop_count"] == 1
    assert result.data["skipped_count"] == 1
    assert result.data["blocked_count"] == 1


def test_robots_txt_adapter_reports_meta_and_x_robots_index_blocks():
    result = RobotsTxtAdapter().fetch(
        text="User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n",
        meta_robots="noindex,follow",
        x_robots_tag="none",
    )
    assert result.status == "needs-review"
    assert result.data["meta_blocks_indexing"] is True
    assert result.data["x_robots_blocks_indexing"] is True
    assert "Meta robots directive blocks indexing." in result.warnings
    assert "X-Robots-Tag directive blocks indexing." in result.warnings


def test_indexnow_missing_credential_raises_not_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("INDEXNOW_KEY", raising=False)
    with pytest.raises(AdapterNotConfigured):
        IndexNowService().submit(
            urls=["https://example.com/a"],
            execute=True,
            confirmation="INDEXNOW_SUBMIT",
        )


def test_indexnow_retries_rate_limits_and_reports_attempts(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INDEXNOW_KEY", "secret-key-1234")
    calls = {"count": 0}

    def opener(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.HTTPError(
                request.full_url,
                429,
                "rate limited",
                hdrs=None,
                fp=Response(429, b"rate limited"),
            )
        return Response(200, b"secret-key-1234 accepted")

    result = IndexNowService().submit(
        urls=["https://example.com/a"],
        execute=True,
        confirmation="INDEXNOW_SUBMIT",
        opener=opener,
        retries=1,
        retry_backoff_seconds=0,
    )
    assert result.status == "ok"
    assert result.data["attempts"] == 2
    assert result.data["response_excerpt"] == "[REDACTED] accepted"
    assert "secret-key-1234" not in json.dumps(result.data)


def test_indexnow_rejects_unbounded_retry_configuration(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INDEXNOW_KEY", "secret-key-1234")
    with pytest.raises(ValueError, match="retries"):
        IndexNowService().submit(
            urls=["https://example.com/a"],
            execute=True,
            confirmation="INDEXNOW_SUBMIT",
            retries=99,
        )
