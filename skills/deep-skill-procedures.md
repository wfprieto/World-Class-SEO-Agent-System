# Deep Skill Procedures

This file is the execution-entry catalog for indexed skills. It intentionally does not maintain a second copy of detailed thresholds, scoring rules, provider behavior, structured-data requirements, or policy guidance.

For every skill below:

1. Load the named canonical definition before execution.
2. Load the agent capability bundle from `orchestration/capability-registry.json`.
3. Use only observed or supplied evidence and preserve missing, stale, invalid, and blocked states.
4. Follow the canonical skill's decision points, handoffs, approval gates, stop conditions, and fallback.
5. Return evidence, confidence, impact, effort, risk, owner, acceptance criteria, verification, and follow-up.
6. When the canonical source and this entry differ, the canonical source wins and the conflict must be reported.

## full-site-audit
Canonical definition: `skills/core-skills.md`.
Execution boundary: Coordinate the registered specialist graph; missing first-party evidence lowers confidence and must not become a clean result.

## seo-diagnostic-stack-design
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Start with a free baseline; paid tools require a distinct role, estimate, and approval.

## technical-audit
Canonical definition: `skills/core-skills.md`.
Execution boundary: Use direct HTTP, source, rendered, crawl, and code evidence; block high-risk implementation when evidence is incomplete.

## crawl-map
Canonical definition: `skills/core-skills.md`.
Execution boundary: Separate URL states and route taxonomy or discovery defects to the Information Architecture Agent.

## indexation-reality-check
Canonical definition: `skills/core-skills.md`.
Execution boundary: Distinguish technical eligibility from confirmed indexation and require approval before deindexing valuable URLs.

## sitemap-audit
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Validate only preferred canonical indexable URLs and hand generation defects to the Engineer.

## analytics-synthesis
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Separate visibility, traffic, engagement, and conversion; do not infer cause from correlation.

## seo-drift-monitor
Canonical definition: `skills/core-skills.md`.
Execution boundary: Reuse the canonical evidence store and preserve insufficient-history, corruption, and normal-volatility states.

## score-normalization
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Preserve critical caps and evidence coverage; never average a blocker into a harmless total.

## schema-detect-validate-generate
Canonical definition: `skills/core-skills.md`.
Execution boundary: Generate only markup that truthfully describes visible content and current supported use cases.

## core-web-vitals-triage
Canonical definition: `skills/core-skills.md`.
Execution boundary: Prefer field data and use lab evidence for diagnosis; explicitly evaluate LCP, INP, and CLS.

## redirect-validation
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Validate relevance, one-hop behavior, internal references, and rollback before migration approval.

## internal-link-map
Canonical definition: `skills/content-ia-skills.md`.
Execution boundary: Recommend crawlable user-useful links and hand navigation or taxonomy changes to the IA Agent.

## seo-ci-checks
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Fail builds on proven regressions and keep advisory optimization from becoming noisy blockers.

## technical-implementation
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Make the smallest approved change, add regression tests, validate rendered behavior, and retain rollback.

## programmatic-seo-governance
Canonical definition: `skills/programmatic-seo-governance.md`.
Execution boundary: The canonical skill owns sampling, similarity, policy, scoring, rollout, and hard-stop rules; missing data returns `PARTIAL` or `BLOCKED`.

## rendered-visual-audit
Canonical definition: `skills/rendered-visual-audit-and-page-entry.md`.
Execution boundary: No rendered or above-the-fold claim without actual rendered evidence; raw HTML fallback must state skipped checks.

## single-page-audit
Canonical definition: `skills/rendered-visual-audit-and-page-entry.md`.
Execution boundary: Run the evidence-supported baseline and page-type skills, deduplicate findings, and escalate sitewide implications.

## faceted-navigation-governance
Canonical definition: `skills/ecommerce-seo-skills.md`.
Execution boundary: Preserve valuable demand pages while controlling crawl and index expansion; no universal parameter rule replaces evidence.

## content-brief
Canonical definition: `skills/content-ia-skills.md`; executable evidence gates: `scripts/content_brief_evidence.py`.
Execution boundary: Relevance, current observed SERP evidence, selected intent, and distinct information gain must pass before briefing.

## content-audit
Canonical definition: `skills/content-ia-skills.md`.
Execution boundary: Keep, improve, consolidate, redirect, noindex, or retire only with business and performance evidence.

## content-decay
Canonical definition: `skills/content-ia-skills.md`.
Execution boundary: Separate decay from seasonality, tracking, technical change, cannibalization, and SERP change.

## anti-ai-public-writing
Canonical definition: `skills/public-facing-writing-skills.md`.
Execution boundary: Preserve proof, natural language, accessibility, brand voice, and compliance; weaken unsupported claims.

