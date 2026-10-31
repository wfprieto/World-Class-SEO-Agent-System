"""Cohesive YouTubeSearchService operations with bounded evidence states."""

from __future__ import annotations

import os
import urllib.parse
from collections.abc import Mapping
from typing import Any

from contracts.adapter import AdapterResult
from integrations.authority_media.input_data import (
    _read_json,
    _state,
)
from integrations.authority_media.transport import BoundedTransport


class YouTubeSearchService:
    ENDPOINT = "https://www.googleapis.com/youtube/v3/search"

    def __init__(
        self, transport: BoundedTransport | None = None, api_key: str | None = None
    ) -> None:
        self.transport = transport or BoundedTransport({"www.googleapis.com"})
        self.api_key = api_key if api_key is not None else os.environ.get("YOUTUBE_API_KEY")

    @staticmethod
    def normalize(
        payload: Mapping[str, Any], *, source: str, requests: int, retries: int
    ) -> AdapterResult:
        rows = []
        for item in payload.get("items", []) if isinstance(payload.get("items"), list) else []:
            if not isinstance(item, dict):
                continue
            raw_identifier = item.get("id")
            identifier: dict[str, Any] = raw_identifier if isinstance(raw_identifier, dict) else {}
            raw_snippet = item.get("snippet")
            snippet: dict[str, Any] = raw_snippet if isinstance(raw_snippet, dict) else {}
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
        raw_page_info = payload.get("pageInfo")
        page_info: dict[str, Any] = raw_page_info if isinstance(raw_page_info, dict) else {}
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
            warnings=[
                "YouTube pageInfo.totalResults is approximate and must not be used as an exact inventory count."
            ],
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
        _validate_search(query, max_results, pages)
        if fixture_path:
            payload = _read_json(fixture_path)
            if not isinstance(payload, dict):
                return AdapterResult(
                    fixture_path, "invalid_response", {"data_state": "INVALID_RESPONSE"}, []
                )
            return self.normalize(payload, source=fixture_path, requests=0, retries=0)
        if not self.api_key:
            return AdapterResult(
                "youtube",
                "not_configured",
                {"data_state": "NOT_CONFIGURED"},
                ["Set YOUTUBE_API_KEY to enable live search."],
            )
        all_items: list[dict[str, Any]] = []
        token = None
        last_payload: dict[str, Any] = {}
        for _ in range(pages):
            params = _search_parameters(
                query, max_results, order, safe_search, token, region_code, relevance_language
            )
            url = self.ENDPOINT + "?" + urllib.parse.urlencode(params)
            payload, _ = self.transport.get_json(url, headers={"X-Goog-Api-Key": self.api_key})
            if not isinstance(payload, dict):
                return AdapterResult(
                    "youtube", "invalid_response", {"data_state": "INVALID_RESPONSE"}, []
                )
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


def _validate_search(query: str, max_results: int, pages: int) -> None:
    if not query.strip() or len(query) > 500:
        raise ValueError("query must contain 1 to 500 characters")
    if not 1 <= max_results <= 50:
        raise ValueError("max_results must be from 1 to 50")
    if not 1 <= pages <= 3:
        raise ValueError("pages must be from 1 to 3")


def _search_parameters(
    query: str,
    max_results: int,
    order: str,
    safe_search: str,
    token: str | None,
    region_code: str | None,
    relevance_language: str | None,
) -> dict[str, str | int]:
    params: dict[str, str | int] = {
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

    return params
