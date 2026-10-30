"""Bound report branding to inert standalone CSS color syntax."""

from __future__ import annotations

import re

_COLOR = re.compile(
    r"(?:\#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})|"
    r"[a-z]{1,32}|(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)"
    r"\([a-z0-9.,%+\-/ \t]{1,80}\))",
    re.IGNORECASE,
)


def validate_brand(value: str) -> str:
    """Accept bounded color literals, never CSS declarations or resource syntax."""
    if not isinstance(value, str) or len(value) > 96:
        raise ValueError("brand must be a bounded standalone CSS color")
    color = value.strip()
    if not _COLOR.fullmatch(color):
        raise ValueError("brand must be a bounded standalone CSS color")
    return color
