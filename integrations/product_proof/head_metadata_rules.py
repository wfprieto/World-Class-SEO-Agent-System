"""Head metadata audit rules for product-proof crawl evidence."""
from __future__ import annotations

from collections import Counter
from typing import Any, Protocol

Page = dict[str, Any]


class RuleSink(Protocol):
    def add(
        self,
        i: str,
        t: str,
        s: str,
        cat: str,
        claims: list[str],
        obs: str,
        impact: str,
        action: str,
        verify: str,
        urls: list[str],
        owner: str,
        state: str = "VERIFIED",
        confidence: str = "High",
        missing: list[str] | None = None,
    ) -> None: ...

    @staticmethod
    def dirs(p: Page) -> set[str]: ...


GENERIC_TITLES = {"home", "homepage", "untitled", "index", "page", "new page"}


def _html_pages(crawl: dict[str, Any]) -> list[Page]:
    return [
        page
        for page in crawl["pages"]
        if 200 <= page["status_code"] < 300
        and str(page.get("content_type") or "").lower().startswith("text/html")
    ]


def _indexable_html(rules: RuleSink, crawl: dict[str, Any]) -> list[Page]:
    return [page for page in _html_pages(crawl) if "noindex" not in rules.dirs(page)]


def _duplicate_urls(rows: list[Page], key: str) -> list[str]:
    values = Counter(str(row.get(key) or "").strip().lower() for row in rows if row.get(key))
    return [
        row["final_url"]
        for row in rows
        if row.get(key) and values[str(row[key]).strip().lower()] > 1
    ]


def _urls_missing(rows: list[Page], key: str) -> list[str]:
    return [row["final_url"] for row in rows if not row.get(key)]


def _urls_with(rows: list[Page], key: str) -> list[str]:
    return [row["final_url"] for row in rows if row.get(key)]


def apply_head_metadata_rules(rules: RuleSink, crawl: dict[str, Any]) -> None:
    html = _html_pages(crawl)
    indexable = _indexable_html(rules, crawl)
    _apply_title_rules(rules, indexable)
    _apply_description_rules(rules, indexable)
    _apply_technical_head_rules(rules, html, indexable)
    _apply_social_rules(rules, indexable)


def _apply_title_rules(rules: RuleSink, indexable: list[Page]) -> None:
    missing_title = _urls_missing(indexable, "title")
    if missing_title:
        rules.add("head-title-missing", "Indexable HTML pages are missing title elements", "High", "Head Metadata", [], f"{len(missing_title)} indexable page(s) have no title.", "Missing titles reduce result clarity, browser context, and page identification.", "Add unique, descriptive title elements that match page purpose.", "Recrawl representative templates and inspect rendered head.", missing_title, "SEO Technical Agent")

    generic = [
        page["final_url"]
        for page in indexable
        if str(page.get("title") or "").strip().lower() in GENERIC_TITLES
    ]
    if generic:
        rules.add("head-title-generic", "Indexable HTML pages use generic title elements", "Medium", "Head Metadata", [], f"{len(generic)} indexable page(s) use generic titles.", "Generic titles weaken differentiation and make template defects harder to spot.", "Write page-specific titles tied to the primary entity, offer, or task.", "Recrawl titles and confirm uniqueness.", generic, "SEO Copywriter/Content Agent")

    duplicate_titles = _duplicate_urls(indexable, "title")
    if duplicate_titles:
        rules.add("head-title-duplicated", "Multiple indexable pages share the same title element", "Medium", "Head Metadata", [], f"{len(set(duplicate_titles))} page(s) share duplicate titles.", "Duplicate titles obscure page purpose and can indicate template-level metadata drift.", "Create page-specific title patterns for each template and canonical intent.", "Recrawl and compare title clusters.", duplicate_titles, "SEO Copywriter/Content Agent")


