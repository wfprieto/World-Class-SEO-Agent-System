"""Canonical numeric-pinned, proxy-free, credential-safe LLM transport."""

from __future__ import annotations

import urllib.request
from typing import Any

from contracts.llm_transport import LLMConfigurationError, LLMOpener
from security.pinned_http import PinnedHTTPHandler, PinnedHTTPSHandler


class RejectCredentialRedirects(urllib.request.HTTPRedirectHandler):
    """Never forward credential-bearing provider requests to a redirect target."""

    def redirect_request(
        self,
        req: Any,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise LLMConfigurationError("LLM credential request refused a redirect.")


def build_llm_opener() -> LLMOpener[urllib.request.Request]:
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        PinnedHTTPHandler(),
        PinnedHTTPSHandler(),
        RejectCredentialRedirects(),
    )
