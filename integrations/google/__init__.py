"""Google first-party SEO and analytics integrations."""

from .client import GoogleAPIError, GoogleJsonClient, GoogleOAuthProvider
from .crux import CrUXHistoryAdapter, decompose_lcp_history
from .ga4 import GoogleAnalyticsDataAdapter
from .gsc import GoogleSearchConsoleAdapter

__all__ = [
    "CrUXHistoryAdapter",
    "GoogleAPIError",
    "GoogleAnalyticsDataAdapter",
    "GoogleJsonClient",
    "GoogleOAuthProvider",
    "GoogleSearchConsoleAdapter",
    "decompose_lcp_history",
]
