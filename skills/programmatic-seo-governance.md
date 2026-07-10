# Programmatic SEO Governance Skill

**Status:** Controlled integration baseline  
**Version:** 2.0.0  
**Canonical source path:** `skills/programmatic-seo-governance.md`  
Skill owners: SEO Technical Agent and SEO ScrumMaster Agent  
SKILL_INDEX category: Technical Implementation Skills  
Primary skill: `programmatic-seo-governance`  
Last primary-source review: 2026-07-10

## Mission

Plan, audit, approve, stage, monitor, or stop pages generated at scale. Protect users and the site from scaled-content abuse, doorway abuse, duplicate intent, index bloat, unreliable data, and uncontrolled publishing.

Programmatic publishing is not inherently abusive. The governing question is whether each indexable page provides distinct, accurate, useful value for a real user need. Automation, generative AI, page count, and shared templates are risk signals, not automatic violations.

## Scope and non-goals

This skill governs generated page sets, templates, supporting data, indexation architecture, rollout, monitoring, and remediation. It does not replace specialist audits for security, privacy, legal compliance, accessibility, structured data, Core Web Vitals, or editorial quality. It coordinates those reviews and prevents approval when a required specialist review is missing.

This skill must not:

- guarantee crawling, indexation, rankings, traffic, conversions, or AI citations
- treat page count, word count, automation, generative AI use, or template reuse as a violation by itself
- approve a page set solely because it passes technical checks
- permit an accountable owner to override an observed spam-policy, security, privacy, or legal violation
- publish, modify, deindex, redirect, or delete URLs without the required authorization

## Required dependencies and handoffs

Before execution, load the current versions of the applicable kit controls. If a required dependency is missing, identify it and downgrade the result rather than reconstructing its rules from memory.

- `knowledge/parasite-seo-expired-domain-checks.md` for site-reputation and expired-domain risk
- `knowledge/core-web-vitals-gates.md` for page-performance evaluation
- `knowledge/schema-deprecation-registry.md` when structured data is generated or reviewed
- `skills/rendered-visual-audit-and-page-entry.md` for rendered and mobile evidence
- `docs/evidence-cache-contract.md` when persisting baselines or monitoring drift

Handoffs:

- SEO Technical Agent: crawlability, rendering, canonicals, sitemaps, status codes, and performance
- SEO Content or Copywriter Agent: editorial usefulness, accuracy, originality, and maintenance
- SEO Accessibility Agent: semantic structure, keyboard use, readable states, and assistive-technology access
- Security and Data Owner: source integrity, injection risks, access controls, secrets, and rollback
- Privacy, Legal, or Compliance Agent: personal data, regulated claims, licensing, disclosures, and jurisdictional risk
- SEO ScrumMaster Agent: independent challenge, conflict resolution, gate enforcement, and escalation

## Source-of-truth order

1. Current Google Search Essentials and spam policies
2. Current Google crawling, canonicalization, JavaScript, and sitemap documentation
3. Verified site evidence: rendered pages, source data, logs, Search Console, analytics, and crawl output
4. This skill's internal governance thresholds
5. Third-party research, labeled `ANALYSIS`

When a current primary source conflicts with this file, follow the primary source and record the conflict. Do not present an internal threshold as a Google rule.

## Operating modes

- `PLAN`: assess feasibility and define the governed architecture before development.
- `AUDIT`: inspect an existing or proposed page set and issue a launch or remediation decision.
- `PILOT`: evaluate a limited production canary before expansion.
- `MONITOR`: compare current performance, quality, and indexation against the approved baseline.
- `INCIDENT`: contain harmful, incorrect, hacked, or unexpectedly indexed generated pages.

## Required inputs

For every mode:

- business objective and the user job each page is intended to solve
- projected page count, template families, URL patterns, and target markets or languages
- source dataset or representative extract, field definitions, provenance, refresh cadence, and accountable owner
- whether content is first-party, user-generated, licensed, syndicated, freelance, white-label, or otherwise third-party
- known data-use, privacy, contractual, accessibility, and regulatory constraints

Before any launch approval:

- template code, rendered samples, or a reproducible page-generation specification
- indexation plan, canonical rules, sitemap rules, internal-linking plan, monitoring plan, and rollback method
- search demand, customer evidence, operational need, or another documented basis for the page types
- an approved score model or permission to use this skill's diagnostic model

