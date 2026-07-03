# Additional Skill Definitions

This file defines specialist skills referenced by agents and workflows that are not covered in the core skill group files.

## `technical-implementation`

Purpose: Convert approved SEO technical recommendations into scoped, testable implementation plans or code changes.

System prompt: Act as a senior SEO engineer. Preserve existing application patterns, minimize blast radius, and verify rendered SEO behavior after implementation.

Required inputs:

- Technical issue
- Affected files/templates/routes
- Acceptance criteria
- Risk level

Execution steps:

1. Inspect the current implementation.
2. Identify the smallest safe change.
3. Map the change to files, routes, and templates.
4. Define tests or verification steps.
5. Implement only after approval when risk is high or critical.

Output format:

- `templates/engineering-change-plan.md`

Quality gate:

- The plan includes rollback, verification, and no unrelated refactors.

Failure conditions:

- Codebase unavailable, unclear routing model, or missing approval for high-risk changes.

Fallback:

- Produce an implementation ticket instead of editing.

## `request-routing`

Purpose: Select the correct lead agent, supporting agents, workflow, and risk gate for an incoming SEO request.

System prompt: Route the request based on ownership, final deliverable, risk, and required evidence. Do not activate unnecessary agents.

Required inputs:

- User request
- Known business context
- Risk indicators
- Desired deliverable

Execution steps:

1. Classify the request as audit, implementation, strategy, monitoring, research, or debate.
2. Select the lead agent that owns the final deliverable.
3. Add supporting agents only when their expertise is necessary.
4. Check for risk gates and compliance/security triggers.
5. Select the matching workflow.

Output format:

- Lead agent
- Supporting agents
- Workflow
- Required evidence
- Escalation needs

Quality gate:

- The route must minimize unnecessary agent activation while covering all material risks.

Failure conditions:

- Request is ambiguous or lacks target/domain/context.

Fallback:

- Ask for the minimum missing clarification or route to SEO Scrummaster Agent for triage.

## `analytics-synthesis`

Purpose: Combine analytics, Search Console, rank, and conversion data into SEO performance insight.

System prompt: Separate first-party truth from estimates. Label missing data and avoid causal claims without evidence.

Required inputs:

- Date range
- Analytics export or access
- Search Console export or access
- Conversion goals

Execution steps:

1. Normalize date ranges.
2. Segment organic traffic.
3. Compare clicks, impressions, CTR, position, sessions, and conversions.
4. Identify winners, losers, and anomalies.
5. Connect findings to pages, queries, or templates.

Output format:

- Agent output schema or `templates/audit-report.md`

Quality gate:

- Metrics must state source and date range.

Failure conditions:

- Missing first-party data or mismatched date ranges.

Fallback:

- Use available data and mark confidence Low or Medium.

## `score-normalization`

Purpose: Convert specialist findings into a consistent audit score.

System prompt: Score conservatively. Apply hard caps for critical indexation, security, or manual-action risks.

Required inputs:

- Specialist outputs
- Scoring model
- Missing data list

Execution steps:

1. Score each pillar using `knowledge/scoring-model.md`.
2. Apply missing-data confidence adjustments.
3. Apply hard caps.
4. Document why each score was assigned.

Output format:

- Audit score table in `templates/audit-report.md`

Quality gate:

- No score may be emitted without rationale.

Failure conditions:

- Missing specialist outputs.

Fallback:

- Emit provisional score with explicit confidence.

## `decision-record`

Purpose: Capture major SEO decisions and the reasoning behind them.

System prompt: Preserve evidence, counterarguments, risks, conditions, and rollback requirements.

Required inputs:

- Proposal
- Evidence
- Risk level
- Decision owner

Execution steps:

1. Summarize proposal.
2. List evidence and counterarguments.
3. Assign risk.
4. Decide Approve, Revise, Reject, or Defer.
5. Define verification and rollback.

Output format:

- `templates/decision-record.md`
- `schemas/decision-record.schema.json`

Quality gate:

- High-risk approvals require verification and rollback.

Failure conditions:

- Evidence unavailable.

Fallback:

- Defer decision and request evidence.

## `definition-of-done`

Purpose: Define completion criteria for SEO tasks.

System prompt: Make done measurable, observable, and safe.

Required inputs:

- Task
- Risk level
- Owner
- Affected pages or systems

Execution steps:

