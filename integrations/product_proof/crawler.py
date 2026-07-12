"""Bounded same-host crawler and Google robots.txt evaluator.

The crawler creates one canonical crawl dataset. Downstream rules consume this dataset
instead of independently refetching the site.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from collections import deque
from html.parser import HTMLParser
from typing import Any, Callable

from adapters.url_safety import validate_public_url
from integrations.product_proof.models import CrawlConfig, PageRecord, RobotsRecord
from integrations.technical.http import BoundedHttpClient, HttpHop

_SOFT_404 = re.compile(r"\b(?:page\s+not\s+found|not\s+found|no\s+results|nothing\s+here|does\s+not\s+exist|404)\b", re.IGNORECASE)
_QUERY_PAGE_KEYS = {"page", "paged", "pagenum", "page_num", "pg"}


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

    def handle_starttag(self, tag: str, attrs) -> None:
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
            self.images.append(values)
            if values.get("src"):
                self.assets.append(values["src"])
            if values.get("srcset"):
                for part in values["srcset"].split(","):
                    candidate = part.strip().split(" ", 1)[0]
                    if candidate:
                        self.assets.append(candidate)
        elif lower in {"script", "source", "video", "audio", "iframe"}:
            candidate = values.get("src") or values.get("poster")
            if candidate:
                self.assets.append(candidate)
            if lower == "script" and values.get("type", "").lower().split(";", 1)[0].strip() == "application/ld+json":
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


class RobotsPolicy:
    """Google-style longest-path matcher with least-restrictive ties."""

    def __init__(self, groups: list[dict[str, Any]]) -> None:
        self.groups = groups

    @staticmethod
    def _pattern(path: str) -> re.Pattern[str]:
        escaped = ""
        for char in path:
            if char == "*":
                escaped += ".*"
            elif char == "$":
                escaped += "$"
            else:
                escaped += re.escape(char)
        return re.compile("^" + escaped)

    @staticmethod
    def _specificity(path: str) -> int:
        return len(path.replace("*", "").replace("$", ""))

    def allowed(self, url: str, user_agent: str = "googlebot") -> bool:
        parsed = urllib.parse.urlsplit(url)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        ua = user_agent.lower()
        matching: list[tuple[int, dict[str, Any]]] = []
        for group in self.groups:
            agents = [str(value).lower() for value in group.get("user_agents", [])]
            exact = [agent for agent in agents if agent != "*" and agent in ua]
            if exact:
                matching.append((max(len(agent) for agent in exact), group))
            elif "*" in agents:
                matching.append((0, group))
        if not matching:
            return True
        most_specific = max(score for score, _ in matching)
        selected = [group for score, group in matching if score == most_specific]
        rules: list[tuple[int, bool]] = []
        for group in selected:
            for rule in group.get("rules", []):
                path = str(rule.get("path", ""))
                if not path:
                    continue
                if self._pattern(path).search(target):
                    rules.append((self._specificity(path), rule.get("directive") == "allow"))
        if not rules:
            return True
        longest = max(score for score, _ in rules)
        return any(allow for score, allow in rules if score == longest)


def parse_robots(text: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    groups: list[dict[str, Any]] = []
    sitemaps: list[str] = []
    unknown: list[str] = []
    current_agents: list[str] = []
    current_rules: list[dict[str, str]] = []

    def flush() -> None:
        nonlocal current_agents, current_rules
        if current_agents:
            groups.append({"user_agents": current_agents, "rules": current_rules})
        current_agents = []
        current_rules = []

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = [part.strip() for part in line.split(":", 1)]
        field = field.lower()
        if field == "user-agent":
            if current_rules:
                flush()
            current_agents.append(value)
        elif field in {"allow", "disallow"}:
            if not current_agents:
                unknown.append(raw.strip())
            else:
                current_rules.append({"directive": field, "path": value})
        elif field == "sitemap":
            sitemaps.append(value)
        else:
            unknown.append(raw.strip())
    flush()
    merged: dict[tuple[str, ...], dict[str, Any]] = {}
    for group in groups:
        key = tuple(sorted(value.lower() for value in group["user_agents"]))
        bucket = merged.setdefault(key, {"user_agents": list(key), "rules": []})
        bucket["rules"].extend(group["rules"])
    return list(merged.values()), sitemaps, unknown


class SiteCrawler:
    def __init__(self, *, config: CrawlConfig | None = None, http: Any | None = None, url_validator: Callable[[str], str] = validate_public_url) -> None:
        self.config = config or CrawlConfig()
        self.url_validator = url_validator
        self.http = http or BoundedHttpClient(timeout=self.config.timeout_seconds, max_response_bytes=self.config.max_response_bytes, max_redirects=self.config.max_redirects, user_agent="World-Class-SEO-Product-Proof/2.0")

    @staticmethod
    def _header(headers: dict[str, str], name: str) -> str | None:
        for key, value in headers.items():
            if key.lower() == name.lower():
                return value
        return None

    @staticmethod
    def _decode(hop: HttpHop) -> str:
        content_type = SiteCrawler._header(hop.headers, "content-type") or ""
        match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, re.I)
        charset = match.group(1) if match else "utf-8"
        try:
            return hop.body.decode(charset, errors="replace")
        except LookupError:
            return hop.body.decode("utf-8", errors="replace")

    @staticmethod
    def _normalized(url: str) -> str:
        parsed = urllib.parse.urlsplit(url)
        return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path or "/", parsed.query, ""))

    @staticmethod
    def _jsonld_types(payloads: list[str]) -> list[str]:
        output: set[str] = set()
        def visit(value: Any) -> None:
            if isinstance(value, dict):
                kind = value.get("@type")
                if isinstance(kind, str): output.add(kind)
                elif isinstance(kind, list): output.update(str(item) for item in kind)
                for nested in value.values(): visit(nested)
            elif isinstance(value, list):
                for nested in value: visit(nested)
        for text in payloads:
            try: visit(json.loads(text))
            except json.JSONDecodeError: continue
        return sorted(output)

    def _page(self, url: str, depth: int, root_host: str) -> PageRecord:
        hop = self.http.get(url)
        content_type = self._header(hop.headers, "content-type")
        html_like = not content_type or any(token in content_type.lower() for token in ("text/html", "application/xhtml+xml"))
        parser = _HTMLAuditParser()
        text = ""
        errors: list[str] = []
        if html_like and hop.body:
            text = self._decode(hop)
            try: parser.feed(text)
            except Exception as exc: errors.append(f"HTML parse warning: {type(exc).__name__}")
        base = hop.final_url
        internal: set[str] = set(); external: set[str] = set(); rel_next: set[str] = set(); rel_prev: set[str] = set(); canonical: str | None = None
        for link in parser.links:
            href = link.get("href", "").strip()
            if not href: continue
            absolute = self._normalized(urllib.parse.urljoin(base, href))
            relation = {part.lower() for part in link.get("rel", "").split()}
            if "canonical" in relation and canonical is None: canonical = absolute
            if "next" in relation: rel_next.add(absolute)
            if "prev" in relation: rel_prev.add(absolute)
            if link.get("href") and link.get("rel", "").lower() not in {"stylesheet", "preload", "modulepreload", "icon"}:
                if urllib.parse.urlsplit(absolute).hostname == root_host: internal.add(absolute)
                elif urllib.parse.urlsplit(absolute).scheme in {"http", "https"}: external.add(absolute)
        assets = sorted({self._normalized(urllib.parse.urljoin(base, value)) for value in parser.assets if urllib.parse.urlsplit(urllib.parse.urljoin(base, value)).scheme in {"http", "https"}})
        robots_values: list[str] = []
        for meta in parser.metas:
            if meta.get("name", "").lower() in {"robots", "googlebot"}:
                robots_values.extend(token.strip().lower() for token in meta.get("content", "").split(",") if token.strip())
        x_robots = self._header(hop.headers, "x-robots-tag")
        images = [{"src": self._normalized(urllib.parse.urljoin(base, image.get("src", ""))) if image.get("src", "").strip() else None, "loading": image.get("loading") or None, "fetchpriority": image.get("fetchpriority") or None, "width": image.get("width") or None, "height": image.get("height") or None, "alt_present": "alt" in image, "position": index} for index, image in enumerate(parser.images)]
        visible_text = " ".join(parser.text_parts)
        title = " ".join(parser.title_parts).strip() or None
        soft = bool(200 <= hop.status_code < 300 and (_SOFT_404.search((title or "") + " " + visible_text[:2000]) or len(visible_text.strip()) < 40))
        return PageRecord(requested_url=url, final_url=self._normalized(hop.final_url), depth=depth, status_code=hop.status_code, elapsed_ms=hop.elapsed_ms, content_type=content_type, title=title, h1=parser.h1, canonical=canonical, meta_robots=sorted(set(robots_values)), x_robots_tag=x_robots, internal_links=sorted(internal), external_links=sorted(external), asset_urls=assets, images=images, jsonld_types=self._jsonld_types(parser.jsonld_payloads), rel_next=sorted(rel_next), rel_prev=sorted(rel_prev), data_nosnippet_count=parser.data_nosnippet_count, text_length=len(visible_text), content_hash=hashlib.sha256(visible_text.encode("utf-8")).hexdigest(), soft_404_signal=soft, raw_html_available=bool(text), errors=errors)

    def _robots(self, scheme: str, host: str) -> RobotsRecord:
        url = urllib.parse.urlunsplit((scheme, host, "/robots.txt", "", ""))
        try:
            hop = self.http.get(url)
            text = self._decode(hop) if hop.body else ""
            groups, sitemaps, unknown = parse_robots(text)
            return RobotsRecord(host=host, robots_url=url, status_code=hop.status_code, elapsed_ms=hop.elapsed_ms, size_bytes=len(hop.body), groups=groups, sitemaps=sitemaps, unknown_directives=unknown, errors=[])
        except Exception as exc:
            return RobotsRecord(host=host, robots_url=url, status_code=0, elapsed_ms=0, size_bytes=0, groups=[], sitemaps=[], unknown_directives=[], errors=[f"{type(exc).__name__}: {str(exc)[:300]}"])

    def crawl(self, start_url: str) -> dict[str, Any]:
        safe = self.url_validator(start_url); start = self._normalized(safe); parsed = urllib.parse.urlsplit(start); root_host = parsed.hostname or ""; root_netloc = parsed.netloc
        queue: deque[tuple[str, int]] = deque([(start, 0)]); enqueued = {start}; pages: list[PageRecord] = []; failed: list[dict[str, str]] = []; asset_hosts: set[str] = set()
        while queue and len(pages) < self.config.max_urls:
            url, depth = queue.popleft()
            try: page = self._page(url, depth, root_host); pages.append(page)
            except Exception as exc: failed.append({"url": url, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}); continue
            for asset in page.asset_urls:
                host = urllib.parse.urlsplit(asset).netloc
                if host: asset_hosts.add(host)
            if depth >= self.config.max_depth: continue
            for target in page.internal_links:
                target_parts = urllib.parse.urlsplit(target)
                if target_parts.hostname != root_host or target_parts.netloc != root_netloc: continue
                if target not in enqueued and len(enqueued) < self.config.max_urls * 5:
                    enqueued.add(target); queue.append((target, depth + 1))
        hosts = [root_netloc] + sorted(asset_hosts - {root_netloc})[: self.config.max_asset_hosts]
        robots = [self._robots(parsed.scheme, host) for host in hosts]
        return {"start_url": start, "root_host": root_host, "pages": [page.to_dict() for page in pages], "robots": [record.to_dict() for record in robots], "failed_fetches": failed, "queued_but_not_crawled": max(len(queue), 0), "limits": self.config.to_dict(), "truncated": bool(queue) or len(pages) >= self.config.max_urls, "data_state": "AVAILABLE" if pages else "EMPTY"}
