from __future__ import annotations

import pytest

from adapters import rendered_page
from integrations.technical.http import BoundedHttpClient

PUBLIC = "http://93.184.216.34"


class Response:
    def __init__(
        self,
        body: bytes = b"",
        *,
        status: int = 200,
        url: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.body = body
        self.status = status
        self.url = url
        self.headers = headers or {}
        self.closed = False

    def read(self, _size: int = -1) -> bytes:
        return self.body

    def geturl(self) -> str:
        return self.url

    def close(self) -> None:
        self.closed = True


class Opener:
    def __init__(self, *responses: Response) -> None:
        self.responses = list(responses)
        self.requests: list[str] = []
        self.timeouts: list[float] = []

    def open(self, request, *, timeout: float):
        self.requests.append(request.full_url)
        self.timeouts.append(timeout)
        response = self.responses.pop(0)
        if not response.url:
            response.url = request.full_url
        return response


class Route:
    def __init__(self, url: str, resource_type: str = "document") -> None:
        self.request = type("Request", (), {"url": url, "resource_type": resource_type})()
        self.action = ""

    def abort(self) -> str:
        self.action = "abort"
        return self.action

    def continue_(self) -> str:
        self.action = "continue"
        return self.action


def _client(opener: Opener, *, redirects: int = 10, size: int = 12_000_000):
    return BoundedHttpClient(
        opener=opener,
        max_redirects=redirects,
        max_response_bytes=size,
        timeout=30,
    )


def test_public_to_private_redirect_is_blocked_and_response_closed() -> None:
    first = Response(
        status=302,
        url=f"{PUBLIC}/start",
        headers={"Location": "http://127.0.0.1/admin"},
    )
    opener = Opener(first)
    with pytest.raises(ValueError, match="non-public"):
        rendered_page._raw_fetch(f"{PUBLIC}/start", _client(opener))
    assert opener.requests == [f"{PUBLIC}/start"]
    assert opener.timeouts == [30.0]
    assert first.closed


def test_legitimate_public_redirect_returns_body_and_closes_every_response() -> None:
    first = Response(status=302, headers={"Location": "/final"})
    final = Response(
        b"<html>ok</html>",
        headers={
            "Content-Type": "text/html",
            "Set-Cookie": "session=top-secret",
            "Authorization": "Bearer top-secret-token",
        },
    )
    opener = Opener(first, final)
    body, status, headers = rendered_page._raw_fetch(
        f"{PUBLIC}/start", _client(opener)
    )
    assert (body, status) == ("<html>ok</html>", 200)
    assert headers == {"content-type": "text/html"}
    assert opener.requests == [f"{PUBLIC}/start", f"{PUBLIC}/final"]
    assert first.closed and final.closed


@pytest.mark.parametrize(
    ("responses", "redirects", "message"),
    [
        (
            (
                Response(status=302, headers={"Location": "/two"}),
                Response(status=302, headers={"Location": "/one"}),
            ),
            10,
            "loop",
        ),
        (
            (
                Response(status=302, headers={"Location": "/two"}),
                Response(status=302, headers={"Location": "/three"}),
            ),
            1,
            "limit",
        ),
    ],
)
def test_redirect_loop_and_limit_fail_closed(
    responses: tuple[Response, ...], redirects: int, message: str
) -> None:
    opener = Opener(*responses)
    with pytest.raises(ValueError, match=message):
        rendered_page._raw_fetch(f"{PUBLIC}/one", _client(opener, redirects=redirects))
    assert all(response.closed for response in responses)


def test_raw_response_size_is_bounded_and_closed() -> None:
    response = Response(b"oversized")
    with pytest.raises(ValueError, match="maximum"):
        rendered_page._raw_fetch(PUBLIC, _client(Opener(response), size=2))
    assert response.closed


def test_browser_route_guard_revalidates_targets_and_preserves_blocking() -> None:
    private = Route("http://127.0.0.1/admin")
    public = Route(f"{PUBLIC}/page")
    blocked_resource = Route(f"{PUBLIC}/pixel", "image")

    assert rendered_page._guard_browser_request(private, ()) == "abort"
    assert rendered_page._guard_browser_request(public, ()) == "continue"
    assert rendered_page._guard_browser_request(blocked_resource, ("image",)) == "abort"


def test_exported_url_headers_console_and_errors_are_sanitized(monkeypatch) -> None:
    monkeypatch.setattr(
        rendered_page,
        "_raw_fetch",
        lambda _url: (
            '<div id="root"></div>',
            200,
            {"Content-Type": "text/html", "Set-Cookie": "session=header-secret"},
        ),
    )

    def renderer(_url, _block):
        return {
            "content": "<html>rendered</html>",
            "status_code": 200,
            "console_errors": [
                "failed https://example.com/path?token=console-secret Authorization: Bearer abc.def.secret"
            ],
        }

    result = rendered_page.fetch(
        f"{PUBLIC}/page?campaign=full-url-secret",
        mode="always",
        render_fn=renderer,
    )
    exported = str(result.data) + str(result.warnings)
    assert "full-url-secret" not in exported
    assert "header-secret" not in exported
    assert "console-secret" not in exported
    assert "abc.def.secret" not in exported
    assert result.data["url"] == f"{PUBLIC}/page"
    assert result.data["headers"] == {"content-type": "text/html"}


def test_fetch_failure_warning_strips_secret_url_and_cookie(monkeypatch) -> None:
    def fail(_url):
        raise RuntimeError(
            "request failed https://example.com/path?token=url-secret cookie=session-secret"
        )

    monkeypatch.setattr(rendered_page, "_raw_fetch", fail)
    result = rendered_page.fetch(PUBLIC, mode="never")
    warning = " ".join(result.warnings)
    assert result.status == "partial"
    assert "url-secret" not in warning
    assert "session-secret" not in warning
    assert "[REDACTED]" in warning