For existing page sets, also request crawl, indexation, Search Console, analytics, conversion, error, and quality data. If a mode-required input is missing, return `PARTIAL` or `BLOCKED`; do not infer approval.

## Execution status

Report execution status separately from the launch decision:

- `COMPLETE`: all required checks for the selected mode ran with sufficient evidence
- `PARTIAL`: useful checks ran, but one or more required evidence areas are missing
- `BLOCKED`: the review cannot proceed or a hard stop prevents approval
- `FAILED`: the workflow terminated because of an execution or integrity error

A `COMPLETE` audit may still result in a `BLOCKED` launch decision.

## Evidence labels

- `FACT`: directly observed, measured, or confirmed by a current primary source
- `ANALYSIS`: reasoned interpretation supported by cited evidence
- `HYPOTHESIS`: unverified proposition requiring a test
- `UNKNOWN`: evidence is unavailable or contradictory

Every finding must include evidence, confidence, affected scope, impact, effort, risk, owner, acceptance criteria, and verification method.

## Execution protocol

### 1. Define the page-set thesis

Document:

- the user need and intended action
- why a separate page is necessary
- what information or functionality is unique to that page
- how the page differs from the nearest sibling pages
- why the page belongs on this domain and within its normal subject area
- the success metric beyond raw page count or impressions

Fail the thesis when the primary purpose is to capture query variations rather than help users.

### 2. Audit the data foundation

For each source and field, record:

- provenance, license or permission, and collection method
- freshness, update frequency, and stale-data behavior
- null rate, duplicate rate, valid-value rate, and referential integrity
- geographic, temporal, product, or population coverage
- personally identifiable, confidential, regulated, or security-sensitive data
- transformation rules and whether any generative system can alter factual values
- owner, change history, and rollback path

Do not publish claims generated from missing, fabricated, unlicensed, or materially stale data. Generative systems may transform approved evidence but must not invent factual attributes.

### 3. Build the intent and entity map

Group proposed URLs by user intent, entity, geography, language, and conversion path. Identify:

- pages that solve genuinely different user needs
- pages that target substantially the same query and lead to the same destination
- pages that exist only to funnel users to another usable page
- records that should be consolidated into a category, directory, comparison, or aggregate page
- entities that lack enough verified information for a standalone page

Doorway-like or duplicate-intent clusters are a hard stop until consolidated or redesigned.

### 4. Test page-level value

Evaluate a stratified sample from every template family, market, data-quality band, and known outlier group. Review all high-risk or exception groups. As an internal default, inspect at least 30 rendered pages per template family when the population permits, then expand sampling until no new material defect class appears.

For every sampled page, answer:

- Does it satisfy its stated user need without requiring another page to become useful?
- Does it contain verified page-specific facts, analysis, media, tools, inventory, availability, instructions, or other substantive value?
- Is the principal value visible in the rendered page and accessible on mobile?
- Does it clearly identify the entity, geography, date, and limitations?
- Would the page still deserve publication if search engines did not exist?
- Is it materially better than a search-results-like list, a variable-swapped template, or the destination page it funnels toward?

Shared navigation, legal text, design components, and reusable explanatory content are not automatically harmful. Measure whether the page-specific contribution is sufficient for the user need rather than relying on word count alone.

### 5. Measure similarity and distinctness

Use multiple diagnostics; do not make a launch decision from a single similarity percentage.

Recommended diagnostics:

- exact and near-duplicate body detection
- normalized n-gram or shingle similarity
- static-to-dynamic content ratio
- field-level overlap and repeated claim patterns
- entity and intent collision rate
- unique verified facts or functional outputs per page
- internal-link and conversion-destination overlap
- title, heading, metadata, and structured-data duplication

High similarity is a review trigger. It becomes a stop condition when substantially similar pages serve the same intent, provide little added value, or function as doorways.

### 6. Audit templates and generation controls

Require:

- deterministic separation of source facts, generated interpretation, and template copy
- source references or traceability for material claims
- validation for nulls, malformed records, invalid combinations, and outliers
- escaping, sanitization, and safe handling of user-supplied or third-party data
- defenses against prompt injection, template injection, unsafe URLs, executable payloads, source data attempting to alter system instructions, and accidental exposure of credentials or secrets
- consistent titles and headings that describe the actual page
- accessible semantic HTML and crawlable `<a href>` links
- server-rendered or reliably rendered primary content
- visible error and empty states that do not masquerade as complete pages
- human review or automated blocking for high-risk claims and regulated topics
- versioning, audit logs, preview, approval, and rollback controls

