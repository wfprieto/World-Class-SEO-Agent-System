"""Authority, media, provenance, and drift services with truthful evidence states."""

from __future__ import annotations

import csv
import json
import os
import re
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from adapters.base import AdapterResult
from adapters.evidence_store import canonicalize_url
from adapters.page_drift import PageDrift
from integrations.authority_media.transport import BoundedTransport

MAX_INPUT_BYTES = 10_000_000
MAX_ROWS = 100_000
IPTC_BASE = "http://cv.iptc.org/newscodes/digitalsourcetype/"
IPTC_LABELS = {
    "captured": "Captured by a camera",
    "compositeCapture": "Composite of captured elements",
    "algorithmicallyEnhanced": "Algorithmically-altered media",
    "dataDrivenMedia": "Data-driven media",
    "digitalCreation": "Digital creation",
    "trainedAlgorithmicMedia": "Created using Generative AI",
    "compositeWithTrainedAlgorithmicMedia": "Edited using Generative AI",
    "algorithmicMedia": "Pure algorithmic media",
    "screenCapture": "Screen capture",
    "virtualRecording": "Virtual event recording",
    "composite": "Composite of elements",
    "compositeSynthetic": "Composite including generative AI elements",
    "humanEdits": "Human-edited media",
}
IPTC_RETIRED = {"softwareImage", "digitalArt"}


def _bounded_text(path: str | Path) -> str:
    target = Path(path)
    size = target.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise ValueError(f"input exceeds {MAX_INPUT_BYTES} bytes")
    return target.read_text(encoding="utf-8-sig")


def _read_json(path: str | Path) -> Any:
    return json.loads(_bounded_text(path))


def _host(value: str) -> str:
    text = value.strip()
    parsed = urllib.parse.urlsplit(text if "://" in text else f"https://{text}")
    if parsed.username or parsed.password or not parsed.hostname:
        raise ValueError("domain must be a hostname or public URL without credentials")
    host = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
    if not host or "." not in host:
        raise ValueError("domain must contain a registrable hostname")
    return host


def _state(status: str) -> str:
    return {
        "ok": "AVAILABLE",
        "partial": "PARTIAL",
        "empty": "EMPTY",
        "not_configured": "NOT_CONFIGURED",
        "not_found": "NOT_FOUND",
        "invalid_response": "INVALID_RESPONSE",
        "blocked": "BLOCKED",
        "failed": "FAILED",
    }.get(status, status.upper())


class CommonCrawlService:
    """Bounded Common Crawl URL-index retrieval. This does not claim backlink coverage."""

    COLLINFO = "https://index.commoncrawl.org/collinfo.json"

    def __init__(self, transport: BoundedTransport | None = None) -> None:
        self.transport = transport or BoundedTransport({"index.commoncrawl.org"})

    @staticmethod
    def _parse_records(text: str, limit: int) -> tuple[list[dict[str, Any]], list[str]]:
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
                normalized_url = canonicalize_url(str(row["url"]))
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
                return AdapterResult("commoncrawl", "invalid_response", {"data_state": "INVALID_RESPONSE"}, warnings)
            selected = None
            for item in listing:
                if isinstance(item, dict) and (index is None or item.get("id") == index):
                    selected = item
                    break
            if not selected:
                return AdapterResult("commoncrawl", "not_found", {"data_state": "NOT_FOUND", "index": index}, warnings)
            api = str(selected.get("cdx-api") or "")
            parsed_api = urllib.parse.urlsplit(api)
            if parsed_api.scheme != "https" or parsed_api.hostname != "index.commoncrawl.org":
                return AdapterResult("commoncrawl", "invalid_response", {"data_state": "INVALID_RESPONSE"}, warnings)
            index_id = str(selected.get("id") or "unknown")
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
                domain = urllib.parse.urlsplit(source if "://" in source else f"https://{source}").hostname or ""
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
            "nofollow" if "nofollow" in row["rel"] or row["rel"] in {"true", "1", "yes"}
            else "dofollow" if row["rel"]
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
                "top_anchors": [{"anchor": key, "count": count} for key, count in anchors.most_common(20)],
                "referring_domains": domains,
                "quality_score": None,
            },
            warnings=["This profile normalizes supplied records; it does not independently verify link existence or quality."],
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
            warnings=["A domain gap is a prospecting lead, not proof that outreach is appropriate or that a link is obtainable."],
        )