1. Define user-visible outcome.
2. Define SEO signal outcome.
3. Define verification method.
4. Define rollback or monitoring requirement.

Output format:

- Checklist in `templates/seo-sprint-plan.md`

Quality gate:

- Every done item must be verifiable.

Failure conditions:

- Undefined owner or missing evidence.

Fallback:

- Mark task not ready.

## `sitemap-audit`

Purpose: Validate XML sitemap coverage, cleanliness, freshness, and alignment with canonical URLs.

System prompt: Treat sitemaps as canonical URL discovery hints, not as indexation guarantees.

Required inputs:

- XML sitemap URLs
- Crawl inventory
- Canonical status
- HTTP status codes

Execution steps:

1. Parse sitemap files and sitemap indexes.
2. Check status codes and canonical alignment.
3. Identify missing valuable URLs.
4. Identify low-value, redirected, blocked, or error URLs.
5. Review lastmod accuracy.

Output format:

- Audit finding or technical ticket.

Quality gate:

- Sitemap recommendations must align with indexation strategy.

Failure conditions:

- Sitemap unavailable or blocked.

Fallback:

- Use crawl inventory and mark sitemap unavailable.

## `redirect-validation`

Purpose: Validate redirects for migrations, canonicalization, and broken URL recovery.

System prompt: Protect link equity and user experience. Avoid chains, loops, and irrelevant redirects.

Required inputs:

- Redirect map
- Source URLs
- Destination URLs
- Status codes

Execution steps:

1. Check every source URL status.
2. Follow redirect chain.
3. Confirm final destination relevance and 200 status.
4. Flag loops, chains, soft 404s, and irrelevant destinations.

Output format:

- Technical ticket or migration validation report.

Quality gate:

- Redirects must preserve intent and resolve in one hop when possible.

Failure conditions:

- Source URL list missing.

Fallback:

- Sample high-value URLs first.

## `seo-ci-checks`

Purpose: Define automated checks that prevent SEO regressions.

System prompt: Prefer simple, reliable checks that fail only on material SEO regressions.

Required inputs:

- Framework
- Critical routes
- SEO requirements

Execution steps:

1. Identify route samples.
2. Define checks for title, meta description, canonical, robots, status, schema, and links.
3. Add accessibility or performance checks where feasible.
4. Integrate with CI.

Output format:

- `templates/engineering-change-plan.md`

Quality gate:

- Checks must be deterministic enough for CI.

Failure conditions:

- No runnable app or route list.

Fallback:

- Provide manual QA checklist.

## `competitive-gap`

Purpose: Identify competitor keyword, content, SERP feature, link, and AI citation gaps.

System prompt: Extract patterns and opportunities; do not copy competitors.

Required inputs:

- Target domain
- Competitors
- Topic or market

Execution steps:

1. Collect competitor ranking/content/link signals.
2. Group gaps by intent and funnel stage.
3. Score by relevance, value, difficulty, and fit.
4. Recommend response actions.

Output format:

- `templates/competitive-intelligence-brief.md`

Quality gate:

- Opportunities must map to user intent and business relevance.

Failure conditions:

- Competitors unknown.

Fallback:

- Infer competitor set and mark confidence.

## `accessibility-audit`

Purpose: Evaluate accessibility issues that affect users and SEO quality.

System prompt: Apply accessibility as a user-value requirement, not a compliance checkbox.

Required inputs:

- Rendered page or component
- HTML/DOM
- Screenshots when available

Execution steps:

1. Check headings.
2. Check alt text and media alternatives.
3. Check labels, controls, keyboard access, focus, and contrast.
4. Prioritize by user impact and SEO impact.

Output format:

- `templates/accessibility-seo-report.md`

Quality gate:

- Recommendations must improve real user access.

Failure conditions:

- Rendered page unavailable.

Fallback:

- Review static markup and mark limitations.

## `brand-serp-audit`

Purpose: Review what appears for brand queries and how consistently the brand/entity is represented.

System prompt: Treat the brand SERP as an entity trust surface.

Required inputs:

- Brand name
- Domain
- Target market

Execution steps:

1. Capture brand SERP snapshot.
2. Identify owned, earned, and third-party results.
3. Check entity consistency.
4. Flag reputation, confusion, or missing profile issues.

Output format:

- `templates/entity-sync-report.md`

Quality gate:

- Do not fabricate entity authority.

Failure conditions:

- SERP unavailable.

Fallback:

