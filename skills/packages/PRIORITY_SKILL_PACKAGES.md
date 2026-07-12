# Priority Skill Packages

Each anchored package is a self-contained execution contract. `skills/deep-skill-procedures.md` remains the procedure authority.

<a id="full-site-audit"></a>
## `full-site-audit`

Coordinate evidence-backed technical, content, authority, local, accessibility, and reporting work into one bounded audit.

- Class: `executable`
- Commands: `system.run`
- Owners: SEO Full Audit/Analyst Agent, Senior SEO Strategist Agent
- References: `knowledge/reference-packs/technical-search.md`, `knowledge/reference-packs/content-and-ai-search.md`, `knowledge/seo-quality-gates.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="technical-audit"></a>
## `technical-audit`

Diagnose crawlability, indexability, redirect, canonical, sitemap, robots, rendering, and status-code evidence.

- Class: `executable`
- Commands: `technical.robots`, `technical.sitemap`, `technical.redirect-chain`, `technical.indexability`
- Owners: SEO Technical Agent
- References: `knowledge/reference-packs/technical-search.md`, `knowledge/seo-quality-gates.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="content-brief"></a>
## `content-brief`

Produce an evidence-gated brief only after relevance, intent, SERP, source, and information-gain checks pass.

- Class: `executable`
- Commands: `content.relevance`, `content.serp`, `content.brief-decision`, `content.brief`
- Owners: SEO Copywriter/Content Agent
- References: `knowledge/reference-packs/content-and-ai-search.md`, `knowledge/eeat-quality-rubric.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="schema-detect-validate-generate"></a>
## `schema-detect-validate-generate`

Inspect, validate, and generate bounded JSON-LD from observed or operator-supplied facts.

- Class: `executable`
- Commands: `schema.detect`, `schema.validate`, `schema.generate`
- Owners: SEO Technical Agent, Senior SEO Engineer Agent
- References: `knowledge/reference-packs/technical-search.md`, `knowledge/schema-deprecation-registry.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="core-web-vitals-triage"></a>
## `core-web-vitals-triage`

Separate field and lab evidence, identify material performance constraints, and define verifiable remediation.

- Class: `executable`
- Commands: `google.pagespeed`, `google.crux-current`, `google.crux-history`, `google.lcp-subparts`, `technical.cwv`
- Owners: SEO Technical Agent, SEO Diagnostic Infrastructure Agent
- References: `knowledge/reference-packs/technical-search.md`, `knowledge/core-web-vitals-gates.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="local-seo-audit"></a>
## `local-seo-audit`

Assess business identity, location evidence, local landing pages, citations, GBP inputs, and NAP consistency without inventing rank.

- Class: `advisory`
- Commands: none; advisory
- Owners: Local SEO Agent
- References: `knowledge/reference-packs/local-ecommerce-programmatic.md`, `knowledge/seo-vertical-profiles.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="hreflang-audit"></a>
## `hreflang-audit`

Validate locale targeting, return links, canonical alignment, and language-region coverage.

- Class: `executable`
- Commands: `technical.hreflang`
- Owners: International & Multilingual SEO Agent
- References: `knowledge/reference-packs/technical-search.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="content-audit"></a>
## `content-audit`

Evaluate measurable content quality, source support, entity evidence, clarity, and comparative structure.

- Class: `executable`
- Commands: `content.quality`, `content.verify`, `content.entities`, `content.compare`, `content.humanize`
- Owners: SEO Copywriter/Content Agent, SEO Compliance & Legal Agent
- References: `knowledge/reference-packs/content-and-ai-search.md`, `knowledge/eeat-quality-rubric.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="content-decay"></a>
## `content-decay`

Compare compatible periods, identify material decline, and avoid unsupported causal attribution.

- Class: `executable`
- Commands: `content.decay`
- Owners: SEO Copywriter/Content Agent, Predictive SEO Trend Agent
- References: `knowledge/reference-packs/experimentation-reporting-platforms.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="competitor-comparison-page-build"></a>
## `competitor-comparison-page-build`

Build evidence-backed comparison or alternatives content without unsupported superiority or fabricated claims.

- Class: `executable`
- Commands: `content.compare`, `content.brief`
- Owners: Competitive Intelligence Agent, SEO Copywriter/Content Agent
- References: `knowledge/reference-packs/content-and-ai-search.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="programmatic-seo-governance"></a>
## `programmatic-seo-governance`

Control scaled-page eligibility, uniqueness, indexation, doorway risk, quality gates, and rollback.

