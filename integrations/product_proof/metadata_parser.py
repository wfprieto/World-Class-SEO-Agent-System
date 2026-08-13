"""Extract rendered head metadata from parsed HTML evidence."""
from __future__ import annotations

import re
from typing import TypedDict

DEPRECATED_META_NAMES = {"keywords", "revisit-after", "rating", "distribution", "expires"}


class HeadMetadata(TypedDict):
    meta_description: str | None
    viewport: str | None
    charset: str | None
    open_graph_tags: list[str]
    twitter_tags: list[str]
    deprecated_meta: list[str]


def extract_head_metadata(
    metas: list[dict[str, str]],
    content_type: str | None,
) -> HeadMetadata:
    meta_description: str | None = None
    viewport: str | None = None
    charset_meta: str | None = None
    open_graph_tags: set[str] = set()
    twitter_tags: set[str] = set()
    deprecated_meta: set[str] = set()

    for meta in metas:
        name = meta.get("name", "").lower()
        prop = meta.get("property", "").lower()
        content = meta.get("content", "")
        if name == "description" and meta_description is None:
            meta_description = content.strip() or None
        if name == "viewport" and viewport is None:
            viewport = content.strip() or None
        if meta.get("charset") and charset_meta is None:
            charset_meta = meta["charset"].strip() or None
        if prop.startswith("og:"):
            open_graph_tags.add(prop)
        if name.startswith("twitter:"):
            twitter_tags.add(name)
        if name in DEPRECATED_META_NAMES:
            deprecated_meta.add(name)

    return {
        "meta_description": meta_description,
        "viewport": viewport,
        "charset": charset_meta or _charset_from_content_type(content_type),
        "open_graph_tags": sorted(open_graph_tags),
        "twitter_tags": sorted(twitter_tags),
        "deprecated_meta": sorted(deprecated_meta),
    }


def extract_robot_directives(metas: list[dict[str, str]]) -> list[str]:
    values: list[str] = []
    for meta in metas:
        if meta.get("name", "").lower() in {"robots", "googlebot"}:
            values.extend(
                token.strip().lower()
                for token in meta.get("content", "").split(",")
                if token.strip()
            )
    return values


def _charset_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, re.I)
    return match.group(1) if match else None
