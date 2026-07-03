"""Google Search Console live OAuth2 adapter example.

This file shows the exact production pattern without storing secrets. It is
safe to commit because credentials are read from environment variables.

Required environment variables:
- GSC_CLIENT_ID
- GSC_CLIENT_SECRET
- GSC_REFRESH_TOKEN

Optional:
- GSC_TOKEN_URI defaults to https://oauth2.googleapis.com/token

Google Search Console API access to user data uses OAuth 2.0.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

from adapters.base import AdapterNotConfigured, AdapterResult


class GSCLiveExampleAdapter:
    name = "gsc_live_example"

    SEARCH_ANALYTICS_URL = "https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"

    def fetch(
        self,
        site_url: str,
        start_date: str | None = None,
        end_date: str | None = None,
        dimensions: list[str] | None = None,
        row_limit: int = 1000,
        **_: Any,
    ) -> AdapterResult:
        token = self._access_token()
        end = end_date or (date.today() - timedelta(days=3)).isoformat()
        start = start_date or (date.today() - timedelta(days=31)).isoformat()
        payload = {
            "startDate": start,
            "endDate": end,
            "dimensions": dimensions or ["page", "query"],
            "rowLimit": row_limit,
        }
        quoted_site = urllib.parse.quote(site_url, safe="")
        url = self.SEARCH_ANALYTICS_URL.format(site_url=quoted_site)
        data = self._post_json(url, payload, {"Authorization": f"Bearer {token}"})
        rows = data.get("rows", [])
        clicks = sum(int(row.get("clicks", 0)) for row in rows)
        impressions = sum(int(row.get("impressions", 0)) for row in rows)
        return AdapterResult(
            source=site_url,
            status="ok",
            data={
                "row_count": len(rows),
                "clicks": clicks,
                "impressions": impressions,
                "date_range": {"start": start, "end": end},
                "dimensions": payload["dimensions"],
            },
            warnings=[],
        )

    def _access_token(self) -> str:
        client_id = os.getenv("GSC_CLIENT_ID")
        client_secret = os.getenv("GSC_CLIENT_SECRET")
        refresh_token = os.getenv("GSC_REFRESH_TOKEN")
        token_uri = os.getenv("GSC_TOKEN_URI", "https://oauth2.googleapis.com/token")
        if not all([client_id, client_secret, refresh_token]):
            raise AdapterNotConfigured("Set GSC_CLIENT_ID, GSC_CLIENT_SECRET and GSC_REFRESH_TOKEN.")
        form = urllib.parse.urlencode(
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            token_uri,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token = payload.get("access_token")
        if not token:
            raise AdapterNotConfigured("OAuth token response did not include access_token.")
        return token

    @staticmethod
    def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