- Use known owned profiles and mark SERP snapshot missing.

## `official-source-monitor`

Purpose: Monitor official search, structured data, accessibility, and policy sources for changes.

System prompt: Only official or first-party sources can create high-confidence rule updates.

Required inputs:

- Source list
- Last checked date

Execution steps:

1. Check official sources.
2. Detect material changes.
3. Summarize operational impact.
4. Draft rule update if needed.

Output format:

- `templates/knowledge-update.md`

Quality gate:

- Source URL and confidence must be included.

Failure conditions:

- Source inaccessible.

Fallback:

- Schedule recheck and do not update rules.

## `negative-seo-threat-review`

Purpose: Assess possible negative SEO attacks or malicious organic visibility risks.

System prompt: Require evidence. Avoid panic, accusations, or automatic disavow actions.

Required inputs:

- Backlink data
- GSC manual/security actions
- Logs or index samples when available

Execution steps:

1. Identify anomaly.
2. Compare against baseline.
3. Determine likely harm.
4. Recommend monitoring, cleanup, or escalation.

Output format:

- `templates/security-seo-report.md`

Quality gate:

- No disavow recommendation without human review.

Failure conditions:

- No baseline.

Fallback:

- Establish baseline first.

## `security-indexation-check`

Purpose: Detect hacked, spam, malware, or index-pollution issues.

System prompt: Treat security risks as SEO and user trust risks.

Required inputs:

- Index samples
- Security reports
- Crawl data
- Server logs when available

Execution steps:

1. Search for suspicious indexed URLs.
2. Check unexpected templates, parameters, or languages.
3. Review security warnings.
4. Recommend containment and cleanup.

Output format:

- `templates/security-seo-report.md`

Quality gate:

- Critical security issues require escalation.

Failure conditions:

- No index evidence.

Fallback:

- Create monitoring task.

## `forecasting`

Purpose: Estimate future SEO opportunity or risk from historical and trend signals.

System prompt: Forecast ranges, not certainties.

Required inputs:

- Historical query/page data
- Seasonality
- Market context

Execution steps:

1. Establish baseline.
2. Identify seasonality and anomalies.
3. Estimate range.
4. State assumptions.

Output format:

- `templates/trend-opportunity-brief.md`

Quality gate:

- Forecast must include confidence and assumptions.

Failure conditions:

- Insufficient history.

Fallback:

- Use directional scenario planning.

## `trend-monitor`

Purpose: Detect emerging topics, seasonal demand, and search behavior changes.

System prompt: Corroborate trends before recommending production work.

Required inputs:

- Trend sources
- Keyword or topic set
- Monitoring cadence

Execution steps:

1. Collect signals.
2. Score by relevance and growth.
3. Cross-check with business fit.
4. Trigger content or strategy brief.

Output format:

- `templates/trend-opportunity-brief.md`

Quality gate:

- Do not treat one source as proof.

Failure conditions:

- No corroboration.

Fallback:

- Add to watchlist.

## `citation-audit`

Purpose: Check local citation consistency and coverage.

System prompt: Validate real business information only.

Required inputs:

- NAP
- Location list
- Citation sources

Execution steps:

1. Compare NAP across sources.
2. Flag inconsistencies.
3. Identify missing priority citations.
4. Prioritize fixes.

Output format:

- `templates/local-seo-report.md`

Quality gate:

- No fake or duplicate locations.

Failure conditions:

- Unverified business data.

Fallback:

- Request source-of-truth NAP.

## `review-strategy`

Purpose: Create an ethical review acquisition and response plan.

System prompt: Improve review quality without manipulation.

Required inputs:

- Review platforms
- Current review profile
- Customer touchpoints

Execution steps:

1. Assess review volume, velocity, rating, and themes.
2. Identify compliant request moments.
3. Draft response guidelines.
4. Define monitoring cadence.

Output format:

- `templates/local-seo-report.md`

Quality gate:

- No incentives, gating, or fake reviews.

Failure conditions:

- Platform policy unknown.

Fallback:

- Use conservative request guidance.

## `local-landing-page-brief`

Purpose: Create a useful local landing page brief.

System prompt: Avoid doorway pages. Each page must serve a real local audience.

Required inputs:

- Location
- Services
- Local proof
- Search intent

Execution steps:

1. Define local intent.
2. Add unique location proof.
3. Map services and FAQs.
4. Add schema and conversion guidance.

Output format:

- `templates/content-brief.md`

Quality gate:

- Page must contain unique, useful local information.

Failure conditions:

- No real business presence.

Fallback:

- Recommend broader service-area page.

## `content-inventory`

Purpose: Catalog pages by topic, intent, performance, and action.

System prompt: Build a decision-ready inventory, not a raw URL dump.

Required inputs:

- URL list
- Performance data when available
- Content metadata

Execution steps:

1. Classify page type and intent.
2. Attach performance signals.
3. Identify duplicates, gaps, and decay.
4. Assign keep, refresh, consolidate, prune, or create.

Output format:

- `templates/ia-map.md`

Quality gate:

- Every action must have a reason.

Failure conditions:

- No URL inventory.

Fallback:

- Start from sitemap or crawl sample.

## `conversational-query-map`

Purpose: Map natural-language questions to pages and answer formats.

System prompt: Optimize for useful answers, not thin FAQ expansion.

Required inputs:

- Topic
- Query/question sources
- Existing pages

Execution steps:

1. Collect who/what/when/where/why/how questions.
2. Group by intent.
3. Map to existing or new pages.
4. Define answer block requirements.

Output format:

- `templates/conversational-seo-plan.md`

Quality gate:

- Avoid duplicate FAQ variants.

Failure conditions:

- No question sources.

Fallback:

- Use customer support and sales questions if available.

## `international-url-architecture`

Purpose: Design URL patterns for multilingual and multiregional SEO.

System prompt: Prioritize clarity, maintainability, and correct targeting.

Required inputs:

- Markets
- Languages
- CMS/routing constraints

Execution steps:

1. Choose ccTLD, subdomain, or subfolder model.
2. Define locale slug rules.
3. Align canonicals and hreflang.
4. Plan sitemap structure.

Output format:

- `templates/international-seo-report.md`

Quality gate:

- Architecture must support reciprocal hreflang.

Failure conditions:

- Market requirements unknown.

Fallback:

- Recommend conservative subfolder model with review.

## `localized-content-review`

Purpose: Review localized content for quality and market fit.

System prompt: Localization is not word-for-word translation.

Required inputs:

- Source content
- Localized content
- Target market

Execution steps:

1. Check intent match.
2. Check terminology and cultural fit.
3. Check legal/commercial claims.
4. Flag machine-translation artifacts.

Output format:

- `templates/international-seo-report.md`

Quality gate:

- Critical pages require native or expert review.

Failure conditions:

- Reviewer lacks market context.

Fallback:

- Mark for local expert review.

## `regional-keyword-map`

Purpose: Map topics to region-specific search language and demand.

System prompt: Do not assume one market's keyword set applies globally.

Required inputs:

- Markets
- Products/services
- Seed topics

Execution steps:

1. Gather regional query variants.
2. Group by intent.
3. Map to localized pages.
4. Note regional search engine differences.

Output format:

- `templates/international-seo-report.md`

Quality gate:

- Market-specific terms must be preserved.

Failure conditions:

- No regional data.

Fallback:

- Use qualitative market research and mark confidence.

## `digital-pr-asset-brief`

Purpose: Define a link-worthy PR asset.

System prompt: Earn links through usefulness, data, originality, or expert value.

Required inputs:

- Audience
- Topic
- Existing assets
- Publication targets

Execution steps:

1. Identify journalist/editor value.
2. Define asset angle.
3. Define evidence or data needed.
4. Map outreach targets.

Output format:

- `templates/outreach-campaign.md`

Quality gate:

- Asset must be genuinely useful and non-manipulative.

Failure conditions:

- No credible asset angle.

Fallback:

- Recommend research or data collection first.

## `outreach-prospecting`

Purpose: Build a qualified outreach list.

System prompt: Relevance beats volume.

Required inputs:

- Asset
- Target audience
- Exclusion rules

Execution steps:

1. Find relevant publications or pages.
2. Score relevance, authority, and risk.
3. Identify angle and contact path.
4. Exclude low-quality prospects.

Output format:

- `templates/outreach-campaign.md`

Quality gate:

- Do not include paid-link or irrelevant prospects.

Failure conditions:

- Asset not defined.

Fallback:

- Build asset brief first.

## `competitor-change-monitor`

Purpose: Track competitor changes that may affect SEO strategy.

System prompt: Distinguish observable changes from assumed causes.

Required inputs:

- Competitor list
- Monitoring cadence
- Signals to track

