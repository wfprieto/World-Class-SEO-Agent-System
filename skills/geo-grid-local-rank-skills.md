# Geo-Grid Local Rank and Maps Skills

**Status:** Controlled integration baseline  
**Version:** 2.0.0  
**Last reconciled:** 2026-07-10  
**Primary owner:** Local SEO Agent  
**Canonical source path:** `skills/geo-grid-local-rank-skills.md`

Follow the host repository's skill-definition standard and register these skills under `Local, International, and Media Skills`.

## Shared execution rules

- Evidence states: `OBSERVED`, `OWNER_AUTHORIZED`, `PROVIDER_REPORTED`, `USER_SUPPLIED`, `INFERRED`, and `UNKNOWN`. Do not convert missing, inferred, or stale data into an observed fact.
- Execution states: `COMPLETE`, `PARTIAL`, `SKIPPED`, `BLOCKED`, and `FAILED`. Report source coverage separately from any score or rank metric.
- Resolve the exact business entity before analysis. Prefer durable platform IDs over name-only matching.
- Metered calls require a documented estimate, approval, hard ceiling, and actual-cost report.
- Protect hidden service-area addresses, private coordinates, access tokens, account data, and personal information.
- Current Google Business Profile, Google Maps Platform, approved provider, and open-data source policies override this file. Preserve attribution, usage, and retention restrictions.
- Every recommendation must state evidence, confidence, owner, acceptance criteria, and verification method.

These skills measure and audit maps-platform evidence for a resolved business entity. They do not replace website local SEO, structured-data validation, or Business Profile ownership workflows.

A successful execution must resolve the exact business entity, remain reproducible, link every material claim to evidence, protect hidden addresses and exact private coordinates, use least-privilege access, obtain cost approval when metered, and state what the active data tier cannot observe.

Tiering is capability-based and each result declares the tier actually used:

- `L0_OPEN_BASELINE`: user-approved identity, website, manual public observations, and policy-compliant open data. It cannot measure maps rank or private Business Profile fields.
- `L1_PUBLIC_MAPS_CONNECTED`: an approved public place/maps or maps-SERP source. It can measure third-party rank observations and public place fields, subject to source terms and cost approval.
- `L2_OWNER_AUTHORIZED_GBP`: OAuth-authorized data for profiles the user owns or is authorized to manage. It can inspect managed fields and Business Profile performance, but performance impressions are not rank positions.

Always state the active tier, source, capture time, market, language, device, query parameters, attribution/retention constraints, and unavailable capabilities. A prior run is historical evidence, and connector presence alone does not upgrade the tier.

---

## `geo-grid-rank-scan`

Purpose: Measure how a business ranks in maps results across a grid of GPS points and express it as Share of Local Voice.

System prompt: Act as a local rank-tracking specialist. This requires a connected metered maps-SERP source. If none is connected, say so and stop; do not estimate ranks.

Required inputs:

- Resolved business identity and an owner-approved measurement center or public place coordinate
- Keyword(s) to scan
- Proposed odd grid size, radius, orientation, `top_k`, and maximum result depth
- An approved L1 maps/local-result source and exact cost approval

Execution steps:

1. Confirm an approved L1 source, its result semantics, terms, and the target entity. If unavailable, return `BLOCKED_SOURCE`; do not estimate rank.
2. Resolve the target by platform ID where possible. Select a public storefront coordinate or an owner-approved privacy-safe center. Never reveal a hidden service-area address.
3. Require an odd grid size. Generate each point with a tested geodesic direct calculation using distance and bearing from the center. Record the Earth model/library, orientation, point IDs, precision, radius, and center-source label.
4. Show provider, planned calls (`grid_points x keywords`, plus any lookup calls), billable fields, unit cost, retry allowance, estimated total, currency, and hard ceiling. Obtain explicit approval for that exact configuration before firing.
5. Query once per point and keyword with fixed market, language, device, search surface, and maximum result depth. Match the target by platform ID where possible. Classify each point as `OBSERVED`, `NOT_FOUND`, `FAILED`, or `SKIPPED`.
6. Compute kit-defined SoLV using the declared `top_k` and valid-result denominator. Report coverage separately. Compute found rate, mean observed rank, and mean capped rank where `NOT_FOUND = max_depth + 1`; never treat request failure as unranked.
7. Render a heatmap whose legend distinguishes found ranks, not found, failed, skipped, and center. Identify weak areas only when enough valid points exist; otherwise return `INSUFFICIENT_COVERAGE`.

