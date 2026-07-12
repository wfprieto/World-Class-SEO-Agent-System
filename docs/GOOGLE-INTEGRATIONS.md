# Google First-Party Integrations

Verified against current official primary documentation on **2026-07-11**.

The Google pack provides optional, read-only evidence acquisition for Search Console Search Analytics, Search Console URL Inspection, Search Console Sitemaps, GA4, PageSpeed Insights, current CrUX, CrUX History, and LCP subparts. It does not modify websites, analytics properties, Search Console properties, sitemaps, or Google tags.

## Commands

```bash
seoctl google gsc-query --site-url sc-domain:example.com \
  --start-date 2026-06-01 --end-date 2026-06-30 \
  --dimension query

seoctl google gsc-aggregate --site-url sc-domain:example.com \
  --start-date 2026-06-01 --end-date 2026-06-30

seoctl google ga4-report --property-id 123456789 \
  --start-date 2026-06-01 --end-date 2026-06-30 \
  --dimension landingPagePlusQueryString \
  --metric sessions --metric engagedSessions --metric keyEvents

seoctl google pagespeed --url https://www.example.com --strategy mobile

seoctl google crux-current --target https://www.example.com \
  --target-type origin --form-factor mobile

seoctl google crux-history --target https://www.example.com \
  --target-type origin --form-factor mobile --periods 25

seoctl google lcp-subparts --target https://www.example.com \
  --target-type url --form-factor mobile

seoctl google url-inspection \
  --url https://www.example.com/page \
  --site-url sc-domain:example.com

seoctl google sitemap-status --site-url sc-domain:example.com
seoctl google sitemap-status --site-url sc-domain:example.com \
  --sitemap-url https://example.com/sitemap.xml
```

`gsc-inspect` remains a compatibility alias for `url-inspection`. Every command returns the standard `seoctl` JSON envelope and stable exit codes.

## Authentication

### Search Console

Use the minimum read-only OAuth scope:

```text
https://www.googleapis.com/auth/webmasters.readonly
```

Configure either `GSC_ACCESS_TOKEN` or all of:

```text
GSC_CLIENT_ID
GSC_CLIENT_SECRET
GSC_REFRESH_TOKEN
```

The refresh-token endpoint is restricted to `https://oauth2.googleapis.com/token`. Token responses are timeout- and size-bounded, and credentials are never persisted by the integration.

### Google Analytics Data API

Use the minimum read-only OAuth scope:

```text
https://www.googleapis.com/auth/analytics.readonly
```

Configure either `GA4_ACCESS_TOKEN` or all of:

```text
GA4_CLIENT_ID
GA4_CLIENT_SECRET
GA4_REFRESH_TOKEN
```

### PageSpeed Insights and CrUX

Configure restricted API keys:

```text
GOOGLE_PAGESPEED_API_KEY
GOOGLE_CRUX_API_KEY
```

The CrUX key may fall back to the PageSpeed key when the same restricted key is enabled for both APIs. Keys travel in the `X-Goog-Api-Key` request header and are not placed in generated URLs or surfaced errors.

## Normalized truthful states

Provider and evidence results preserve these explicit states where applicable:

```text
AVAILABLE
PARTIAL
EMPTY
NOT_CONFIGURED
UNAUTHORIZED
RATE_LIMITED
NOT_FOUND
INVALID_RESPONSE
BLOCKED
FAILED
```

A missing record, permission failure, rate limit, invalid response, or unconfigured credential is never converted into a clean zero result.

## Evidence and accuracy rules

### Search Console totals

Search Analytics can omit anonymized or lower-volume dimension rows and returns top rows rather than every row. Therefore:

- property totals come from a separate dimensionless aggregate query;
- the normalized field is `aggregate`, with source `dimensionless_aggregate_query`;
- dimension rows are never summed to replace those totals;
- row pagination is bounded and truncation is explicit;
- source dimensions, Search Console data state, dates, time zone, pagination, and provider metadata are preserved.

### URL Inspection

URL Inspection reports the version stored in Google's index. It does not test the current live URL. The connector:

- keeps the Search Console property and inspected URL distinct;
- verifies that the inspected URL belongs to the supplied property;
- preserves provider verdict fields without reinterpretation;
- does not add an indexing request or any write action.

### Sitemaps

`sitemap-status` uses read-only Search Console Sitemaps list/get operations. It:

- sends GET requests with no request body;
- normalizes sitemap listing and detail responses;
- preserves warning and error counts separately;
- never submits or deletes a sitemap.

### GA4 totals and pagination

GA4 totals come from the Data API `TOTAL` metric aggregation. They are not recomputed from the returned page. The connector preserves:

- `rowCount`, returned-row count, offset, and limit;
- property quota metadata;
- data-loss metadata and warnings;
- property time zone and currency;
- requested date range;
- current `keyEvents` terminology.

Missing permission is surfaced as `UNAUTHORIZED`, not empty analytics.

### Current CrUX and CrUX History

Current CrUX and CrUX History are separate commands and response models. Mobile, desktop, and tablet form factors remain separate.

- Current CrUX returns one eligible 28-day field record.
- CrUX History returns 1 to 40 requested collection periods.
- Historical points are overlapping rolling 28-day aggregates.
- A 404/no eligible record returns `NOT_FOUND`, not zero performance.
- Request and retry telemetry are preserved.

### LCP subparts

LCP subparts are derived only from the field metrics actually returned by CrUX. Output retains milliseconds and source identity. If all required subparts are not present, the result is `INSUFFICIENT_EVIDENCE`; no timing component is estimated.

## Transport and quota controls

All Google calls use one bounded JSON transport with:

- exact approved Google hosts and HTTPS only;
- same-host redirect enforcement;
- timeouts and bounded retries;
- response-size ceilings;
- JSON-object validation;
- credential redaction, including encoded credentials;
- retry, status, and rate-limit telemetry;
- injectable clients/openers for deterministic tests;
- no unbounded pagination.

CrUX and CrUX History share an official quota of 150 queries per minute per Google Cloud project. The implementation does not attempt unbounded retries or parallel expansion to evade provider quotas.

## Official sources

The following official primary sources were verified on 2026-07-11:

- Search Analytics query: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
- Search Console URL Inspection: https://developers.google.com/webmaster-tools/v1/urlInspection.index/inspect
- Search Console Sitemaps list: https://developers.google.com/webmaster-tools/v1/sitemaps/list
- Search Console Sitemaps get: https://developers.google.com/webmaster-tools/v1/sitemaps/get
- Google Analytics Data API `runReport`: https://developers.google.com/analytics/devguides/reporting/data/v1/rest/v1beta/properties/runReport
- PageSpeed Insights `runPagespeed`: https://developers.google.com/speed/docs/insights/rest/v5/pagespeedapi/runpagespeed
- Current CrUX API: https://developer.chrome.com/docs/crux/api/
- CrUX History API: https://developer.chrome.com/docs/crux/history-api/
- Google OAuth 2.0 overview: https://developers.google.com/identity/protocols/oauth2

## Verification status

Fixture and transport-contract tests verify:

- OAuth and API-key boundaries;
- header-only API-key transport;
- response-size limits and credential redaction;
- separate GSC aggregate totals and bounded detail pagination;
- URL Inspection property containment and provider-verdict preservation;
- read-only sitemap list/get behavior;
- GA4 typed rows, provider totals, pagination, data-loss warnings, and quota metadata;
- current and historical CrUX separation;
- 404 `NOT_FOUND` semantics;
- CrUX period bounds and histogram shapes;
- truthful LCP subpart handling;
- installed `seoctl google` commands;
- explicit unavailable/blocked credential states.

No live Search Console, GA4, PageSpeed, CrUX, URL Inspection, or Sitemaps request is claimed without authorized credentials. Until redacted live smoke evidence is recorded, the live state remains `BLOCKED` and the associated comparative live-smoke rows remain `GAP_OPEN`.

## Removal and rollback

Remove Google credentials from the environment to disable live calls. No database migration, persistent provider token store, or write-side Google operation is created. The pack can be rolled back by reverting the phase commit without data migration.