Execution steps:

1. Compare page, ranking, content, schema, and link changes.
2. Flag material movements.
3. Assign threat/opportunity level.
4. Recommend response.

Output format:

- `templates/competitive-intelligence-brief.md`

Quality gate:

- Do not infer causation without corroboration.

Failure conditions:

- No baseline.

Fallback:

- Establish baseline snapshot.

## `claims-risk-review`

Purpose: Review marketing and SEO claims for legal, trust, and compliance risk.

System prompt: Unsupported claims are SEO trust liabilities.

Required inputs:

- Claims
- Sources
- Industry category

Execution steps:

1. Identify factual, comparative, regulated, or testimonial claims.
2. Check support.
3. Flag risk.
4. Recommend revision or escalation.

Output format:

- `templates/compliance-review.md`

Quality gate:

- High-risk claims require expert/legal review.

Failure conditions:

- No source for claim.

Fallback:

- Remove or soften claim.

## `spam-policy-check`

Purpose: Check SEO tactics against search spam policies.

System prompt: Reject manipulative tactics even if they might produce short-term gains.

Required inputs:

- Proposed tactic
- Page or campaign context

Execution steps:

1. Identify tactic category.
2. Check against anti-patterns and official guidance.
3. Determine risk.
4. Approve, revise, or reject.

Output format:

- `templates/compliance-review.md`

Quality gate:

- Any spam-risk tactic must be rejected or revised.

Failure conditions:

- Tactic unclear.

Fallback:

- Ask for details before approving.

## `landing-page-cro-audit`

Purpose: Evaluate organic landing page conversion readiness.

System prompt: Improve conversion without degrading content accessibility or search intent satisfaction.

Required inputs:

- Landing page
- Organic intent
- Conversion goal
- Analytics if available

Execution steps:

1. Check intent match.
2. Evaluate above-the-fold clarity.
3. Review trust and friction.
4. Recommend tests.

Output format:

- `templates/cro-test-brief.md`

Quality gate:

- CRO changes must not hide or weaken primary content.

Failure conditions:

- Conversion goal undefined.

Fallback:

- Define goal before audit.

## `conversion-intent-map`

Purpose: Map query intent to appropriate conversion actions.

System prompt: Match CTA intensity to user readiness.

Required inputs:

- Query set
- Page set
- Funnel goals

Execution steps:

1. Classify query intent.
2. Match to funnel stage.
3. Assign CTA type.
4. Identify mismatches.

Output format:

- `templates/cro-test-brief.md`

Quality gate:

- CTAs must align with intent.

Failure conditions:

- Funnel goals unknown.

Fallback:

- Use conservative CTA mapping.

## `executive-summary`

Purpose: Convert detailed SEO work into executive-ready narrative.

System prompt: Be concise, decision-oriented, and tied to business outcomes.

Required inputs:

- Findings
- Roadmap
- Risks
- Metrics

Execution steps:

1. Summarize position.
2. Name top opportunities.
3. Name top risks.
4. State decisions needed.

Output format:

- Executive section of `templates/seo-roadmap.md` or `templates/audit-report.md`

Quality gate:

- No jargon without business meaning.

Failure conditions:

- No prioritization.

Fallback:

- Ask strategist for priorities.

## `content-calendar`

Purpose: Sequence content production by opportunity, seasonality, and capacity.

System prompt: Balance opportunity with editorial quality and realistic throughput.

Required inputs:

- Topic opportunities
- Capacity
- Seasonal windows

Execution steps:

1. Prioritize topics.
2. Assign publication windows.
3. Define dependencies.
4. Map refresh and net-new work.

Output format:

- `templates/seo-roadmap.md`

Quality gate:

- Calendar must be achievable.

Failure conditions:

- Capacity unknown.

Fallback:

- Produce phased recommendations.

## `metadata-generation`

Purpose: Generate accurate, intent-aligned metadata for pages or templates.

System prompt: Metadata should summarize the page honestly and improve click clarity.

Required inputs:

- Page content
- Target query
- Brand guidelines

Execution steps:

1. Identify intent and differentiator.
2. Draft title and meta description.
3. Draft Open Graph metadata.
4. Check uniqueness and length.

Output format:

- `templates/metadata-set.md`

Quality gate:

- Metadata must match visible content.

Failure conditions:

- Page content unavailable.

Fallback:

- Ask for page copy or produce provisional metadata.
