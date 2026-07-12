# Primary-Source Technical SEO Rules

**Authority:** `knowledge/seo-claim-registry.json`  
**Source corpus:** SEO BIBLE 2026, with Part 10 primary-source corrections taking precedence  
**Verified:** 2026-07-12

This pack is an implementation reference, not a second source of truth. Runtime findings must cite claim IDs from the machine-readable registry.

## Rules implemented by the flagship audit

### Crawling and robots.txt

- Evaluate robots.txt separately for each relevant host, protocol, and port.
- Check the primary host and discovered CDN, image, media, and asset hosts.
- Treat a genuine missing file differently from server errors.
- Parse only documented Google fields and preserve unknown directives for review.
- Resolve rule conflicts by the longest matching path and the least-restrictive outcome on equal specificity.
- Do not use crawl controls as proof of deindexing.
- Flag pages whose index or canonical instructions are made unreadable by crawl blocking.

### HTTP responses

- A successful response is evidence that content was returned, not proof of indexing.
- Distinguish permanent and temporary redirect signals.
- Treat 404 and 410 as legitimate removal states while identifying internal links and formerly valuable URLs that need remediation.
- Treat 429 and 5xx as availability and crawl-health evidence.
- Detect likely soft 404s rather than accepting every 2xx page as healthy.

### Canonicalization and pagination

- Build a canonical graph and detect cycles, chains, broken targets, and internal links to duplicate variants.
- Give paginated pages their own canonicals and discoverable anchor links.
- Do not depend on legacy next/previous annotations as the current Google mechanism.
- Keep canonical instructions crawlable and consistent across redirects, sitemaps, and internal links.

### Faceted navigation

- Detect repeatable filter parameters, unstable parameter order, and empty successful pages.
- Return a genuine missing-page response for empty or nonsensical combinations when that is the intended content state.
- Do not diagnose a crawl-budget crisis solely because parameters exist.

### Core Web Vitals

- Use current LCP, INP, and CLS field thresholds at the 75th percentile.
- Diagnose LCP using TTFB, resource-load delay, resource-load duration, and render delay.
- Confirm the actual LCP element before applying image-specific recommendations.
- Do not lazy-load the confirmed LCP image.
- Diagnose INP through input, processing, and presentation delay.
- Reserve layout space for images and embeds.

### AI extraction controls

- Report `nosnippet`, `max-snippet`, `data-nosnippet`, and X-Robots-Tag controls as visibility trade-offs.
- Never remove an extraction control automatically.
- Separate vendor-specific crawler access from Google's index-grounded AI feature controls.

## Non-universal heuristics

The following are not hard-coded as universal requirements:

- A fixed internal-link count for every page
- A mandatory number of outbound authority links
- A universal content word count
- A guaranteed ranking gain from schema markup
- Unverified percentages for AI citations or introductory passages
- A named engagement metric not documented by Google

These may inform research or hypotheses only when their evidence class and limitations are displayed.
