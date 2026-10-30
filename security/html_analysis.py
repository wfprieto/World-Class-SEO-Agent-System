"""Single-pass HTML facts without suffix-scanning markup regular expressions."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_RAW_START = re.compile(r'<(script|style)(?:\s|>|/>)', re.IGNORECASE)
_RAW_END = {tag: re.compile(r'</\s*' + tag + r'\s*>', re.IGNORECASE)
            for tag in ('script', 'style')}


class HTMLFacts(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.image_count = 0
        self.missing_alt_count = 0
        self.h1_count = 0
        self._script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'script':
            self._script = True
        elif tag == 'img':
            self.image_count += 1
            self.missing_alt_count += not any(name == 'alt' for name, _ in attrs)
        elif tag == 'h1':
            self.h1_count += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script':
            self._script = False

    def handle_data(self, data: str) -> None:
        if not self._script:
            self.text.append(data)


def _tag_end(text: str, start: int) -> int:
    quote = ''
    for index in range(start + 1, len(text)):
        char = text[index]
        if index - start > 65_536:
            raise ValueError('HTML tag exceeds the analysis character ceiling')
        if quote:
            if char == quote:
                quote = ''
        elif char in {'"', "'"}:
            quote = char
        elif char == '>':
            return index + 1
    return len(text)


def validate_html_work(text: str) -> None:
    if len(text) > 12_000_000:
        raise ValueError('HTML exceeds the analysis character ceiling')
    cursor = 0
    while (start := text.find('<', cursor)) >= 0:
        cursor = _tag_end(text, start)
        raw = _RAW_START.match(text, start)
        if raw and not text[start:cursor].rstrip().endswith('/>'):
            closing = _RAW_END[raw.group(1).lower()].search(text, cursor)
            cursor = closing.end() if closing else len(text)


def html_facts(text: str) -> HTMLFacts:
    validate_html_work(text)
    facts = HTMLFacts()
    facts.feed(text)
    facts.close()
    return facts
