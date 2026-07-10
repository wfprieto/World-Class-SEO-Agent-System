# Free and Low-Cost Backlink Evidence Sources

**Status:** Primary-source reconciled baseline  
**Version:** 2.0.0  
**Last reconciled:** 2026-07-10  
**Next scheduled review:** 2026-10-10, with provider limits verified at execution time  
**Primary consumers:** Off-page SEO, link-health monitoring, and drift workflows  
**Canonical source path:** `knowledge/free-backlink-sources.md`

## Purpose

This file separates **link discovery**, **known-link verification**, and **provider-specific metrics** so free, open, or account-included data is not assigned invented coverage, authority, freshness, or confidence. No defensible universal coverage percentage exists; use one only when a current, reproducible benchmark matches the exact source and population.

## Evidence roles

| Source | Access scope | Evidence it can support | Important limits |
|---|---|---|---|
| Google Search Console Links report | Verified properties | Google's sampled/aggregated view of top linking sites, top linked pages, and linking text | Not a complete backlink index; grouped by root domain in parts of the report; property access required |
| Bing Webmaster API / tools | Registered sites | Link details and other Bing Webmaster data for the user's sites | Bing's view only; authentication and site registration required; current endpoint/limits must be checked |
| Common Crawl web graphs | Public host/domain graph data | Host/domain relationships and graph metrics from a published crawl | Includes technical links; graph freshness and crawl coverage vary; not a complete page-level link database or direct proof that a link still exists |
| Verification crawler | Known source URL and target URL | Whether a known page currently exposes a link, plus observed destination, anchor, `rel`, status, and redirect behavior | Cannot discover links it was not given; client-side or blocked content may require rendering; observations change over time |
| Provider APIs with free, trial, or account-included access | Provider- and account-specific | Metrics and link records documented by that provider | Entitlements, quotas, definitions, and freshness change; metrics are proprietary and cannot be treated as equivalent across providers |

## Source selection

Use the least expensive source that can answer the actual question:

- **What does Google report for my verified property?** Use Search Console.
- **What does Bing report for my registered site?** Use Bing Webmaster.
- **Which domains are connected in an open crawl graph?** Use Common Crawl and disclose graph limitations.
- **Does this known link still exist?** Fetch or render the source page and record direct evidence.
- **What is the complete competitor gap, link velocity, or page-level authority landscape?** A commercial index may be necessary after cost approval.

Do not describe a discovery source as a verification source or a provider metric as an objective fact.

## Normalized link evidence record

Every imported or observed link should retain:

- `source_provider`
- `source_scope` such as verified property, provider index, open crawl graph, or direct fetch
- `source_url` and normalized target URL when available
- `observed_at` or provider snapshot date
- HTTP and render method when directly verified
- Anchor text and `rel` attributes when observable
- Link state: `observed`, `redirected`, `removed`, `blocked`, `unknown`, or `provider_reported`
- Provider-specific metrics with the provider name and definition
- Evidence confidence based on what was directly observed, not a universal numeric weight
- Limitations and any sampling/truncation notice

Deduplicate records carefully without erasing independent observations from different dates or providers.

## Conflict and normalization rules

- Preserve the provider's original URL, timestamp, and identifiers before normalization.
- Normalize scheme, host case, default ports, fragments, and tracking parameters only under documented rules; do not collapse URLs that may represent different canonical resources.
- A provider-reported link and a direct fetch are separate observations. If they conflict, retain both and prefer the newer direct observation for current existence while noting that rendering, geography, authentication, or crawl timing may explain the difference.
- Exclude obvious internal links and self-referential host aliases from external-link counts only after canonical ownership is established.
- Do not infer that a missing record is a lost link unless a prior dated record identifies the exact source and target.

## Scoring and reporting controls

- Do not merge Domain Authority, Domain Rating, proprietary spam scores, PageRank-like graph values, or other provider metrics into a universal authority score without a separately validated model.
- Referring-domain counts and raw link counts are descriptive, not proof of quality or causation.
- Evaluate relevance, editorial context, source credibility, link placement, traffic potential, and observed status individually.
- Mark provider-reported links as unverified until directly fetched when existence is material to the recommendation.
- Report the source mix and blind spots beside every backlink-health conclusion.

## Verification crawler safeguards

- Respect robots controls, terms, rate limits, and site stability.
- Use SSRF-safe URL validation and block private, loopback, link-local, reserved, and credential-bearing destinations.
- Limit redirects, response size, runtime, and concurrency.
- Do not execute untrusted scripts unless an approved browser sandbox is required.
- Store snapshots and timestamps so a later “lost link” claim has a baseline.
- Follow provider terms, privacy controls, and data-retention rules; do not store credentials or unnecessary personal data in evidence records.

## Paid-upgrade gate

Recommend a paid source only when the requested decision requires capabilities the available evidence cannot provide, such as:

- broad competitor discovery at page level
- historical link acquisition/loss trends
- large-scale prospecting or gap analysis
- current anchor and destination detail across many domains
- client-required commercial metrics or SLAs

Before a metered call, state the provider, estimated cost, expected evidence gain, limitations, and fallback; obtain explicit approval and record actual cost.

## Disavow and risk decisions

Incomplete or low-quality link data must never trigger an automated disavow file. Use Google's current manual-action and disavow guidance, verify suspicious links, distinguish malicious or manipulative patterns from ordinary low-quality links, and require senior review. When no manual action or clear history of link-scheme participation exists, do not imply that routine “toxic link cleanup” is required.

## Primary sources

- Google Search Console Links report: https://support.google.com/webmasters/answer/9049606
- Bing Webmaster API: https://learn.microsoft.com/en-us/bingwebmaster/
- Common Crawl web graphs: https://commoncrawl.org/web-graphs
- Common Crawl open repository: https://commoncrawl.org/
- Google manual actions guidance: https://support.google.com/webmasters/answer/9044175
