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

import urllib.parse
from datetime import date, timedelta
from typing import Any

from adapters.base import AdapterNotConfigured, AdapterResult
from integrations.google.client import (
    GoogleAPIError,
    GoogleJsonClient,
    GoogleOAuthConfig,
    GoogleOAuthProvider,
)


class GSCLiveExampleAdapter:
    name = "gsc_live_example"

    SEARCH_ANALYTICS_URL = "https://www.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"

    def __init__(
        self,
        *,
        oauth: GoogleOAuthProvider | None = None,
        client: GoogleJsonClient | None = None,
    ) -> None:
        self.oauth = oauth or GoogleOAuthProvider(GoogleOAuthConfig.from_env("GSC"))
        self.client = client or GoogleJsonClient(allowed_hosts={"www.googleapis.com"})

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
        try:
            return self.oauth.token()
        except GoogleAPIError as exc:
            if exc.state == "NOT_CONFIGURED":
                raise AdapterNotConfigured(
                    "Set GSC_CLIENT_ID, GSC_CLIENT_SECRET and GSC_REFRESH_TOKEN."
                ) from exc
            raise

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        authorization = headers.get("Authorization", "")
        scheme, _, access_token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not access_token:
            raise GoogleAPIError("gsc", None, "missing bearer token", state="BLOCKED")
        return self.client.request(
            url,
            service="gsc",
            method="POST",
            payload=payload,
            access_token=access_token,
        )
