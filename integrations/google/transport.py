"""Same-host Google redirects; credentials never cross host boundaries."""
from __future__ import annotations

import urllib.parse
import urllib.request
from http.client import HTTPMessage
from typing import IO

from contracts.google import GoogleAPIError


class _NoCrossHostRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]) -> None:
        super().__init__()
        self.allowed_hosts = set(allowed_hosts)

    def redirect_request(
        self, req: urllib.request.Request, fp: IO[bytes], code: int,
        msg: str, headers: HTTPMessage, newurl: str,
    ) -> urllib.request.Request | None:
        original = urllib.parse.urlsplit(req.full_url)
        redirected = urllib.parse.urlsplit(newurl)
        if (
            redirected.scheme != "https"
            or redirected.hostname not in self.allowed_hosts
            or redirected.hostname != original.hostname
        ):
            raise GoogleAPIError(
                "google_api",
                code,
                "refused redirect outside the original approved Google host",
                state="BLOCKED",
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)
