"""Google first-party SEO and analytics integrations."""

from .client import GoogleAPIError, GoogleJsonClient, GoogleOAuthProvider
from .crux import CrUXCurrentAdapter, CrUXHistoryAdapter, decompose_lcp_history
from .ga4 import GoogleAnalyticsDataAdapter
from .gsc import GoogleSearchConsoleAdapter
from .sitemaps import GoogleSitemapsAdapter

__all__ = [
    "CrUXCurrentAdapter",
    "CrUXHistoryAdapter",
    "GoogleAPIError",
    "GoogleAnalyticsDataAdapter",
    "GoogleJsonClient",
    "GoogleOAuthProvider",
    "GoogleSearchConsoleAdapter",
    "GoogleSitemapsAdapter",
    "decompose_lcp_history",
]