## keyword-cluster
Canonical definition: `skills/content-ia-skills.md`.
Execution boundary: Cluster by shared user need and SERP evidence, not word overlap alone.

## content-inventory
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Build an actionable, owned, refreshable inventory with clearly labeled missing metrics.

## sxo-page-fit
Canonical definition: `skills/content-ia-skills.md`.
Execution boundary: Align query intent, user task, page promise, accessibility, trust, and conversion without forcing premature CTAs.

## metadata-generation
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Do not polish metadata for pages whose purpose, content, or differentiation is unresolved.

## conversion-intent-map
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Map intent to an appropriate next action and measurement plan; missing conversion data remains explicit.

## landing-page-cro-audit
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Revenue-critical page or form changes remain approval-gated and require guardrail metrics.

## competitor-comparison-page-build
Canonical definition: `skills/competitor-comparison-pages.md`.
Execution boundary: The canonical skill owns identity, evidence, claim ledger, methodology, disclosures, length, scoring, schema eligibility, freshness, and publication blocks.

## flow-prompt-run
Canonical definition: `skills/seo-flow-skill.md`; stage references: `skills/flow-prompts/`.
Execution boundary: Select one justified stage, bind claims to sources, and route regulated or commercial claims for review.

## serp-overlap-cluster
Canonical definition: `skills/seo-cluster-skill.md`; executable helper: `scripts/serp_cluster.py`.
Execution boundary: Use supplied observed SERPs, preserve distinct intent, and never fabricate rank, volume, or CPC.

## desktop-commander-execution
Canonical definition: `skills/local-execution-skills.md`.
Execution boundary: Stay inside the approved workspace, enforce operation-specific approvals, redact secrets, and record what each command does not prove.

## consent-mode-diagnostic
Canonical reference: `knowledge/dma-consent-mode-v2.md`; executable helper: `scripts/consent_mode_diagnostic.py`.
Execution boundary: Analyze supplied configuration only, separate observed defects from verification requirements, never grant consent, and always require legal review for legal conclusions.

## local-seo-audit
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Resolve the real business entity, preserve service-area privacy, distinguish public from owner-authorized evidence, and reject fake locations or reviews.

## citation-audit
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Compare identity fields without inflating formatting differences and avoid low-quality directories.

## review-strategy
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Never incentivize, gate, fabricate, or selectively solicit reviews; escalate sensitive responses.

## local-landing-page-brief
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Require real local proof and user value; block doorway or fabricated location pages.

## regional-keyword-map
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Preserve market, language, intent, terminology, localization, and page-eligibility distinctions.

## hreflang-audit
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Validate reciprocal, canonical, indexable, valid-locale targets and separate inventory gaps from clean results.

## international-url-architecture
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Base structure on real operational market differences, localization capacity, risk, and migration verification.

## localized-content-review
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Require market-appropriate terminology, proof, links, schema, CTA, and human review where business-critical.

## image-seo-audit
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Separate accessibility, on-page UX, Search eligibility, Merchant requirements, performance, and provenance.

## video-seo-audit
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Validate visible media context, captions, transcripts, thumbnails, schema, discoverability, and intent.

## accessibility-audit
Canonical definition: `skills/missing-skills.md`.
Execution boundary: Combine automated evidence with manual template checks and never claim full accessibility from a scanner alone.

## geo-grid-rank-scan
Canonical definition: `skills/geo-grid-local-rank-skills.md`.
Execution boundary: The canonical skill owns source tier, entity resolution, geodesic grid generation, privacy, cost, coverage, comparability, and measured rank semantics.

## gbp-profile-audit
Canonical definition: `skills/geo-grid-local-rank-skills.md`.
Execution boundary: The canonical skill owns authorization modes, applicable-field coverage, policy review, scoring eligibility, and the boundary between profile performance and rank.

## competitor-radius-map
Canonical definition: `skills/geo-grid-local-rank-skills.md`.
Execution boundary: Presence is not rank or market share; resolve and deduplicate entities and disclose source coverage.

## cross-platform-nap-verify
Canonical definition: `skills/geo-grid-local-rank-skills.md`.
Execution boundary: Compare against an owner-approved identity, preserve intentional variations and hidden addresses, and assign severity by actual customer or entity impact.

## product-page-seo-audit
Canonical definition: `skills/ecommerce-seo-skills.md`.
Execution boundary: Resolve exact product and variant, separate evidence dimensions, reuse schema and consistency results, and report coverage.

## product-schema-validate-generate
Canonical definition: `skills/ecommerce-seo-skills.md`.
Execution boundary: Select the current supported use case, validate visible parity and required properties, and block fabricated or hidden markup.

