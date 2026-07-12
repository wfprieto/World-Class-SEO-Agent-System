# Google First-Party Integrations

The Google pack provides optional, read-only evidence acquisition for Search Console, GA4, PageSpeed Insights, and CrUX History. It does not modify websites, analytics properties, Search Console properties, or Google tags.

## Commands

```bash
seoctl google gsc-query --site-url sc-domain:example.com \
  --start-date 2026-06-01 --end-date 2026-06-30 \
  --dimension query

seoctl google gsc-inspect \
  --url https://www.example.com/page \
  --site-url sc-domain:example.com

seoctl google ga4-report --property-id 123456789 \
  --start-date 2026-06-01 --end-date 2026-06-30 \
  --dimension landingPagePlusQueryString \
  --metric sessions --metric engagedSessions --metric keyEvents

seoctl google pagespeed --url https://www.example.com --strategy mobile

seoctl google crux-history --target https://www.example.com \
  --target-type origin --form-factor mobile --periods 25

seoctl google lcp-subparts --target https://www.example.com \
  --target-type url --form-factor mobile
```

Every command returns the standard `seoctl` JSON envelope and uses stable exit codes.

## Authentication

### Search Console

Use the minimum read-only OAuth scope:

```text
https://www.googleapis.com/auth/webmasters.readonly
```

Configure either:

```text
GSC_ACCESS_TOKEN
```

or:

```text
GSC_CLIENT_ID
GSC_CLIENT_SECRET
GSC_REFRESH_TOKEN
```

The refresh-token endpoint is restricted to `https://oauth2.googleapis.com/token`.

### Google Analytics Data API

Use the minimum read-only OAuth scope:

```text
https://www.googleapis.com/auth/analytics.readonly
```

Configure either:

```text
GA4_ACCESS_TOKEN
```

or:

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

The CrUX key may fall back to the PageSpeed key when the same restricted key is enabled for both APIs.

Keys travel in the `X-Goog-Api-Key` request header. They are not placed in URLs.

## Evidence and accuracy rules

### Search Console totals

Search Analytics can omit anonymized low-volume dimension rows. Therefore:

- property totals come from a separate dimensionless aggregate query;
- dimension rows are never summed to replace those totals;
- row coverage may be partial even when totals are valid;
- the response preserves Google metadata about incomplete recent data.

### URL Inspection

URL Inspection reports the version stored in Google's index. It does not test the current live URL.

The connector also rejects inspection URLs outside the supplied Search Console property.

### GA4 totals

GA4 totals come from the Data API `TOTAL` metric aggregation. They are not computed from the returned page of rows.

The connector preserves:

- `rowCount`;
- returned-row count;
- offset and limit;
- property quota metadata;
- data-loss metadata;
- property time zone and currency.

The default conversion outcome metric is `keyEvents`.

### CrUX History

CrUX History supports 1 to 40 collection periods. This pack defaults to 25.

Each point is a 28-day rolling field aggregate and adjacent weekly points overlap. A missing record means no eligible field data is available. It does not prove that performance is good or bad.

LCP subparts are reported only when Google supplies them. Missing subparts are never estimated.

## Failure behavior

- Missing credentials return `unavailable`, not a clean result.
- Invalid operator input returns exit code 2.
- Provider or validation failures return typed, sanitized errors.
- Retryable 429 and 5xx responses use bounded retries.
- Responses are size limited.
- Redirects outside the original approved Google API host are refused.
- Exact API keys and access tokens are removed if a provider echoes them in an error body.

## What is verified

Fixture and transport-contract tests verify:

- OAuth and API-key boundaries;
- header-only key transport;
- separate GSC and GA4 totals;
- Search Console pagination and property containment;
- GA4 type normalization and quota metadata;
- CrUX collection-period bounds and official histogram shape;
- truthful LCP subpart handling;
- installed `seoctl google` commands;
- unavailable credential states.

## What is not yet verified

No live Search Console, GA4, PageSpeed, CrUX, or URL Inspection request is claimed by this implementation alone.

The comparative capability rows remain open until an authorized smoke test runs against specifically approved non-production or read-only properties and records redacted evidence.

## Removal

The integration pack is optional. Remove Google credentials from the environment to disable live calls. No database migration or persistent provider token store is created.
