# Framework SEO Implementation Expanded Reference Pack

- Owner: Senior SEO Engineer Agent
- Last verified: 2026-07-12
- Freshness class: quarterly
- Evidence posture: framework implementation notes are advisory until mapped to the target stack, runtime, deployment mode, and generated HTML.

## Primary sources

- https://nextjs.org/docs/app/api-reference/functions/generate-metadata
- https://developers.google.com/search/docs/appearance/structured-data/intro-structured-data
- https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview
- https://developers.google.com/search/docs/crawling-indexing/robots/intro
- https://developers.google.com/search/apis/indexing-api/v3/quickstart

<a id="framework-metadata-boundary"></a>
## Framework metadata boundary

Framework libraries can help generate metadata and JSON-LD, but the SEO system must validate the rendered output, not the component intent. For Next.js App Router projects, prefer native metadata generation for standard title, description, canonical, robots, and social tags, then use JSON-LD helpers only where they produce valid structured data for the page type.

Do not assume a framework package fixes duplicate titles, missing canonical URLs, stale product data, or weak content. The Senior SEO Engineer Agent must inspect final HTML, response status, canonical destination, robots directives, and structured-data validation results.

<a id="structured-data-component-gate"></a>
## Structured data component gate

Structured-data components are implementation conveniences, not proof of eligibility. Before recommending generated schema, verify page type, required and recommended properties, visible-content alignment, canonical URL consistency, image availability, date freshness, and policy eligibility. Invalid or misleading schema must be removed or corrected rather than hidden behind a helper component.

When multiple page templates share one schema helper, test representative pages from each template, including missing optional fields, empty arrays, multiple authors, out-of-stock products, events, local pages, and paginated or filtered pages.

<a id="sitemap-generation-patterns"></a>
## Sitemap generation patterns

Sitemap tooling should match the deployment model. Static builds may generate sitemaps after build; server-side or frequently changing applications may require dynamic sitemap endpoints or scheduled generation. Large sites should use sitemap indexes, stable shard boundaries, canonical-only URL inclusion, lastmod discipline, and separate treatment for image, video, news, and hreflang alternates where applicable.

Robots.txt should point to the sitemap index or canonical sitemap locations without duplicating every child sitemap unless there is a specific operational reason. Sitemaps are discovery hints, not indexing guarantees.

<a id="adapter-hardening-patterns"></a>
## Adapter hardening patterns

Live adapters and crawler-style integrations must use explicit credential gates, budget gates, bounded concurrency, timeout limits, retry/backoff for retryable failures, URL safety validation, robots or policy awareness where applicable, and structured missing-evidence states. Indexing API adapters must also enforce eligibility gates: the Google Indexing API is not a generic ranking lever and is restricted to supported content types.

Broken-link and redirect checks should account for relative URLs, base URLs, compression, redirects, authentication boundaries, nofollow/noindex directives, robots exclusions, non-HTML resources, and paused or resumable queues. A single tool failure must not erase other evidence gathered in the same audit.
