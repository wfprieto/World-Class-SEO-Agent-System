# Rendering and Technical Execution Pack

Verified against current official primary documentation on **2026-07-11**.

This pack adds bounded, optional browser rendering and public-web technical inspection through the canonical `seoctl` command registry and runtime `ToolDispatcher`. It does not replace the repository's canonical URL-safety implementation, Google PageSpeed integration, evidence store, runtime budget, or agent capability registry.

## Commands

```bash
seoctl render health
seoctl render page --url https://example.com --wait-until networkidle
seoctl render screenshot --url https://example.com --output capture.png --full-page

seoctl technical robots --url https://example.com
seoctl technical sitemap --url https://example.com/sitemap.xml
seoctl technical hreflang --url https://example.com/en/page
seoctl technical preload --url https://example.com
seoctl technical redirect-chain --url https://example.com/old --max-redirects 10
seoctl technical indexability --url https://example.com/page
seoctl technical cwv --fixture fixtures/pagespeed.json
seoctl technical cwv --url https://example.com --strategy mobile

seoctl schema detect --url https://example.com/article
seoctl schema detect --html-file fixtures/article.html
seoctl schema validate --file fixtures/article.json
seoctl schema generate --type Organization \
  --value name="Example Inc." \
  --value url=https://example.com
```

All commands return the standard `seoctl` JSON envelope and stable exit codes.

## Optional Playwright installation

Playwright is intentionally outside the core dependency set.

```bash
pip install -e ".[render]"
python -m playwright install chromium
seoctl render health
```

Linux environments that also need operating-system dependencies can use Playwright's documented dependency installation flow:

```bash
python -m playwright install --with-deps chromium
```

To remove the browser binary:

```bash
python -m playwright uninstall chromium
```

To remove the optional Python dependency, uninstall Playwright through the environment's package manager. The rest of `seoctl` remains operational without it.

`render health` reports `NOT_CONFIGURED` when either the Python package or compatible Chromium binary is absent. A clean core install never treats missing Playwright as a runtime crash or as rendered evidence.

## Rendering contract

`render page` and `render screenshot` use one isolated headless Chromium context per operation. The implementation enforces:

- canonical public-URL validation before navigation;
- HTTP or HTTPS network requests only;
- DNS/IP checks on every intercepted subresource request;
- TLS verification;
- bounded page timeout, viewport, console errors, page errors, failed requests, and screenshot size;
- explicit wait conditions;
- optional bounded resource-type blocking;
- validated final public URL;
- PNG-only screenshot output with atomic replacement;
- no cookies, login state, or persistent browser profile;
- no claim of success when Chromium is absent or a render fails.

Playwright browser versions are coupled to Playwright releases, so the browser installation command should be rerun after Playwright upgrades. Browser and screenshot behavior can vary by environment and browser version.

## Public HTTP contract

The technical HTTP client manually follows redirects so each target is revalidated. It uses:

- `adapters.url_safety` as the sole public-target policy;
- no automatic arbitrary redirect following;
- a default 30-second request timeout;
- a 12 MB response ceiling;
- a default 10-hop redirect ceiling, with a hard maximum of 20;
- `Accept-Encoding: identity` to keep response-size enforcement direct;
- explicit loop, limit, and blocked-target evidence;
- no authentication headers, cookies, form submissions, or write methods.

## Operation semantics

### Robots

The command fetches the origin's `/robots.txt`, preserves user-agent groups and allow/disallow rules, reports sitemap directives, and keeps unknown directives visible. It does not reinterpret crawling rules as guaranteed deindexing. A missing robots file is not reported as a crawl block.

### Sitemaps

The command parses `urlset` and `sitemapindex` XML, reports location count, duplicate locations, invalid or non-public locations, response status, and truncation. Analysis is bounded to the first 50,000 locations. The command does not submit, delete, or recursively crawl sitemap indexes.

### Hreflang

The command inspects HTML `<link rel="alternate" hreflang="...">` annotations, checks a bounded BCP-47-style format, validates public targets, identifies duplicate language codes, and reports `x-default`. A single-page result cannot prove reciprocal return links or inspect HTTP-header or XML-sitemap annotations.

