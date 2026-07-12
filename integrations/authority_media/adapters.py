"""Runtime adapters for the authority, media, and drift integration pack."""

from __future__ import annotations

from typing import Any

from adapters.base import AdapterResult
from integrations.authority_media.services import (
    BacklinkProfileService,
    CommonCrawlService,
    DomainHistoryService,
    DriftService,
    IPTCLabelService,
    TranscriptService,
    YouTubeSearchService,
)


class AuthorityMediaAdapter:
    name = "authority_media"

    def __init__(self) -> None:
        self.commoncrawl = CommonCrawlService()
        self.backlinks = BacklinkProfileService()
        self.domain_history = DomainHistoryService()
        self.youtube = YouTubeSearchService()
        self.iptc = IPTCLabelService()
        self.transcripts = TranscriptService()

    def fetch(self, operation: str, **kwargs: Any) -> AdapterResult:
        handlers = {
            "commoncrawl": self.commoncrawl.search,
            "link_profile": self.backlinks.profile,
            "link_gap": self.backlinks.gap,
            "domain_history": self.domain_history.history,
            "youtube_search": self.youtube.search,
            "iptc_label": self.iptc.inspect,
            "transcript_check": self.transcripts.check,
        }
        if operation not in handlers:
            raise ValueError(f"unsupported authority/media operation: {operation}")
        return handlers[operation](**kwargs)


class DriftExecutionAdapter:
    name = "drift_execution"

    def __init__(self) -> None:
        self.service = DriftService()

    def fetch(self, operation: str, **kwargs: Any) -> AdapterResult:
        handlers = {
            "baseline": self.service.baseline,
            "compare": self.service.compare,
            "history": self.service.history,
            "report": self.service.report,
            "watch": self.service.watch,
        }
        if operation not in handlers:
            raise ValueError(f"unsupported drift operation: {operation}")
        return handlers[operation](**kwargs)