class DomainHistoryService:
    BOOTSTRAP = "https://data.iana.org/rdap/dns.json"

    def __init__(self, bootstrap_transport: BoundedTransport | None = None) -> None:
        self.bootstrap_transport = bootstrap_transport or BoundedTransport({"data.iana.org"})

    @staticmethod
    def normalize(payload: Mapping[str, Any], domain: str, source: str) -> AdapterResult:
        events: dict[str, list[str]] = {}
        for item in payload.get("events", []) if isinstance(payload.get("events"), list) else []:
            if isinstance(item, dict) and item.get("eventAction") and item.get("eventDate"):
                events.setdefault(str(item["eventAction"]), []).append(str(item["eventDate"]))
        registrar = None
        for entity in payload.get("entities", []) if isinstance(payload.get("entities"), list) else []:
            if not isinstance(entity, dict) or "registrar" not in entity.get("roles", []):
                continue
            registrar = {"handle": entity.get("handle"), "public_ids": entity.get("publicIds", [])}
            break
        nameservers = []
        for item in payload.get("nameservers", []) if isinstance(payload.get("nameservers"), list) else []:
            if isinstance(item, dict) and item.get("ldhName"):
                nameservers.append(str(item["ldhName"]).lower())
        notices = [
            {"title": item.get("title"), "description": item.get("description")}
            for item in payload.get("notices", []) if isinstance(item, dict)
        ] if isinstance(payload.get("notices"), list) else []
        return AdapterResult(
            source=source,
            status="ok",
            data={
                "data_state": "AVAILABLE",
                "domain": str(payload.get("ldhName") or domain).lower(),
                "handle": payload.get("handle"),
                "status": payload.get("status", []),
                "events": events,
                "nameservers": nameservers,
                "secure_dns": payload.get("secureDNS"),
                "registrar": registrar,
                "notices": notices,
                "rdap_conformance": payload.get("rdapConformance", []),
                "ownership_inference": None,
            },
            warnings=[
                "RDAP registration data may be redacted, incomplete, delayed, or inconsistent across registries.",
                "Registrar and event data do not establish beneficial ownership or domain reputation."
            ],
        )

    def history(self, domain: str, *, fixture_path: str | None = None) -> AdapterResult:
        host = _host(domain)
        if fixture_path:
            payload = _read_json(fixture_path)
            if not isinstance(payload, dict):
                return AdapterResult(fixture_path, "invalid_response", {"data_state": "INVALID_RESPONSE"}, [])
            return self.normalize(payload, host, fixture_path)
        bootstrap, _ = self.bootstrap_transport.get_json(self.BOOTSTRAP)
        if not isinstance(bootstrap, dict) or not isinstance(bootstrap.get("services"), list):
            return AdapterResult("iana-rdap-bootstrap", "invalid_response", {"data_state": "INVALID_RESPONSE"}, [])
        tld = host.rsplit(".", 1)[-1]
        base = None
        for service in bootstrap["services"]:
            if not isinstance(service, list) or len(service) != 2:
                continue
            tlds, urls = service
            if isinstance(tlds, list) and tld in {str(item).lower() for item in tlds} and isinstance(urls, list):
                base = next((str(url) for url in urls if str(url).startswith("https://")), None)
                break
        if not base:
            return AdapterResult("iana-rdap-bootstrap", "not_found", {"data_state": "NOT_FOUND", "domain": host}, [])
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != "https" or not parsed.hostname:
            return AdapterResult("iana-rdap-bootstrap", "invalid_response", {"data_state": "INVALID_RESPONSE"}, [])
        endpoint = base.rstrip("/") + "/domain/" + urllib.parse.quote(host, safe="")
        transport = BoundedTransport({parsed.hostname})
        payload, response = transport.get_json(endpoint, accepted_statuses=frozenset({200, 404}))
        if response.status_code == 404:
            return AdapterResult(endpoint, "not_found", {"data_state": "NOT_FOUND", "domain": host}, [])
        if not isinstance(payload, dict):
            return AdapterResult(endpoint, "invalid_response", {"data_state": "INVALID_RESPONSE"}, [])
        result = self.normalize(payload, host, endpoint)
        result.data["request_count"] = self.bootstrap_transport.request_count + transport.request_count
        result.data["retry_count"] = self.bootstrap_transport.retry_count + transport.retry_count
        return result


