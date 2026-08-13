# FLOW Prompts - Local

## Use When

Use when the work affects Google Business Profile, local landing pages, map visibility, reviews,
service areas, local citations, or location-specific conversion paths. The Local stage applies
the FLOW loop to local search and map behavior.

## Owner Agents

- Local SEO Agent
- SEO Diagnostic Infrastructure Agent
- SEO Copywriter/Content Agent
- SEO Knowledge Graph Sync Agent
- SEO Compliance & Legal Agent

## Required Inputs

- Business type: brick-and-mortar, service-area business, hybrid, ecommerce local pickup, or
  multi-location.
- Verified NAP, service list, service area, locations, hours, categories, website URLs, and review
  evidence.
- Market/city/region and target services.
- Budget and tool access if local rank tracking, citation tools, or GBP API work is requested.

## Stop Conditions

- User asks for fake locations, fake reviews, keyword-stuffed business names, virtual offices that
  violate platform rules, or review gating.
- NAP cannot be confirmed.
- Regulated service claims need review and no compliance path exists.

## Decision Tree

1. If business type or service area is unclear, run `local-profile-discovery`.
2. If Business Profile setup is requested, run `gbp-category-and-service-map`.
3. If local pages need writing, run `local-page-brief-or-rewrite`.
4. If title/meta is requested, run `local-title-meta`.
5. If map visibility is weak, run `local-competitive-brief`.
6. If reviews or claims are involved, route to compliance before publication.

## Prompt Blocks

## Prompt: Local Profile Discovery

```text
Classify [business] for local SEO execution.

Return:
1. Business type: brick-and-mortar, service-area, hybrid, multi-location, practitioner, or unknown.
2. Verified NAP fields.
3. Service area logic.
4. Primary services.
5. Market and local intent.
6. Missing setup data.
7. Compliance or platform-policy risks.

Rule:
- Do not proceed to GBP, citation, or local page recommendations if NAP is unverified.
```

## Prompt: GBP Category And Service Map

```text
For [business type] in [city/market], recommend Business Profile category and service structure.

Use only supplied service evidence.

Return:
1. Primary category candidate.
2. Secondary category candidates.
3. Services to list.
4. Services to omit because they are not genuinely offered.
5. Description guidance.
6. Verification needed before update.

Rules:
- No keyword stuffing.
- No categories or services the business cannot fulfill.
- Flag regulated claims.
```

## Prompt: Local Page Brief Or Rewrite

```text
Create or rewrite a local page for [service] in [city/area].

Required structure:
- what the business does
- who it serves
- service area
- local proof
- reviews or credentials if supplied
- FAQs based on local buyer questions
- clear next action
- NAP consistency note
- schema candidates

Rules:
- Do not create doorway pages.
- Every location page needs unique local proof or service relevance.
- Do not fabricate local testimonials, staff, offices, awards, or service areas.
```

## Prompt: Local Title And Meta

```text
For [local page] targeting [service] and [city/area], write:
- title tag under about 60 characters
- meta description under about 155 characters

Rules:
- Include service and location naturally.
- Match the actual page.
- No fake superlatives.
- No keyword stuffing.
- No guaranteed outcomes.
```

## Prompt: Local Competitive Brief

```text
Build a local competitive brief for [business] in [market].

Use supplied evidence from map results, GBP profiles, reviews, local pages, citations, or rank
tracking.

Return:
1. Competitors visible in map/local results.
2. Category patterns.
3. Review quantity, quality, and recency patterns.
4. Local page strengths.
5. Citation or entity consistency gaps.
6. Highest-leverage local action.
7. Measurement plan: local rank, calls, direction requests, bookings, or qualified leads.

Rules:
- Label inferred competitor advantages.
- Do not treat a single geo-grid point as a complete market view.
```

## Output Contract

Return:

- Minimum JSON keys: `"stage"`, `"business_type"`, `"local_surface"`,
  `"verified_nap_status"`, `"local_action_plan"`, `"recommended_actions"`,
  `"policy_risks"`, `"evidence_register"`, `"measurement_plan"`.
- `"stage": "local"`
- `business_type`
- `local_surface`: GBP, map pack, local page, citations, reviews, or service area
- `verified_nap_status`
- `local_action_plan`
- `recommended_actions`
- `policy_risks`
- `evidence_register`
- `measurement_plan`
