# Core SEO Skills

## `full-site-audit`

Purpose: Produce a complete SEO health report across technical, content, IA, authority, local/international, accessibility, CRO, GEO/AIO, security, and compliance.

Inputs:

- Domain
- Crawl data
- Search Console and analytics when available
- Business type
- Target market
- Known competitors

Output:

- Audit report
- Health score
- Top issues
- Evidence appendix
- Prioritized roadmap input

Quality gate:

- Every score must disclose missing data.

## `technical-audit`

Purpose: Evaluate crawlability, indexability, rendering, metadata, canonicals, redirects, structured data, mobile, security, and Core Web Vitals.

Output:

- Technical findings
- Fix backlog
- Affected URL groups
- Engineering acceptance criteria

Quality gate:

- Use direct page evidence. Do not rely on crawler summaries alone for critical issues.

## `crawl-map`

Purpose: Build a URL inventory, crawl-depth map, internal-link graph, orphan candidate list, and sitemap comparison.

Output:

- URL inventory
- Depth distribution
- Internal link opportunities
- Orphan and near-orphan candidates

Quality gate:

- Separate indexable, non-indexable, blocked, redirected, canonicalized, and error URLs.

## `indexation-reality-check`

Purpose: Compare intended indexation against actual indexation signals.

Output:

- Indexed/intended mismatch list
- Blocked but valuable URLs
- Indexed but low-value URLs
- Validation plan

Quality gate:

- Do not recommend deindexing without business and traffic review.

## `schema-detect-validate-generate`

Purpose: Detect existing structured data, validate it, and generate safe JSON-LD recommendations.

Output:

- Schema inventory
- Validation issues
- Recommended schema types
- Paste-ready JSON-LD or implementation ticket

Quality gate:

- Schema must describe visible page content and follow structured data policies.

## `core-web-vitals-triage`

Purpose: Identify likely causes and fixes for LCP, INP, and CLS issues.

Output:

- Metric status
- Likely causes
- Fix candidates
- Verification method

Quality gate:

- Prefer field data. Use lab data to diagnose, not to overclaim real-user impact.

## `seo-drift-monitor`

Purpose: Detect SEO regressions across deployments, content changes, rankings, indexation, metadata, schema, links, and performance.

Output:

- Regression report
- Changed signals
- Severity
- Rollback or remediation recommendation

Quality gate:

- Distinguish normal volatility from deployment-linked drift.

