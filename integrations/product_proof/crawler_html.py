"""HTML collection state for canonical product-proof page evidence."""
from __future__ import annotations

from html.parser import HTMLParser


class _HTMLAuditParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1: list[str] = []
        self.links: list[dict[str, str]] = []
        self.metas: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.assets: list[str] = []
        self.jsonld_parts: list[str] | None = None
        self.jsonld_payloads: list[str] = []
        self.text_parts: list[str] = []
        self.data_nosnippet_count = 0
        self._in_title = False
        self._in_h1 = False
        self._h1_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        lower = tag.lower()
        if "data-nosnippet" in values:
            self.data_nosnippet_count += 1
        if lower == "title":
            self._in_title = True
        elif lower == "h1":
            self._in_h1 = True
            self._h1_parts = []
        elif lower == "a":
            self.links.append(values)
        elif lower == "link":
            self.links.append(values)
            if values.get("href"):
                self.assets.append(values["href"])
        elif lower == "meta":
            self.metas.append(values)
        elif lower == "img":
            self._capture_image(values)
        elif lower in {"script", "source", "video", "audio", "iframe"}:
            self._capture_media(lower, values)

    def _capture_image(self, values: dict[str, str]) -> None:
        self.images.append(values)
        if values.get("src"):
            self.assets.append(values["src"])
        if values.get("srcset"):
            for part in values["srcset"].split(","):
                candidate = part.strip().split(" ", 1)[0]
                if candidate:
                    self.assets.append(candidate)

    def _capture_media(self, lower: str, values: dict[str, str]) -> None:
        media_candidate: str | None = values.get("src") or values.get("poster")
        if media_candidate:
            self.assets.append(media_candidate)
        if (
            lower == "script"
            and values.get("type", "").lower().split(";", 1)[0].strip() == "application/ld+json"
        ):
            self.jsonld_parts = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        self.text_parts.append(text)
        if self._in_title:
            self.title_parts.append(text)
        if self._in_h1:
            self._h1_parts.append(text)
        if self.jsonld_parts is not None:
            self.jsonld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower == "title":
            self._in_title = False
        elif lower == "h1":
            self._in_h1 = False
            value = " ".join(self._h1_parts).strip()
            if value:
                self.h1.append(value)
            self._h1_parts = []
        elif lower == "script" and self.jsonld_parts is not None:
            value = "".join(self.jsonld_parts).strip()
            if value:
                self.jsonld_payloads.append(value)
            self.jsonld_parts = None
