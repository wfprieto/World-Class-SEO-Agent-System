# Anonymized Production-Style Example

This example shows how the system should operate with realistic exports while protecting client identity. The data is anonymized and synthetic, but the columns and workflow mirror common production inputs from a crawler, Google Search Console, and analytics exports.

## Inputs

- `inputs/crawl.csv`: crawler-style technical export.
- `inputs/gsc.csv`: search performance export.
- `inputs/ga4.csv`: analytics-style landing page export.

## Expected Workflow

1. Parse crawl data with the crawler CSV adapter.
2. Parse GSC and GA4 exports with the export adapters.
3. Route the request to the SEO Full Audit/Analyst Agent with SEO Technical Agent support.
4. Validate the final output against `schemas/agent-output.schema.json`.

## Privacy Rule

Production examples must remove client names, private URLs, account IDs, user data, and revenue numbers unless the client has approved publication.
