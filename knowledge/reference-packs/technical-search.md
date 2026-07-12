# Technical Search Reference Pack

- Owner: SEO Technical Agent
- Last verified: 2026-07-12
- Freshness class: quarterly

## Primary sources

- https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics
- https://developers.google.com/search/docs/crawling-indexing/robots/intro
- https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview
- https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- https://developers.google.com/search/docs/crawling-indexing/301-redirects
- https://developers.google.com/search/docs/specialty/international/localized-versions
- https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data
- https://developers.google.com/search/docs/appearance/core-web-vitals

<a id="crawling-indexing"></a>
## Crawling and indexing

Separate discovery, fetch, render, canonical selection, and indexing evidence. A discovered URL is not automatically fetched, rendered, indexed, or selected as canonical.

<a id="javascript-rendering"></a>
## JavaScript rendering

Treat crawling, rendering, and indexing as distinct phases. Inspect rendered HTML and HTTP status codes rather than assuming client-side execution succeeded.

<a id="robots-sitemaps"></a>
## Robots and sitemaps

robots.txt controls crawling, not guaranteed index removal. Sitemaps are discovery hints and should contain canonical, indexable URLs with accurate metadata.

<a id="canonicals-redirects"></a>
## Canonicals and redirects

Canonical annotations are signals, not commands. Prefer permanent server-side redirects for durable moves and preserve evidence about redirect chains.

<a id="hreflang-localization"></a>
## Hreflang and localization

Localized alternates need valid language or region codes, reciprocal relationships, and canonical alignment.

<a id="structured-data"></a>
## Structured data

Markup must describe visible content and follow feature-specific guidance. Valid syntax does not guarantee rich-result eligibility.

<a id="core-web-vitals"></a>
## Core Web Vitals

Keep field and lab evidence separate. No single metric is a complete ranking explanation.