Block pages that claim functionality, availability, inventory, pricing, locations, or outcomes the underlying data does not support.

### 7. Govern URLs, canonicals, robots, and sitemaps

- Give each approved indexable page one stable, descriptive URL.
- Use self-referencing canonicals on primary pages.
- Use canonicalization only for duplicate or very similar URLs; do not canonicalize a distinct page merely because it performs poorly.
- Keep internal links, redirects, canonicals, and sitemap URLs consistent.
- Do not use `robots.txt` to deindex pages or as a canonicalization method.
- When using `noindex`, allow crawling long enough for the directive to be seen, and exclude the URL from XML sitemaps.
- Include only preferred, canonical, indexable URLs in sitemaps.
- Use accurate `<lastmod>` values tied to meaningful page updates, not every build or request.
- Split a sitemap before it exceeds 50,000 URLs or 50 MB uncompressed.
- Return truthful HTTP status codes: `200` for valid pages, `404` or `410` for removed records, and appropriate `5xx` responses for temporary server failures.
- Prevent infinite parameter, calendar, search, sort, filter, and pagination spaces unless each crawlable URL is intentionally governed.

### 8. Assess crawl and indexation risk

Crawl-budget work is relevant mainly to very large or rapidly changing sites, or sites showing discovery and indexing problems. Do not invoke crawl budget as a generic reason to remove useful pages.

Review:

- generated URL population versus approved indexable population
- orphan pages and crawl depth
- duplicate and parameterized URLs
- server capacity, latency, and error rates
- rendered-content availability
- sitemap and internal-link discovery
- Search Console page-indexing states
- crawl-stat patterns for large or fast-changing sites

A crawlable URL is not guaranteed to be indexed or served. Never promise indexation, traffic, rankings, or AI citations.

### 9. Apply policy and abuse gates

#### Hard stops

Return `BLOCKED` when any of these is observed:

- pages are generated primarily to manipulate rankings rather than help users
- substantially similar city, region, product, service, or query pages funnel users to the same destination
- scraped, stitched, translated, synonymized, or AI-generated content adds little or no original value
- third-party content is placed on a host primarily to exploit the host's ranking signals
- the dataset is fabricated, materially unreliable, unlicensed, unlawfully obtained, or unsafe to publish
- sensitive or regulated data lacks required controls or approval
- pages expose fake, unavailable, or misleading functionality
- primary content is inaccessible to users or cannot be reliably crawled and rendered
- the generator can publish uncontrolled factual hallucinations
- there is no practical way to stop publishing, remove affected URLs, or roll back a defective release

#### Warnings requiring remediation or explicit approval

- sparse records or material null rates
- strong content and intent similarity without demonstrated user value
- weak internal linking or browse hierarchy
- stale data without a visible date or stale-state treatment
- unverified generated summaries
- pages outside the site's normal subject area
- heavy dependence on a single volatile source
- low evidence coverage in the reviewed sample
- indexation growth that materially outpaces quality review and monitoring capacity

Internal warning thresholds are configurable. Page count, word count, AI use, human review, or a shared-template percentage must never be treated as standalone proof of compliance or a Google policy violation. Third-party content is not automatically abusive; the purpose, user value, editorial relationship, and use of the host site's ranking signals determine the risk.

### 10. Score without hiding uncertainty

Use the following kit-defined diagnostic model unless a canonical project model overrides it:

| Dimension | Weight |
|---|---:|
| Standalone user value | 25 |
| Data quality and traceability | 20 |
| Intent and entity distinctness | 15 |
| Template, rendering, and accessibility quality | 15 |
| URL, internal-linking, canonical, and indexation governance | 15 |
| Monitoring, ownership, approval, and rollback | 10 |

Score only dimensions supported by evidence. Report `score_coverage` separately. Do not publish an overall score when less than 80% of the weighted model has direct evidence; return `INSUFFICIENT_EVIDENCE` instead. A high score cannot override a hard stop.

### 11. Issue the launch decision

Before the decision, the SEO ScrumMaster Agent must challenge the page-set thesis, sampling coverage, strongest approval argument, strongest blocking argument, unresolved `UNKNOWN` findings, and rollback readiness. Record disagreements and their resolution; do not collapse dissent into an unsupported consensus.