### Preload

The command reports HTML preload/modulepreload declarations and relevant attributes such as `as`, `type`, `media`, `crossorigin`, and `fetchpriority`. Markup presence is not represented as proof of improved performance.

### Redirect chains

The command reports every bounded response, loop detection, hop-limit state, final URL, and blocked targets. It does not follow a redirect into private, loopback, link-local, reserved, or otherwise disallowed destinations.

### Indexability

The command evaluates technical eligibility evidence from HTTP status, `X-Robots-Tag`, robots meta directives, and HTML canonical declarations. It uses the term `indexable` only for this bounded technical eligibility result. It does not claim that Google indexed, will index, or selected a specific canonical for the URL.

### Core Web Vitals

Fixture mode normalizes a supplied PageSpeed/Lighthouse payload and sets `live_measurement = false`. Live mode reuses the existing PageSpeed adapter. Ratings use current Core Web Vitals thresholds:

- LCP: good at 2,500 ms or less;
- INP: good at 200 ms or less;
- CLS: good at 0.1 or less.

Lighthouse values are lab diagnostics. CrUX values are field aggregates. They remain distinct evidence sources.

### Structured data

`schema detect` parses JSON-LD from a URL or supplied HTML. `schema validate` checks JSON syntax and baseline `@context`/`@type` presence. Neither command claims Google rich-result eligibility.

`schema generate` is deliberately bounded to a small set of types and includes only operator-supplied values. It does not invent identities, ratings, reviews, prices, availability, medical claims, or eligibility claims. Generated markup still requires page-level and current Google feature-specific validation.

## Runtime wiring

The canonical runtime adapter registry exposes:

```text
rendered_page_execution
technical_execution
```

These adapters pass normalized `AdapterResult` evidence through `runtime.tools.ToolDispatcher`. Existing fixture adapters remain available for compatibility and offline workflows.

## Truthful states

Relevant explicit states include:

```text
AVAILABLE
PARTIAL
EMPTY
NOT_CONFIGURED
INVALID_RESPONSE
BLOCKED
FAILED
```

A missing browser, blocked redirect, invalid XML, incomplete field data, or absent evidence is never converted to a successful empty result.

## Official sources

Verified on 2026-07-11:

- Playwright Python installation: https://playwright.dev/python/docs/intro
- Playwright browser installation and removal: https://playwright.dev/python/docs/browsers
- Playwright screenshots: https://playwright.dev/python/docs/screenshots
- Playwright network routing: https://playwright.dev/python/docs/network
- Google robots.txt introduction: https://developers.google.com/search/docs/crawling-indexing/robots/intro
- Google sitemap overview: https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview
- Google canonical guidance: https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- Google localized-page and hreflang guidance: https://developers.google.com/search/docs/specialty/international/localized-versions
- Google structured data introduction: https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data
- Web Vitals definitions and thresholds: https://web.dev/articles/vitals

## Verification status

Deterministic tests cover:

- RED-before-production implementation history;
- clean-install browser health and missing-parent-module behavior;
- injected rendered HTML and screenshot evidence;
- PNG output constraints;
- robots groups, directives, and sitemaps;
- sitemap duplicates and unsafe locations;
- HTML hreflang, preload, canonical, robots meta, and JSON-LD extraction;
- redirect loops and hop ceilings;
- fixture-only CWV truthfulness;
- bounded schema generation without invented facts;
- runtime ToolDispatcher wiring;
- all 13 installed command routes and help surfaces;
- canonical command registry and generated documentation synchronization;
- Windows and Ubuntu, Python 3.11 and 3.13 repository validation.

A browser-network smoke test is not claimed unless Playwright Chromium is installed and an explicitly approved public target is used. Until that evidence exists, browser live-smoke parity remains open.

## Rollback

Rollback requires reverting the phase commit and removing the optional Playwright package/browser if installed. No database migration, persistent browser profile, credentials, or write-side external operation is created.