def _apply_description_rules(rules: RuleSink, indexable: list[Page]) -> None:
    missing_desc = _urls_missing(indexable, "meta_description")
    if missing_desc:
        rules.add("meta-description-missing", "Indexable HTML pages are missing meta descriptions", "Medium", "Head Metadata", [], f"{len(missing_desc)} indexable page(s) have no meta description.", "Missing descriptions reduce control over human-readable snippets, even though snippets are not guaranteed.", "Add concise, page-specific descriptions that reflect visible content and intent.", "Recrawl and inspect rendered head.", missing_desc, "SEO Copywriter/Content Agent")

    duplicate_desc = _duplicate_urls(indexable, "meta_description")
    if duplicate_desc:
        rules.add("meta-description-duplicated", "Multiple indexable pages share the same meta description", "Low", "Head Metadata", [], f"{len(set(duplicate_desc))} page(s) share duplicate descriptions.", "Duplicate descriptions usually indicate generic template copy rather than page-specific intent.", "Write descriptions from page-specific evidence and buyer language.", "Recrawl and compare description clusters.", duplicate_desc, "SEO Copywriter/Content Agent")


def _apply_technical_head_rules(
    rules: RuleSink,
    html: list[Page],
    indexable: list[Page],
) -> None:
    no_viewport = _urls_missing(html, "viewport")
    if no_viewport:
        rules.add("viewport-missing", "HTML pages are missing a viewport declaration", "High", "Head Metadata", [], f"{len(no_viewport)} HTML page(s) lack viewport metadata.", "Mobile rendering can be unreliable, affecting usability and search quality diagnostics.", "Add a standard responsive viewport declaration unless the framework already injects one at render time.", "Render mobile and inspect the final head.", no_viewport, "Senior SEO Engineer Agent")

    no_charset = _urls_missing(html, "charset")
    if no_charset:
        rules.add("charset-missing", "HTML pages do not expose a detectable charset", "Medium", "Head Metadata", [], f"{len(no_charset)} HTML page(s) lack a detectable charset.", "Character decoding can become inconsistent across clients and crawlers.", "Declare charset in HTTP headers or early HTML head.", "Fetch and inspect response headers and rendered head.", no_charset, "Senior SEO Engineer Agent")

    missing_canonical = _urls_missing(indexable, "canonical")
    if missing_canonical:
        rules.add("canonical-missing", "Indexable HTML pages are missing canonical annotations", "Medium", "Head Metadata", ["canonical-strength"], f"{len(missing_canonical)} page(s) lack canonical annotations.", "Canonical absence may be acceptable on simple sites, but weakens duplicate-management visibility at scale.", "Add self-canonicals or document why canonical annotations are unnecessary.", "Recrawl and inspect canonical targets.", missing_canonical, "SEO Technical Agent", "STRONGLY_SUPPORTED", "Medium")

    deprecated = _urls_with(html, "deprecated_meta")
    if deprecated:
        rules.add("deprecated-head-metadata", "HTML pages contain deprecated or low-value head metadata", "Low", "Head Metadata", [], f"{len(deprecated)} page(s) contain deprecated metadata fields.", "Deprecated metadata creates noise and can mislead teams into maintaining ineffective controls.", "Remove low-value legacy tags unless a documented non-search system needs them.", "Inspect final head after template cleanup.", deprecated, "Senior SEO Engineer Agent")


def _apply_social_rules(rules: RuleSink, indexable: list[Page]) -> None:
    social = [
        page["final_url"]
        for page in indexable
        if page.get("title")
        and not {"og:title", "og:description"}.issubset(set(page.get("open_graph_tags", [])))
    ]
    if social:
        rules.add("social-metadata-incomplete", "Indexable pages have incomplete Open Graph metadata", "Low", "Head Metadata", [], f"{len(social)} page(s) lack complete Open Graph title and description metadata.", "Social sharing previews and downstream previews may be generic or incorrect.", "Add Open Graph metadata where sharing matters; keep it aligned with visible content.", "Inspect final head and preview output.", social, "SEO Copywriter/Content Agent")