## marketplace-intelligence
Canonical definition: `skills/ecommerce-seo-skills.md`.
Execution boundary: Require an approved connected source, exact matching rules, cost approval, coverage, and truthful descriptive statistics.

## marketplace-keyword-gap
Canonical definition: `skills/ecommerce-seo-skills.md`.
Execution boundary: Align market, date, device, query, source semantics, and landing-page identity; missing channels remain unavailable.

## merchant-data-consistency-audit
Canonical definition: `skills/ecommerce-seo-skills.md`.
Execution boundary: Reconcile the exact item and variant across page, schema, feed, and approved checkout evidence without silently choosing a source.

## agentic-commerce-readiness-check
Canonical definition: `skills/ecommerce-seo-skills.md`.
Execution boundary: Separate verified foundations from speculative capability readiness and re-check current standards before recommendation.

## geo-aio-citation-audit
Canonical definition: `skills/specialist-skills.md`; scoring reference: `knowledge/geo-readiness-rubric.md`.
Execution boundary: Use dated repeated observations, normal Search eligibility, entity clarity, source quality, originality, and volatility labels.

## brand-serp-audit
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Record market, query, device, date, owned/editable/third-party sources, and reputation escalation.

## knowledge-graph-sync
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Reconcile entities to durable sources and never invent relationships, credentials, or profile control.

## conversational-query-map
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Use real question evidence, map intent and answer type, and avoid thin FAQ production.

## official-source-monitor
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Separate official changes, first-party observations, experiments, hypotheses, and watch items.

## knowledge-sync
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Version accepted rule changes, name affected agents, define validation, and schedule re-review.

## backlink-profile
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Reconcile tool coverage, separate noise from material risk, and keep disavow approval-gated.

## backlink-gap
Canonical definition: `skills/specialist-skills.md`.
Execution boundary: Select true organic competitors and reject manipulative, irrelevant, paid, or private-network opportunities.

## digital-pr-asset-brief
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Require newsworthy or useful value, rights, methodology, proof, compliance, and a real audience.

## outreach-prospecting
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Verify topical fit and contact path; do not send, spam, buy links, or use unverified contact data.

## negative-seo-threat-review
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Preserve evidence, compare baselines, escalate hacked content, and avoid reflexive disavow recommendations.

## security-indexation-check
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Treat malware or injected indexation as critical, fix root cause first, and coordinate with security owners.

## compliance-review
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Identify jurisdiction and claim risk, distinguish technical review from legal advice, and require qualified approval where needed.

## spam-policy-check
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Use current primary policies, label uncertainty, and let policy risk override short-term traffic opportunity.

## claims-risk-review
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Bind each material claim to proof, qualify or remove unsupported language, and route regulated claims.

## competitive-gap
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Use observed SERP overlap and business fit; reject copycat work outside the site's model or capability.

## competitor-change-monitor
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Preserve comparable snapshots and trigger action only for material changes affecting priority scope.

## forecasting
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Use scenarios, assumptions, ranges, seasonality, conversion data, and explicit uncertainty; avoid false precision.

## trend-monitor
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Confirm durable relevant demand across evidence sources and track outcomes rather than reacting to noise.

## seo-roadmap
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Accept only governed findings, reflect capacity and dependencies, assign owners, and sequence measurement before speculation.

## executive-summary
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Separate facts, changes, expected benefits, risks, missing evidence, and the single next action.

## plain-language-seo-report
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Translate validated outputs without hiding missing access, incomplete work, unverified outcomes, or risk.

## content-calendar
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Balance useful new work, refreshes, dependencies, proof, compliance, capacity, and measurement dates.

## request-routing
Canonical definition: `skills/strategy-governance-skills.md`; executable router: `runtime/routing.py`.
Execution boundary: Select the deliverable owner, necessary specialists, evidence plan, risk gates, and routing confidence.

## prioritization-matrix
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Normalize impact, confidence, effort, risk, reversibility, dependencies, and time-to-value without hiding blockers.

## scrummaster-debate
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Require evidence, dissent, failure modes, rollback, and a schema-valid decision before contested work proceeds.

## experiment-design
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Predefine hypothesis, design, metrics, guardrails, sample, confounders, analysis window, and decision rule.

## decision-record
Canonical definition: `skills/strategy-governance-skills.md`; schema: `schemas/decision-record.schema.json`.
Execution boundary: Record evidence, counterarguments, risk, owner, conditions, verification, and rollback for material decisions.

## definition-of-done
Canonical definition: `skills/strategy-governance-skills.md`.
Execution boundary: Distinguish built, launched, verified, and outcome-validated states; missing proof returns blocked or conditional completion.
