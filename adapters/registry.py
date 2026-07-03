"""Adapter registry for runtime usage."""

from __future__ import annotations

from adapters.backlinks import BacklinkCSVAdapter
from adapters.crawler_csv import CrawlerCSVAdapter
from adapters.ga4 import GA4ExportAdapter
from adapters.gsc import GSCExportAdapter
from adapters.log_parser import LogParserAdapter
from adapters.pagespeed import PageSpeedPayloadAdapter
from adapters.rank_tracking import RankTrackingCSVAdapter
from adapters.schema_validation import SchemaValidationAdapter


def default_adapters() -> dict[str, object]:
    return {
        "backlink_csv": BacklinkCSVAdapter(),
        "crawler_csv": CrawlerCSVAdapter(),
        "ga4_export": GA4ExportAdapter(),
        "gsc_export": GSCExportAdapter(),
        "log_parser": LogParserAdapter(),
        "pagespeed_payload": PageSpeedPayloadAdapter(),
        "rank_tracking_csv": RankTrackingCSVAdapter(),
        "schema_validation": SchemaValidationAdapter(),
    }