Allowed decisions:

- `APPROVED_CANARY`: limited release only; no hard stops; monitoring and rollback ready
- `APPROVED_STAGED`: canary passed and expansion gates are satisfied
- `HOLD_FOR_REWORK`: remediable warnings or insufficient evidence prevent approval
- `BLOCKED`: one or more hard stops are present

No agent may silently override a hard stop. Exception requests require an accountable business owner, SEO Technical Agent, SEO ScrumMaster Agent, and any required Security, Privacy, Legal, or Compliance reviewer. Releases with material brand, regulatory, financial, or irreversible indexation risk also require written Executive Sponsor or VP review. An exception does not convert an observed or suspected policy violation into an approved SEO practice.

### 12. Roll out progressively

Use a risk-based canary rather than a fixed universal batch size. The canary must represent every template family and high-risk data segment while remaining small enough to remove quickly.

Before launch, capture:

- approved URL inventory and configuration version
- rendered-page and source-data samples
- crawl, indexation, traffic, conversion, and error baselines
- monitoring owners, alert thresholds, and rollback commands

Expand only after the observation window is long enough to assess crawling, indexation, user behavior, conversion, support impact, errors, and data freshness for the site's normal demand cycle. Do not use ranking movement alone as the expansion gate.

### 13. Monitor and remediate

Monitor by template, market, data cohort, and release version:

- valid, excluded, duplicate, crawled-not-indexed, and discovered-not-indexed states
- organic entrances, engagement, conversions, assisted outcomes, and support signals
- server errors, rendering failures, stale records, broken links, and empty states
- canonical selection and sitemap consistency
- duplicate-intent and cannibalization patterns
- policy, security, privacy, legal, and brand complaints
- source-data drift and unexpected page-count growth

When a release causes material harm, stop expansion, preserve evidence, roll back or deindex the affected cohort, diagnose the root cause, and require reapproval before republishing.

## Output contract

Return one governance report containing:

1. Mode, scope, page population, template families, markets, and evidence date
2. Source-of-truth and evidence register
3. Data-quality and provenance assessment
4. Intent/entity map and consolidation candidates
5. Sampling method, sample coverage, and observed defect classes
6. Page-value, similarity, rendering, accessibility, and template findings
7. URL, canonical, robots, sitemap, crawl, and indexation findings
8. Policy and abuse gate table with `PASS`, `WARN`, `STOP`, or `UNKNOWN`
9. Weighted diagnostic score and score coverage, when permitted
10. Deduplicated, prioritized actions with one canonical finding per root cause and all supporting evidence attached; include confidence, impact, effort, risk, owner, acceptance criteria, and verification method
11. Launch decision and exact reasons
12. Canary, monitoring, expansion, rollback, and reapproval plan
13. Skipped checks, contradictory evidence, blockers, limitations, and the exact conditions required to move to the next decision state

## Failure and fallback handling

- **Source data unavailable:** return `BLOCKED` for launch approval; provide only a conditional review plan.
- **Rendered samples unavailable:** return `PARTIAL`; do not claim page-level value, mobile, accessibility, or rendering checks passed.
- **Population too large for full review:** use stratified and risk-based sampling, disclose coverage, and do not generalize beyond supported cohorts.
- **Similarity tooling unavailable:** perform manual cluster review and label similarity conclusions `ANALYSIS`.
- **Search Console or analytics unavailable:** evaluate prelaunch quality, but return monitoring readiness as `UNKNOWN` and limit approval to a removable canary.
- **Conflicting evidence:** preserve both sources, identify the authority and freshness difference, and do not resolve by assumption.
- **Hard stop present:** issue `BLOCKED`; do not replace the decision with owner sign-off language.

## Current primary references

Re-verify before client-facing use:

- Google Search spam policies: `https://developers.google.com/search/docs/essentials/spam-policies`
- Helpful, reliable, people-first content: `https://developers.google.com/search/docs/fundamentals/creating-helpful-content`
- Canonicalization: `https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls`
- JavaScript SEO: `https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics`
- Robots.txt limits: `https://developers.google.com/search/docs/crawling-indexing/robots/intro`
- Sitemap requirements: `https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap`
- Crawl-budget guidance: `https://developers.google.com/crawling/docs/crawl-budget`
