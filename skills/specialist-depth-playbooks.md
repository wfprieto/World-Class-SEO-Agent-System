# Specialist Depth Playbooks

These playbooks add domain-specific synthesis and precedence rules to canonical skills. Every specialist also follows `skills/specialist-decision-standard.md`.

Each section is versioned and digest-bound by `governance/specialist-playbook-integrity.json`.
Passing that integrity gate proves the reviewed section was loaded unchanged, not that a model
understood or followed it.

## Agent: `Negative SEO & Security Agent`

### Decision branches

- Compromise indicators, injected pages, malware warnings, or unauthorized templates: preserve evidence, mark `ESCALATE`, and route root-cause containment to security/engineering before search cleanup.
- Backlink anomaly without manual action, traffic/indexation impact, or corroborating pattern: `PARTIAL`; establish a dated baseline and monitor.
- Manual action or verified link scheme connected to the site: prepare human-reviewed remediation evidence; never submit a disavow automatically.

### Evidence sufficiency

`READY` requires a resolved incident scope, dated baseline, at least one primary control surface or reproducible index/crawl observation, and separation of backlink, compromise, and ordinary volatility hypotheses.

### Failure, abstention, and escalation

`BLOCKED` when the target, baseline, or alleged signal is unavailable. `ABSTAIN` from attacker identity or causation. Escalate credible compromise, malware, unsafe URLs, manual actions, or exposure of sensitive data immediately.

### Edge cases and examples

Distinguish scraper copies from compromise, spam links from demonstrated harm, historical URLs from current injection, and reporting-tool noise from index evidence. Good: contain an evidenced injected-template incident first. Bad: blame a competitor or disavow solely from a vendor toxicity score.

## Agent: `SEO Accessibility Agent`

### Decision branches

- Automated rule violation with reproducible DOM evidence: report the bounded rule failure and request manual confirmation where user interaction matters.
- Keyboard, focus, reading order, name/role/value, captions, or contrast requiring human/tool verification: `PARTIAL` until the required check is performed.
- Static markup only: report markup observations; never claim rendered behavior or WCAG conformance.

### Evidence sufficiency

`READY` for a finding requires target/template coverage, method and viewport, evidence ID, affected user impact, reproducible steps, and applicable success criterion. Full-conformance claims are outside agent authority.

### Failure, abstention, and escalation

`BLOCKED` when the experience cannot be rendered or tested safely. `ABSTAIN` from legal compliance and full-site conformance conclusions. Escalate blockers affecting primary navigation, authentication, purchase, forms, safety information, or broad shared components.

### Edge cases and examples

Treat decorative images, hidden labels, custom controls, modal focus, zoom/reflow, motion preferences, transcripts, and localized accessible names separately. Good: report an unlabeled checkout control with DOM and keyboard evidence. Bad: declare a site accessible because an automated scanner returned zero errors.

## Agent: `International & Multilingual SEO Agent`

### Decision branches

- Reciprocal hreflang set with indexable, canonical-aligned targets: validate locale coverage and return-tag integrity.
- Canonical points outside its hreflang locale cluster, invalid locale code, redirect, noindex, or missing reciprocal: report the precise conflict; do not prescribe a bulk rewrite before inventory coverage is known.
- Localization quality or market intent cannot be verified: `PARTIAL` and route business-critical pages to a qualified market reviewer.

### Evidence sufficiency

`READY` requires a market-locale inventory, exact URL identities, canonicals, indexability/status, hreflang sources, sitemap relationships where used, and the intended market/language model.

### Failure, abstention, and escalation

`BLOCKED` when market requirements or URL inventory are unknown. `ABSTAIN` from translation quality without market expertise. Escalate sitewide URL migrations, geo-routing, forced redirects, canonical changes, or bulk hreflang deployment.

### Edge cases and examples

Handle same-language regional pages, untranslated fallbacks, x-default, parameterized locales, mobile alternates, cross-domain ownership, regional search engines, and partially launched markets explicitly. Good: isolate a canonical/hreflang contradiction to affected clusters. Bad: assume subfolders are always correct or reuse one market's demand globally.

## Agent: `Local SEO Agent`

### Decision branches

- Owner-approved identity plus resolved listing/entity: compare normalized fields and preserve intentional variations.
- Public-subset evidence only: report observed public fields and unknown managed fields; do not issue a complete-profile score.
- Service-area business: protect hidden addresses and treat absent public address as `NOT_APPLICABLE`, not an inconsistency.

### Evidence sufficiency

`READY` requires resolved business identity, authorization/source tier, location or service-area scope, capture time, platform IDs or URLs, and coverage adequate for the requested decision.

### Failure, abstention, and escalation

`BLOCKED` for unresolved identity, missing owner source of truth, or prohibited collection. `ABSTAIN` from rank-cause and market-share claims. Escalate listing merges, ownership disputes, suspensions, hidden-address exposure, regulated review responses, and bulk profile edits.

### Edge cases and examples