Comparison rule:

- Compare against a prior scan only when the configuration fingerprint matches. Otherwise label the run `NEW_BASELINE` or `NON_COMPARABLE`; do not report an improvement or decline.

Output format:

- Query configuration and identity-match method.
- Point-level observation table or artifact reference, heatmap, valid coverage, SoLV with declared `top_k`, found rate, mean observed rank, mean capped rank, spatial summary, and per-keyword results.
- Estimated and actual cost. Any qualitative SoLV band is kit-defined and must not be presented as a Google benchmark.

Grid size and radius are scope decisions, not universal best practices. Show the call count and spatial resolution tradeoff before approval.

Scoring and completion:

- Geo-grid metrics are reported as measurements, not an overall local SEO score. `COMPLETE` requires at least 95% valid point coverage for the approved scan; otherwise return `PARTIAL`.

Quality gate:

- No rank data without an approved live source. Cost approved before firing. Grid geometry is geodesic and reproducible. The report states how the center was selected and does not call a service-area centroid the business's “true location.”

Failure conditions:

- No approved L1 source, entity unresolved, center selection unsafe, geodesic generation fails, insufficient valid coverage, rate/quota limit, policy restriction, cost ceiling, or provider semantics cannot be verified. Return a specific blocker or failure code; do not emit zero ranks.

Fallback:

- Offer `competitor-radius-map` at Tier 0 (presence, not rank) and recommend connecting a metered source for rank.

---

## `gbp-profile-audit`

Purpose: Audit the resolved Google Business Profile for accuracy, eligibility, applicable-field completeness, policy risk, and measurement readiness without inventing ranking weights.

System prompt: Act as an authorized-profile auditor. Use owner-account data only for locations the user owns or is authorized to manage. A public profile observation is not a substitute for managed fields. Never claim that a checklist score predicts rank.

Required inputs:

- Resolved business identity and location model
- Requested mode: `OWNER_AUTHORIZED`, `PUBLIC_SUBSET`, or `MANUAL_CHECKLIST`
- L2 OAuth-approved Business Profile source for owner-authorized mode
- Current Google Business Profile policy references

Execution steps:

1. Confirm the entity, authorization, tier, mode, and profile/location ID. Business Profile APIs may be used only for listings the user owns or is authorized to manage.
2. Evaluate eligibility and identity: real-world name, location model, duplicate/department/practitioner rules, verification or status evidence where authorized.
3. Evaluate category and service relevance using current allowed categories. Do not create categories, add every service as a category, or insert keywords into the business name.
4. Evaluate public address, service area, regular and special hours, phone, website, links, attributes, services/products, media, and other fields only when applicable and observable. A service-area business that does not serve customers at its address must not be told to display that address.
5. Review reputation operations: genuine-review request process, response ownership, policy violations, and fake/incentivized/selective-review risks. Do not recommend incentives, review gating, staff quotas, or competitor reviews.
6. When authorized, summarize Business Profile performance metrics and search-keyword impressions with date ranges. Do not translate impressions into ranking positions.
7. Score applicable dimensions under the contract. Unknown managed fields remain unknown. Return null score below the coverage gate or when a public subset would imply full-profile completeness.

Output format:

- Audit mode, tier, profile identity, evidence coverage, applicable-dimension table, score when eligible, owner/policy risks, performance observations, prioritized fixes, acceptance criteria, and fields requiring owner verification.

Quality gate:

- No profile access without authorization. No invented field values or ranking weights. No name stuffing, fake categories, fake reviews, incentives, selective review solicitation, hidden-address exposure, or claim that payment improves organic local rank.

Failure conditions:

- Entity unresolved, authorization absent for owner mode, profile inaccessible, source stale/corrupt, or evidence coverage below the requested decision threshold.

Fallback:

- Downgrade to `PUBLIC_SUBSET` or `MANUAL_CHECKLIST`, mark managed fields unknown, and do not issue a completeness score.

---

## `competitor-radius-map`

Purpose: Identify candidate local competitors and describe market density without presenting incomplete place coverage as a definitive market census.

System prompt: Act as a local entity-resolution analyst. Separate open-data presence, public place discovery, and rank observations. A nearby same-category listing is a candidate until customer-need and entity evidence support competitor classification.

Required inputs:

- Resolved target identity and privacy-safe center
- Search category/keyword, customer need, radius or boundary, country, and language
- Approved source tier and cost approval when metered

Execution steps:

1. Define direct, adjacent, out-of-scope, and unresolved competitor criteria before retrieval.
2. At L0, query policy-compliant open data and preserve source tags, timestamps, attribution, and coverage limitations. Open-map presence is not rank or complete market coverage.
3. At L1, use an approved public place or maps-result source with required field masks, attribution, retention rules, locale, and cost controls. Keep organic/maps rank observations separate from place discovery.
4. Resolve and deduplicate location entities by platform ID where available, then website/domain, phone, normalized address, coordinates, and name. Keep chains, departments, practitioners, and co-located businesses distinct unless evidence supports a merge.
5. Classify each entity with rationale. Do not infer malicious intent, market share, or competitive strength solely from rating, review count, or source-result order.
6. Compute density only for unique in-scope entities and disclose the area formula, taxonomy, source coverage, and exclusions.

Output format:

- Scope definition, tier, source/attribution notes, candidate and classified entity table, duplicate-resolution record, density when valid, coverage limitations, and actions for manual verification.

Quality gate:

- Presence is not rank. Missing open data is not nonexistence. Ratings and reviews require live evidence. Data use, display, retention, and attribution must comply with the connected source.

Failure conditions:

- Center unresolved, source unavailable, taxonomy cannot map to the requested scope, entity duplication unresolved, rate/cost limit reached, or source terms prohibit the intended use.

Fallback:

- Narrow the scope, use a manual candidate list, or return an open-data baseline with no density or ranking conclusion. State exactly what changed.

---

## `cross-platform-nap-verify`

Purpose: Verify cross-platform business identity and customer-routing fields against an owner-approved canonical record while preserving legitimate platform and service-area differences.

System prompt: Act as an identity-consistency specialist. Normalize before comparing. Exact formatting is not the goal; correct entity identity and safe customer routing are. Do not present NAP consistency as a guaranteed local-ranking lever.

Required inputs:

- Owner-approved canonical identity record
- Resolved platform IDs or candidate listing URLs
- Platforms and fields in scope
- Known intentional variations, call-tracking rules, departments, practitioners, and service-area privacy requirements

Execution steps:

1. Resolve the same business entity on each approved platform. If identity is uncertain, stop at `UNRESOLVED`; do not compare a likely namesake.
2. Retrieve only permitted public or owner-authorized fields and record source, capture time, listing ID, locale, and authorization mode.
3. Normalize names, phone country codes, punctuation, abbreviations, suite/unit formatting, URLs, and address components without erasing meaningful differences.
4. Classify each field as `EXACT`, `NORMALIZED_EQUIVALENT`, `INTENTIONAL_VARIATION`, `SUSPECTED_CONFLICT`, `MISSING`, `NOT_OBSERVED`, or `NOT_APPLICABLE`.
5. Assign impact-based severity. Hidden service-area addresses are `NOT_APPLICABLE`; their absence is not an error. A call-tracking number may be an intentional variation if it routes correctly and the canonical number remains governed.
6. Produce an owner-approved remediation plan. Never claim, edit, merge, or close a listing automatically.

Output format:

- Platform identity matrix, normalized field comparison, evidence-linked status and severity, intentional-variation register, unresolved entities, and remediation plan with owner and verification method.

Quality gate:

- Canonical identity is owner-approved. Formatting differences are not inflated into conflicts. Hidden addresses remain protected. Missing listing versus missing field versus inaccessible source remain distinct.

Failure conditions:

- Canonical identity absent, target entity unresolved, platform inaccessible, source terms prohibit collection, or required owner verification is unavailable.

Fallback:

- Return a manual verification worksheet with direct platform references and mark all unobserved fields unknown.

---

## LocalBusiness structured-data boundary

Delegate all structured-data decisions to `schema-detect-validate-generate` and the current schema registry. Mark up only visible website content and never expose a hidden service-area address or copy unverified maps fields into JSON-LD. LocalBusiness markup is not a Google Maps ranking control. Self-serving `LocalBusiness` or `Organization` review markup is not eligible for Google review snippets; do not promise stars.

## Primary policy anchors

Use current Google-owned Business Profile, Maps Platform, Search structured-data, and review-policy documentation plus the official Nominatim usage policy. Reverify time-sensitive requirements before client delivery.