class YouTubeSearchService:
    ENDPOINT = "https://www.googleapis.com/youtube/v3/search"

    def __init__(self, transport: BoundedTransport | None = None, api_key: str | None = None) -> None:
        self.transport = transport or BoundedTransport({"www.googleapis.com"})
        self.api_key = api_key if api_key is not None else os.environ.get("YOUTUBE_API_KEY")

    @staticmethod
    def normalize(payload: Mapping[str, Any], *, source: str, requests: int, retries: int) -> AdapterResult:
        rows = []
        for item in payload.get("items", []) if isinstance(payload.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            identifier = item.get("id") if isinstance(item.get("id"), dict) else {}
            snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
            video_id = identifier.get("videoId")
            if not video_id:
                continue
            rows.append(
                {
                    "video_id": video_id,
                    "title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "channel_id": snippet.get("channelId"),
                    "channel_title": snippet.get("channelTitle"),
                    "published_at": snippet.get("publishedAt"),
                    "live_broadcast_content": snippet.get("liveBroadcastContent"),
                    "thumbnails": snippet.get("thumbnails", {}),
                }
            )
        status = "ok" if rows else "empty"
        page_info = payload.get("pageInfo") if isinstance(payload.get("pageInfo"), dict) else {}
        return AdapterResult(
            source=source,
            status=status,
            data={
                "data_state": _state(status),
                "results": rows,
                "result_count": len(rows),
                "next_page_token": payload.get("nextPageToken"),
                "region_code": payload.get("regionCode"),
                "provider_total_results_approximate": page_info.get("totalResults"),
                "request_count": requests,
                "retry_count": retries,
                "quota_units_estimated": requests,
                "quota_bucket": "search.list",
            },
            warnings=["YouTube pageInfo.totalResults is approximate and must not be used as an exact inventory count."],
        )

    def search(
        self,
        query: str,
        *,
        fixture_path: str | None = None,
        max_results: int = 25,
        pages: int = 1,
        region_code: str | None = None,
        relevance_language: str | None = None,
        order: str = "relevance",
        safe_search: str = "moderate",
    ) -> AdapterResult:
        if not query.strip() or len(query) > 500:
            raise ValueError("query must contain 1 to 500 characters")
        if not 1 <= max_results <= 50:
            raise ValueError("max_results must be from 1 to 50")
        if not 1 <= pages <= 3:
            raise ValueError("pages must be from 1 to 3")
        if fixture_path:
            payload = _read_json(fixture_path)
            if not isinstance(payload, dict):
                return AdapterResult(fixture_path, "invalid_response", {"data_state": "INVALID_RESPONSE"}, [])
            return self.normalize(payload, source=fixture_path, requests=0, retries=0)
        if not self.api_key:
            return AdapterResult("youtube", "not_configured", {"data_state": "NOT_CONFIGURED"}, ["Set YOUTUBE_API_KEY to enable live search."])
        all_items: list[dict[str, Any]] = []
        token = None
        last_payload: dict[str, Any] = {}
        for _ in range(pages):
            params = {
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": max_results,
                "order": order,
                "safeSearch": safe_search,
            }
            if token:
                params["pageToken"] = token
            if region_code:
                params["regionCode"] = region_code
            if relevance_language:
                params["relevanceLanguage"] = relevance_language
            url = self.ENDPOINT + "?" + urllib.parse.urlencode(params)
            payload, _ = self.transport.get_json(url, headers={"X-Goog-Api-Key": self.api_key})
            if not isinstance(payload, dict):
                return AdapterResult("youtube", "invalid_response", {"data_state": "INVALID_RESPONSE"}, [])
            last_payload = dict(payload)
            items = payload.get("items", [])
            if isinstance(items, list):
                all_items.extend(item for item in items if isinstance(item, dict))
            token = payload.get("nextPageToken")
            if not token:
                break
        last_payload["items"] = all_items
        return self.normalize(
            last_payload,
            source=self.ENDPOINT,
            requests=self.transport.request_count,
            retries=self.transport.retry_count,
        )


class IPTCLabelService:
    @staticmethod
    def _extract(payload: Mapping[str, Any]) -> list[str]:
        candidates = []
        for key in ("digital_source_type", "DigitalSourceType", "digitalSourceType"):
            value = payload.get(key)
            if isinstance(value, str):
                candidates.append(value)
            elif isinstance(value, list):
                candidates.extend(str(item) for item in value)
        return candidates

    def inspect(
        self,
        input_path: str,
        *,
        label: str | None = None,
        write: bool = False,
        authorize_write: bool = False,
        output_path: str | None = None,
    ) -> AdapterResult:
        payload = _read_json(input_path)
        if not isinstance(payload, dict):
            return AdapterResult(input_path, "invalid_response", {"data_state": "INVALID_RESPONSE"}, [])
        observed = self._extract(payload)
        normalized = []
        invalid = []
        retired = []
        for value in observed:
            token = value.rsplit("/", 1)[-1].split(":")[-1]
            if token in IPTC_RETIRED:
                retired.append(value)
            elif token in IPTC_LABELS:
                normalized.append(IPTC_BASE + token)
            else:
                invalid.append(value)
        requested_uri = None
        if label:
            token = label.rsplit("/", 1)[-1].split(":")[-1]
            if token in IPTC_RETIRED:
                retired.append(label)
            elif token not in IPTC_LABELS:
                invalid.append(label)
            else:
                requested_uri = IPTC_BASE + token
        if write and not authorize_write:
            return AdapterResult(input_path, "blocked", {"data_state": "BLOCKED", "reason": "explicit_write_authorization_required"}, [])
        if write and not output_path:
            raise ValueError("--output is required when --write is used")
        written = None
        if write:
            if invalid or retired or not requested_uri:
                return AdapterResult(input_path, "invalid_response", {"data_state": "INVALID_RESPONSE", "invalid": invalid, "retired": retired}, [])
            sidecar = dict(payload)
            sidecar["digital_source_type"] = requested_uri
            target = Path(str(output_path))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            written = str(target)
        status = "invalid_response" if invalid or retired else "ok"
        return AdapterResult(
            source=input_path,
            status=status,
            data={
                "data_state": _state(status),
                "observed": normalized,
                "requested": requested_uri,
                "invalid": invalid,
                "retired": retired,
                "written_sidecar": written,
                "source_mutated": False,
                "rollback": f"Delete {written}" if written else None,
            },
            warnings=["This command validates or writes a JSON sidecar only; it does not modify binary media metadata."],
        )


class TranscriptService:
    TIMESTAMP = re.compile(r"(?:\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->")

    def check(self, input_path: str, *, video_id: str | None = None) -> AdapterResult:
        text = _bounded_text(input_path)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        caption_lines = [
            line for line in lines
            if not self.TIMESTAMP.search(line) and not line.isdigit() and line.upper() not in {"WEBVTT", "NOTE"}
        ]
        words = re.findall(r"\b[\w'-]+\b", " ".join(caption_lines), flags=re.UNICODE)
        repeated = [line for line, count in Counter(caption_lines).items() if count >= 3 and len(line) > 8]
        issues = []
        if not self.TIMESTAMP.search(text):
            issues.append({"code": "NO_TIMESTAMPS", "severity": "warning"})
        if len(words) < 50:
            issues.append({"code": "VERY_SHORT_TRANSCRIPT", "severity": "warning"})
        if any(len(line) > 160 for line in caption_lines):
            issues.append({"code": "LONG_CAPTION_LINES", "severity": "info"})
        if repeated:
            issues.append({"code": "REPEATED_SEGMENTS", "severity": "warning", "examples": repeated[:5]})
        placeholders = [token for token in ("[music]", "[inaudible]", "[applause]") if token in text.lower()]
        status = "ok" if caption_lines else "empty"
        return AdapterResult(
            source=input_path,
            status=status,
            data={
                "data_state": _state(status),
                "video_id": video_id,
                "word_count": len(words),
                "caption_line_count": len(caption_lines),
                "timestamp_evidence": bool(self.TIMESTAMP.search(text)),
                "placeholder_markers": placeholders,
                "issues": issues,
                "semantic_accuracy_verified": False,
            },
            warnings=["Structural transcript checks do not verify spoken-word accuracy, speaker identity, or legal accessibility compliance."],
        )


class DriftService:
    ALLOWED_FIELDS = {"title", "canonical", "robots", "h1", "status_code", "html", "schema_json"}

    @classmethod
    def _state_file(cls, path: str) -> dict[str, Any]:
        payload = _read_json(path)
        if not isinstance(payload, dict):
            raise ValueError("state file must contain a JSON object")
        unknown = sorted(set(payload) - cls.ALLOWED_FIELDS)
        if unknown:
            raise ValueError("unsupported state fields: " + ", ".join(unknown))
        return payload

    def baseline(self, url: str, state_path: str, *, db_path: str | None = None) -> AdapterResult:
        fields = self._state_file(state_path)
        with PageDrift(db_path) as drift:
            snapshot_id = drift.capture(url, fields, source=state_path, status="ok")
        return AdapterResult(
            source=state_path,
            status="ok",
            data={"data_state": "AVAILABLE", "url": canonicalize_url(url), "snapshot_id": snapshot_id, "action": "baseline_recorded"},
            warnings=[],
        )

    def compare(self, url: str, *, db_path: str | None = None) -> AdapterResult:
        with PageDrift(db_path) as drift:
            result = drift.compare(url)
        status = "ok" if result.get("status") == "ok" else "partial"
        return AdapterResult("evidence_store", status, {"data_state": _state(status), **result}, [])

    def history(self, url: str, *, db_path: str | None = None, limit: int = 20) -> AdapterResult:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be from 1 to 1000")
        with PageDrift(db_path) as drift:
            rows = drift.history(url, limit=limit)
        status = "ok" if rows else "empty"
        return AdapterResult("evidence_store", status, {"data_state": _state(status), "url": canonicalize_url(url), "history": rows, "count": len(rows)}, [])

    def report(self, url: str, *, db_path: str | None = None, output_path: str | None = None) -> AdapterResult:
        result = self.compare(url, db_path=db_path)
        written = None
        if output_path:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result.data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            written = str(target)
        result.data["report_path"] = written
        result.warnings.append("The report reflects only stored snapshots and is not an ongoing monitor.")
        return result

    def watch(self, url: str, state_path: str, *, db_path: str | None = None) -> AdapterResult:
        fields = self._state_file(state_path)
        with PageDrift(db_path) as drift:
            snapshot_id = drift.capture(url, fields, source=state_path, status="ok")
            result = drift.compare(url)
        status = "ok" if result.get("status") == "ok" else "partial"
        return AdapterResult(
            source=state_path,
            status=status,
            data={"data_state": _state(status), "snapshot_id": snapshot_id, "one_shot": True, **result},
            warnings=["drift watch performs one bounded capture-and-compare; it does not create a background schedule."],
        )
