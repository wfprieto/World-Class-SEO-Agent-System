"""Authority, media, provenance, and drift services with truthful evidence states."""

from __future__ import annotations

import csv
import json
import urllib.parse
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from contracts.adapter import AdapterResult
from contracts.construction import URLIdentity
from integrations.authority_media.domain_history import DomainHistoryService as DomainHistoryService
from integrations.authority_media.drift import DriftService as DriftService
from integrations.authority_media.input_data import (
    MAX_ROWS,
    _bounded_text,
    _host,
    _state,
)
from integrations.authority_media.media_metadata import IPTCLabelService as IPTCLabelService
from integrations.authority_media.transcript_service import TranscriptService as TranscriptService
from integrations.authority_media.transport import BoundedTransport
from integrations.authority_media.youtube_service import (
    YouTubeSearchService as YouTubeSearchService,
)


class CommonCrawlService:
    """Bounded Common Crawl URL-index retrieval. This does not claim backlink coverage."""

    COLLINFO = "https://index.commoncrawl.org/collinfo.json"

    def __init__(
        self, canonicalize_url: URLIdentity, transport: BoundedTransport | None = None
    ) -> None:
        self._canonicalize_url = canonicalize_url
        self.transport = transport or BoundedTransport({"index.commoncrawl.org"})

    def _parse_records(self, text: str, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            if len(records) >= limit:
                warnings.append("Common Crawl records were truncated at the configured limit.")
                break
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                warnings.append(f"Ignored invalid NDJSON record at line {line_number}.")
                continue
            if not isinstance(row, dict) or not row.get("url"):
                warnings.append(f"Ignored incomplete Common Crawl record at line {line_number}.")
                continue
            try:
                normalized_url = self._canonicalize_url(str(row["url"]))
            except ValueError:
                warnings.append(f"Ignored unsafe or invalid URL at line {line_number}.")
                continue
            records.append(
                {
                    "url": normalized_url,
                    "timestamp": row.get("timestamp"),
                    "status": row.get("status"),
                    "mime": row.get("mime"),
                    "digest": row.get("digest"),
                    "filename": row.get("filename"),
                    "offset": row.get("offset"),
                    "length": row.get("length"),
                }
            )
        return records, warnings

    def search(
        self,
        domain: str,
        *,
        fixture_path: str | None = None,
        index: str | None = None,
        max_pages: int = 1,
        page_size: int = 100,
    ) -> AdapterResult:
        host = _host(domain)
        if not 1 <= max_pages <= 5:
            raise ValueError("max_pages must be from 1 to 5")
        if not 1 <= page_size <= 1000:
            raise ValueError("page_size must be from 1 to 1000")
        warnings = [
            "Common Crawl URL-index presence is not a complete backlink graph and must not be presented as one."
        ]
        if fixture_path:
            text = _bounded_text(fixture_path)
            records, parse_warnings = self._parse_records(text, max_pages * page_size)
            warnings.extend(parse_warnings)
            source = fixture_path
            index_id = index or "fixture"
            request_count = 0
            retry_count = 0
        else:
            listing, _ = self.transport.get_json(self.COLLINFO)
            if not isinstance(listing, list) or not listing:
                return AdapterResult(
                    "commoncrawl", "invalid_response", {"data_state": "INVALID_RESPONSE"}, warnings
                )
            selected = _select_index(listing, index)
            if not selected:
                return AdapterResult(
                    "commoncrawl",
                    "not_found",
                    {"data_state": "NOT_FOUND", "index": index},
                    warnings,
                )
            api = str(selected.get("cdx-api") or "")
            parsed_api = urllib.parse.urlsplit(api)
            if parsed_api.scheme != "https" or parsed_api.hostname != "index.commoncrawl.org":
                return AdapterResult(
                    "commoncrawl", "invalid_response", {"data_state": "INVALID_RESPONSE"}, warnings
                )
            index_id = str(selected.get("id") or "unknown")
            collected = self._collect_pages(host, api, max_pages, page_size, warnings)
            records = collected[: max_pages * page_size]
            source = api
            request_count = self.transport.request_count
            retry_count = self.transport.retry_count
        unique = {row["url"]: row for row in records}
        normalized = list(unique.values())
        status = "ok" if normalized else "empty"
        return AdapterResult(
            source=source,
            status=status,
            data={
                "data_state": _state(status),
                "domain": host,
                "index": index_id,
                "records": normalized,
                "record_count": len(normalized),
                "request_count": request_count,
                "retry_count": retry_count,
                "coverage": "bounded_url_index_sample",
            },
            warnings=warnings,
        )

    def _collect_pages(
        self, host: str, api: str, max_pages: int, page_size: int, warnings: list[str]
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        for page in range(max_pages):
            query = urllib.parse.urlencode(
                {
                    "url": f"{host}/*",
                    "output": "json",
                    "filter": "status:200",
                    "collapse": "urlkey",
                    "pageSize": page_size,
                    "page": page,
                }
            )
            text, _ = self.transport.get_text(f"{api}?{query}")
            page_records, parse_warnings = self._parse_records(text, page_size)
            warnings.extend(parse_warnings)
            collected.extend(page_records)
            if len(page_records) < page_size:
                break

        return collected


class BacklinkProfileService:
    FIELD_ALIASES = {
        "source_url": ("source_url", "referring_page", "referring_url", "source", "url_from"),
        "target_url": ("target_url", "destination_url", "target", "url_to"),
        "referring_domain": ("referring_domain", "source_domain", "domain"),
        "anchor": ("anchor", "anchor_text", "link_text"),
        "rel": ("rel", "link_rel", "nofollow"),
    }

    @classmethod
    def _value(cls, row: Mapping[str, Any], key: str) -> str:
        lower = {str(k).lower(): v for k, v in row.items()}
        for alias in cls.FIELD_ALIASES[key]:
            value = lower.get(alias)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    @classmethod
    def load_rows(cls, path: str | Path) -> list[dict[str, str]]:
        target = Path(path)
        text = _bounded_text(target)
        if target.suffix.lower() == ".json":
            payload = json.loads(text)
            if isinstance(payload, dict):
                payload = payload.get("rows", payload.get("backlinks", []))
            if not isinstance(payload, list):
                raise ValueError("JSON backlink input must be an array or contain rows/backlinks")
            raw_rows = [row for row in payload if isinstance(row, dict)]
        else:
            raw_rows = list(csv.DictReader(text.splitlines()))
        if len(raw_rows) > MAX_ROWS:
            raise ValueError(f"backlink input exceeds {MAX_ROWS} rows")
        normalized: list[dict[str, str]] = []
        for row in raw_rows:
            source = cls._value(row, "source_url")
            domain = cls._value(row, "referring_domain")
            if not domain and source:
                domain = (
                    urllib.parse.urlsplit(
                        source if "://" in source else f"https://{source}"
                    ).hostname
                    or ""
                )
            domain = domain.lower().rstrip(".")
            if not domain:
                continue
            normalized.append(
                {
                    "source_url": source,
                    "target_url": cls._value(row, "target_url"),
                    "referring_domain": domain,
                    "anchor": cls._value(row, "anchor") or "(empty)",
                    "rel": cls._value(row, "rel").lower(),
                }
            )
        return normalized

    def profile(self, path: str) -> AdapterResult:
        rows = self.load_rows(path)
        domains = sorted({row["referring_domain"] for row in rows})
        anchors = Counter(row["anchor"] for row in rows)
        targets = {row["target_url"] for row in rows if row["target_url"]}
        rel_counts = Counter(
            "nofollow"
            if "nofollow" in row["rel"] or row["rel"] in {"true", "1", "yes"}
            else "dofollow"
            if row["rel"]
            else "unknown"
            for row in rows
        )
        status = "ok" if rows else "empty"
        return AdapterResult(
            source=path,
            status=status,
            data={
                "data_state": _state(status),
                "backlink_count": len(rows),
                "referring_domain_count": len(domains),
                "unique_target_count": len(targets),
                "rel_counts": dict(rel_counts),
                "top_anchors": [
                    {"anchor": key, "count": count} for key, count in anchors.most_common(20)
                ],
                "referring_domains": domains,
                "quality_score": None,
            },
            warnings=[
                "This profile normalizes supplied records; it does not independently verify link existence or quality."
            ],
        )

    def gap(self, target_path: str, competitor_path: str) -> AdapterResult:
        target = self.load_rows(target_path)
        competitor = self.load_rows(competitor_path)
        target_domains = {row["referring_domain"] for row in target}
        competitor_by_domain: dict[str, list[str]] = {}
        for row in competitor:
            competitor_by_domain.setdefault(row["referring_domain"], [])
            if row["source_url"] and len(competitor_by_domain[row["referring_domain"]]) < 3:
                competitor_by_domain[row["referring_domain"]].append(row["source_url"])
        gaps = [
            {"referring_domain": domain, "sample_source_urls": competitor_by_domain[domain]}
            for domain in sorted(set(competitor_by_domain) - target_domains)
        ]
        status = "ok" if gaps else "empty"
        return AdapterResult(
            source=f"{target_path}|{competitor_path}",
            status=status,
            data={
                "data_state": _state(status),
                "target_referring_domains": len(target_domains),
                "competitor_referring_domains": len(competitor_by_domain),
                "gap_count": len(gaps),
                "gaps": gaps,
            },
            warnings=[
                "A domain gap is a prospecting lead, not proof that outreach is appropriate or that a link is obtainable."
            ],
        )


def _select_index(listing: list[Any], index: str | None) -> dict[str, Any] | None:
    selected = None
    for item in listing:
        if isinstance(item, dict) and (index is None or item.get("id") == index):
            selected = item
            break

    return selected