Distinguish departments, practitioners, co-located businesses, tracking numbers, relocations, seasonal hours, duplicates, and franchises. Good: preserve a verified tracking-number variation. Bad: expose a service-area address, create fake locations, or treat formatting differences as critical conflicts.

## Agent: `Competitive Intelligence Agent`

### Decision branches

- Comparable dated snapshots show a material change in priority scope: describe the observation, business relevance, and verification action.
- Ranking/content/link movement lacks controlled evidence: label cause as a hypothesis and avoid reactive copying.
- Competitor selection lacks SERP overlap or business-model fit: re-resolve the comparison set before gap scoring.

### Evidence sufficiency

`READY` requires observed competitors, aligned market/query/device/date/source semantics, comparable snapshots, and a materiality threshold tied to business scope.

### Failure, abstention, and escalation

`BLOCKED` without a baseline or comparable source coverage. `ABSTAIN` from causal attribution and competitor intent. Escalate trademark, reputation, confidential-data, scraping-policy, or manipulative-outreach risks.

### Edge cases and examples

Account for personalization, localization, SERP churn, migrations, seasonality, syndicated content, brand/non-brand mix, and provider coverage changes. Good: validate a persistent new competitor page type across comparable snapshots. Bad: copy content or attribute one ranking change to a guessed tactic.

## Agent: `Predictive SEO Trend Agent`

### Decision branches

- Recurring historical seasonality with sufficient lead time: produce ranges, assumptions, publication dependencies, and review dates.
- Multi-source emerging demand aligned with business expertise: create a bounded experiment or watch item based on uncertainty.
- One-source spike, news shock, or weak business fit: watchlist only; do not trigger scaled production.

### Evidence sufficiency

`READY` requires a dated historical window, seasonality treatment, anomaly handling, at least two independent signal classes for emerging trends, business timing/capacity, and forecast uncertainty.

### Failure, abstention, and escalation

`BLOCKED` when history, timing, or capacity is unknown. `ABSTAIN` from point forecasts and durability claims unsupported by evidence. Escalate regulated, crisis-sensitive, reputational, or high-cost speculative production.

### Edge cases and examples

Separate durable demand from viral noise, reporting-definition changes, algorithm volatility, pandemic/outlier periods, zero-volume emerging terms, and cannibalizing topics. Good: publish a scenario range with stop conditions. Bad: present a social spike as guaranteed search demand.

## Agent: `Visual & Video Search Agent`

### Decision branches

- Rendered asset, metadata, visible context, and delivery evidence available: evaluate discovery, accessibility, performance, and schema as separate dimensions.
- Screenshot only: limit conclusions to visible observations and mark DOM, transcript, schema, and delivery checks unavailable.
- Transcript, captions, thumbnail, timestamps, or asset identity cannot be verified: `PARTIAL`; do not generate supposedly accurate replacements from inference.

### Evidence sufficiency

`READY` requires a resolved media inventory, rendered placement, source asset/metadata, viewport or player context, and dimension-specific evidence. Search eligibility is not indexing or ranking proof.

### Failure, abstention, and escalation

`BLOCKED` when assets are inaccessible or rights/identity cannot be established. `ABSTAIN` from accessibility, provenance, performance, and ranking conclusions outside captured evidence. Escalate rights, sensitive imagery, deceptive media, missing critical captions, or destructive asset replacement.

### Edge cases and examples

Handle decorative versus informative images, CSS backgrounds, lazy loading, responsive variants, animated media, embedded third-party players, transcript parity, live streams, and duplicate thumbnails. Good: separate missing captions from video-index eligibility. Bad: keyword-stuff alt text or fabricate transcript timestamps.

## Agent: `SEO Compliance & Legal Agent`

### Decision branches

- Material claim has directly applicable, current proof: bind the evidence and state remaining jurisdiction/editorial review.
- Proof is absent, indirect, stale, or mismatched: qualify/remove the claim or mark `BLOCKED`; never approve through inference.
- Regulated, privacy, consent, testimonial, comparative, trademark, or spam-policy risk: apply the relevant technical policy check and escalate final approval to the qualified owner.

### Evidence sufficiency

`READY` for technical risk classification requires exact claim/tactic, source and date, jurisdiction/market, commercial relationship, page context, and current primary policy. This agent never makes final legal determinations.

### Failure, abstention, and escalation

`BLOCKED` when jurisdiction, source, relationship, or current policy is unknown. `ABSTAIN` from legal advice or compliance certification. Escalate regulated claims, privacy/consent uncertainty, threatened disputes, testimonial substantiation, trademark use, and any proposed spam tactic.

### Edge cases and examples

Treat implied claims, footnotes, localized claims, affiliate relationships, user-generated content, AI-generated assertions, outdated endorsements, and technically valid but legally uncertain consent states explicitly. Good: remove or qualify an unsupported comparative claim and request counsel. Bad: state that technical Consent Mode configuration proves legal compliance.
