# Anonymized Real-Site GSC Export

This folder shows the format expected from a real Google Search Console export after client-identifying details have been removed.

The included CSV is anonymized and safe for public repository use. It preserves production-style fields and realistic query/page patterns, but the domain, queries and numeric values are sanitized so no private client data is exposed.

## File

- `gsc-search-performance-anonymized.csv`: page/query export with clicks, impressions, CTR and average position.
- `gsc-local-pages-anonymized.csv`: local landing page query sample.
- `gsc-commercial-pages-anonymized.csv`: commercial service page query sample.
- `crux-origin-cwv-anonymized.json`: origin-level Core Web Vitals sample.
- `pagespeed-cwv-anonymized.json`: PageSpeed/Lighthouse Core Web Vitals-style sample.

## Required Privacy Steps Before Adding Real Client Data

1. Replace domains with approved public examples or neutral placeholders.
2. Remove account IDs, property IDs and internal campaign names.
3. Round or bucket sensitive clicks, impressions and conversion values when needed.
4. Remove queries that reveal private customer, patient, legal, financial or employee information.
5. Get written approval before publishing any real client export, even when anonymized.
