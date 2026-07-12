# seoctl Command Reference

This file is generated from `seoctl/command-registry.json`. Do not edit it manually.

Run `python -m seoctl --help` for interactive argument details.

| Command | Owner | Skills | Network |
|---|---|---|---|
| `seoctl benchmark compare` | AI Principal SEO Scientist | `experiment-design` | `none` |
| `seoctl benchmark tracer` | SEO Research and Development Agent | `experiment-design` | `none` |
| `seoctl cluster serp` | SEO Information Architecture Agent | `serp-overlap-cluster` | `none` |
| `seoctl content brief-decision` | SEO Copywriter/Content Agent | `content-brief` | `none` |
| `seoctl content relevance` | SEO Copywriter/Content Agent | `content-brief` | `none` |
| `seoctl content serp` | SEO Copywriter/Content Agent | `content-brief` | `none` |
| `seoctl google crux-current` | SEO Technical Agent | `core-web-vitals-triage` | `live_optional` |
| `seoctl google crux-history` | SEO Technical Agent | `core-web-vitals-triage` | `live_optional` |
| `seoctl google ga4-report` | SEO Full Audit/Analyst Agent | `analytics-synthesis` | `live_optional` |
| `seoctl google gsc-aggregate` | SEO Full Audit/Analyst Agent | `analytics-synthesis` | `live_optional` |
| `seoctl google gsc-query` | SEO Full Audit/Analyst Agent | `analytics-synthesis` | `live_optional` |
| `seoctl google lcp-subparts` | SEO Technical Agent | `core-web-vitals-triage` | `live_optional` |
| `seoctl google pagespeed` | SEO Technical Agent | `core-web-vitals-triage` | `live_optional` |
| `seoctl google sitemap-status` | SEO Technical Agent | `indexation-reality-check` | `live_optional` |
| `seoctl google url-inspection` | SEO Technical Agent | `indexation-reality-check` | `live_optional` |
| `seoctl privacy consent` | SEO Compliance & Legal Agent | `consent-mode-diagnostic` | `none` |
| `seoctl profile resolve` | SEO Scrummaster Agent | `request-routing` | `none` |
| `seoctl report render` | SEO Output Report Agent | `plain-language-seo-report` | `none` |
| `seoctl system route` | SEO Scrummaster Agent | `request-routing` | `none` |
| `seoctl system run` | SEO Full Audit/Analyst Agent | `full-site-audit` | `provider_optional` |

## Stable exit codes

| Code | Meaning |
|---:|---|
| 0 | Completed successfully or truthfully partial without a hard failure |
| 2 | Invalid or missing operator input |
| 3 | Optional capability or provider unavailable |
| 4 | Blocked by evidence, authorization, privacy or governance gate |
| 5 | Execution or validation failure |

Every command writes one JSON envelope with `command`, `status`, `data`, `warnings`, and `error`.

## Examples

```bash
python -m seoctl --registry-check
python -m seoctl system route "Run a full SEO audit" --domain https://example.com --business-type saas
python -m seoctl system run "Build an SEO content brief" --domain https://example.com --business-type saas
python -m seoctl profile resolve --signal cart --signal checkout --signal visible_price
python -m seoctl cluster serp --serps examples/serps.json
python -m seoctl privacy consent --config consent-fixture.json
python -m seoctl benchmark compare
```

Commands that require live providers remain optional and must preserve runtime budgets, credential redaction, and approval gates.
