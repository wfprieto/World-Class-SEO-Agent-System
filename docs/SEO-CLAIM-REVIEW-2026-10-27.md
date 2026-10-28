# SEO primary-source review — October 27, 2026

Reviewer: Codex. Owner: repository maintainer. Related work: PR #66; repository control `documentation-knowledge-truth` (issue #29).

## Reason for review

After the setup-python contract repair passed its quality checks, canonical run [40627585142](https://github.com/wfprieto/World-Class-SEO-Agent-System/actions/runs/40627585142) failed because 33 PRIMARY_SOURCE claims had reached their October 12 review deadline.

The cited primary documents were retrieved and the relevant sections checked against each existing claim, approved wording, and prohibited wording. All 33 claims remain supported. This review refreshes their verification date to October 27 and retains the existing three-month review cadence, with the next review due January 27, 2027. It does not change evidence classes, claim wording, the five other claims, validation logic, or the policy for stale evidence.

## Claim-to-source evidence

| Claim IDs | Primary document and sections reviewed | Result |
|---|---|---|
| `robots-supported-fields`, `robots-crawl-delay-unsupported`, `robots-file-limit`, `robots-scope`, `robots-precedence`, `robots-4xx`, `robots-5xx` | [Google robots.txt specification](https://developers.google.com/crawling/docs/robots-txt/robots-txt-spec): file location, error handling, file format, supported syntax, and precedence | Supported; including error/cache contingencies and the 429 exception |
| `robots-disallow-not-noindex` | [Introduction to robots.txt](https://developers.google.com/search/docs/crawling-indexing/robots/intro): purpose, limits, and indexing warning | Supported |
| `http-200-not-index-guarantee`, `http-redirect-signals`, `http-404-410`, `http-429-server-signal`, `soft-404` | [HTTP status codes](https://developers.google.com/crawling/docs/troubleshooting/http-status-codes): 2xx processing, 3xx signal strength, 4xx removal, 429 overload | Supported; registry URLs updated to the redirect destination |
| `nosnippet-ai-input`, `max-snippet-ai-input`, `meta-robots-restrictive-wins` | [Robots meta specifications](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag): conflicting rules, nosnippet, and max-snippet | Supported; separately granted content permissions remain a documented exception |
| `canonical-strength`, `canonical-noindex`, `canonical-http-header`, `canonical-js`, `canonical-link-consistency` | [Canonical methods](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls): signal order, best practices, HTML links, and HTTP Link header | Supported |
| `pagination-self-canonical`, `pagination-real-links`, `rel-next-prev-dead` | [Pagination guidance](https://developers.google.com/search/docs/specialty/ecommerce/pagination-and-incremental-page-loading): indexing strategies, sequential links, and unique URLs | Supported |
| `facets-empty-404`, `facets-parameter-separator` | [Faceted navigation](https://developers.google.com/crawling/docs/faceted-navigation): crawlable URL best practices | Supported; registry URLs updated to the redirect destination |
| `crawl-budget-scale` | [Crawl budget](https://developers.google.com/crawling/docs/crawl-budget): introduction and intended site sizes | Supported; registry URL updated to the redirect destination |
| `crawling-not-ranking-signal` | [Myths about crawling](https://developers.google.com/crawling/docs/myths-about-crawling): crawling as a ranking factor | Supported; registry now cites the current page that directly states the distinction |
| `cwv-thresholds` | [Web Vitals](https://web.dev/articles/vitals): current metrics, thresholds, and 75th percentile | Supported |
| `lcp-subparts`, `lcp-no-lazy` | [Optimize LCP](https://web.dev/articles/optimize-lcp): four timing subparts and LCP image discovery/lazy loading | Supported |
| `inp-subparts` | [Optimize INP](https://web.dev/articles/optimize-inp): interaction timing subparts | Supported |
| `schema-not-ranking-factor` | [Google rich-results FAQ](https://developers.google.com/search/blog/2020/08/rich-results-search-console): whether structured data raises rankings; checked alongside the [current structured-data introduction](https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data) | Supported; registry now cites Google's explicit statement |

The sources were inspected as primary documentation. No observational, consensus, hypothesis, or unverified entry was promoted or refreshed. The registry's original compilation date remains historical.

## Verification

Run `python scripts/validate_seo_claims.py`, `python scripts/validate_reference_freshness.py`, and the existing reference, technical-audit, and metadata tests. Hosted canonical and autonomous certification must then pass at the updated PR head. A passing date check alone is not evidence that the source review occurred; the claim mapping above records the review scope.

