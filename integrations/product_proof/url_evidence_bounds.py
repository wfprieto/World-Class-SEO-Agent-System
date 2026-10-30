"""Fail-closed URL expansion budgets shared by every crawl evidence field."""

from __future__ import annotations

import urllib.parse
from collections.abc import Callable
from typing import Any

MAX_URL_CHARS = 8_192
PAGE_URL_CHARS = 2_000_000
CRAWL_URL_CHARS = 20_000_000


def check_url_length(value: str) -> None:
    if len(value) > MAX_URL_CHARS:
        raise ValueError('URL evidence exceeds the per-URL character ceiling')


class URLBudget:
    def __init__(self, maximum: int = PAGE_URL_CHARS, parent: URLBudget | None = None) -> None:
        self.maximum = maximum
        self.used = 0
        self.parent = parent

    def reserve(self, size: int) -> None:
        if self.used + size > self.maximum:
            raise ValueError('URL evidence exceeds the aggregate character ceiling')
        if self.parent is not None:
            self.parent.reserve(size)
        self.used += size

    def expand(self, base: str, value: str, normalize: Callable[[str], str]) -> str:
        check_url_length(base)
        check_url_length(value)
        # Charge before urljoin allocates. One URL may be retained as navigation,
        # canonical, next and previous evidence; count all four representations.
        self.reserve(4 * (len(base) + len(value) + 1))
        absolute = urllib.parse.urljoin(base, value)
        check_url_length(absolute)
        normalized = normalize(absolute)
        check_url_length(normalized)
        return normalized


def extract_media_evidence(assets: list[str], images: list[dict[str, str]], base: str,
                           normalize: Callable[[str], str], budget: URLBudget
                           ) -> tuple[list[str], list[dict[str, Any]]]:
    expanded = {budget.expand(base, value, normalize) for value in assets}
    asset_urls = sorted(value for value in expanded
                        if urllib.parse.urlsplit(value).scheme in {'http', 'https'})
    image_rows = []
    for index, image in enumerate(images):
        src = image.get('src', '').strip()
        image_rows.append({'src': budget.expand(base, src, normalize) if src else None,
                           'loading': image.get('loading') or None,
                           'fetchpriority': image.get('fetchpriority') or None,
                           'width': image.get('width') or None, 'height': image.get('height') or None,
                           'alt_present': 'alt' in image, 'position': index})
    return asset_urls, image_rows


def crawl_data_state(pages: list[Any], failed: list[Any], queue: Any) -> str:
    if failed or queue:
        return 'PARTIAL'
    return 'AVAILABLE' if pages else 'EMPTY'