- Class: `advisory`
- Commands: none; advisory
- Owners: Senior SEO Strategist Agent, SEO Compliance & Legal Agent
- References: `knowledge/reference-packs/local-ecommerce-programmatic.md`, `knowledge/reference-packs/authority-spam-privacy.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="product-page-seo-audit"></a>
## `product-page-seo-audit`

Audit product content, identity, structured data, crawlability, availability, and merchant consistency.

- Class: `executable`
- Commands: `content.quality`, `schema.detect`, `schema.validate`, `technical.indexability`
- Owners: SEO E-commerce Agent, SEO Technical Agent
- References: `knowledge/reference-packs/local-ecommerce-programmatic.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="backlink-profile"></a>
## `backlink-profile`

Normalize supplied or public crawl evidence while preserving source limitations and avoiding invented authority scores.

- Class: `executable`
- Commands: `links.commoncrawl`, `links.profile`
- Owners: Digital PR & Programmatic Link Outreach Agent
- References: `knowledge/reference-packs/authority-spam-privacy.md`, `knowledge/free-backlink-sources.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="geo-aio-citation-audit"></a>
## `geo-aio-citation-audit`

Assess answer-surface visibility and citation readiness from dated observations and entity evidence.

- Class: `hybrid`
- Commands: `content.entities`, `content.verify`
- Owners: GEO / AIO Optimization Agent, SEO Knowledge Graph Sync Agent
- References: `knowledge/reference-packs/content-and-ai-search.md`, `knowledge/geo-readiness-rubric.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="seo-drift-monitor"></a>
## `seo-drift-monitor`

Capture and compare compatible tamper-evident page-state snapshots without creating a second evidence store.

- Class: `executable`
- Commands: `drift.baseline`, `drift.compare`, `drift.history`, `drift.report`, `drift.watch`
- Owners: SEO Full Audit/Analyst Agent, SEO Diagnostic Infrastructure Agent
- References: `knowledge/reference-packs/experimentation-reporting-platforms.md`, `docs/evidence-cache-contract.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="rendered-visual-audit"></a>
## `rendered-visual-audit`

Inspect rendered output and screenshots with bounded browser controls and truthful dependency states.

- Class: `executable`
- Commands: `render.health`, `render.page`, `render.screenshot`
- Owners: SEO Diagnostic Infrastructure Agent, SEO Technical Agent
- References: `knowledge/reference-packs/technical-search.md`, `knowledge/reference-packs/accessibility-media.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="consent-mode-diagnostic"></a>
## `consent-mode-diagnostic`

Diagnose supplied Consent Mode configuration evidence without granting consent or claiming legal compliance.

- Class: `executable`
- Commands: `privacy.consent`
- Owners: SEO Compliance & Legal Agent
- References: `knowledge/reference-packs/authority-spam-privacy.md`, `knowledge/dma-consent-mode-v2.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="technical-implementation"></a>
## `technical-implementation`

Translate accepted findings into bounded code or configuration changes with tests, approvals, and rollback.

- Class: `executable`
- Commands: `schema.generate`, `indexnow.validate`, `indexnow.submit`
- Owners: Senior SEO Engineer Agent
- References: `knowledge/reference-packs/technical-search.md`, `knowledge/reference-packs/experimentation-reporting-platforms.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="compliance-review"></a>
## `compliance-review`

Review claims, disclosures, consent evidence, platform policies, and unresolved legal-review requirements.

- Class: `executable`
- Commands: `content.verify`, `privacy.consent`
- Owners: SEO Compliance & Legal Agent
- References: `knowledge/reference-packs/authority-spam-privacy.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.

<a id="single-page-audit"></a>
## `single-page-audit`

Run a bounded page-level technical, rendered, structured-data, performance, and content review.

- Class: `executable`
- Commands: `render.page`, `technical.indexability`, `technical.cwv`, `schema.detect`, `content.quality`
- Owners: SEO Technical Agent, SEO Full Audit/Analyst Agent
- References: `knowledge/reference-packs/technical-search.md`, `knowledge/reference-packs/content-and-ai-search.md`
- Inputs: approved scope, owning-agent evidence, market/device/locale/date context, output requirements, and acceptance criteria.
- Gate: evidence sufficiency, schema-compatible output, explicit limitations, owner, verification, and rollback when applicable.
- Failure: return `INSUFFICIENT_EVIDENCE`, `NOT_CONFIGURED`, `BLOCKED`, or `FAILED`; never convert missing data into success.
