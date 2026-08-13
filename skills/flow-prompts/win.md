# FLOW Prompts - Win

## Use When

Use when visibility exists but qualified action, revenue contribution, lead quality, or stakeholder
clarity is weak. The Win stage connects SEO work to business outcomes without pretending that
traffic alone is success.

## Owner Agents

- SEO CRO Agent
- Senior SEO Strategist Agent
- SEO Output Report Agent
- SEO Compliance & Legal Agent
- SEO Copywriter/Content Agent

## Required Inputs

- Target page, offer, audience, and buying stage.
- Conversion goal and measurement event.
- Objections, proof, reviews, sales notes, analytics, funnel data, or call-to-action evidence.
- Compliance constraints for pricing, guarantees, regulated claims, testimonials, and disclosures.

## Stop Conditions

- No conversion goal exists.
- The requested page requires proof that is not supplied.
- The page is in a regulated category and compliance review is unavailable.

## Decision Tree

1. If the page is bottom-funnel or sales-assisted, run `bofu-page-brief`.
2. If the page gets traffic but weak action, run `conversion-audit`.
3. If the team needs one plain score, run `dual-surface-scorecard`.
4. If outcomes cannot be measured immediately, mark leading indicators and verification horizon.
5. If compliance-sensitive claims appear, route to SEO Compliance & Legal Agent first.

## Prompt Blocks

## Prompt: BOFU Page Brief

```text
Create a bottom-funnel page brief for [offer] targeting [audience] at [buying stage].

Use only supplied evidence: objections, customer language, proof points, product facts, case
studies, reviews, pricing, policies, demos, or sales notes.

Return:
1. Page promise in plain language.
2. Buyer decision risk.
3. Objections in the buyer's words.
4. Proof needed for each objection.
5. Page structure.
6. CTA and secondary action.
7. Trust signals and disclosures.
8. Claims needing legal or compliance review.
9. Measurement event and success threshold.

Rules:
- Do not invent proof.
- Do not imply guaranteed outcomes.
- Do not hide pricing, limitations, or eligibility when those matter to the decision.
```

## Prompt: Conversion Audit

```text
Audit [URL] as a conversion page.

Check:
- above-the-fold clarity
- offer specificity
- CTA and intent match
- proof placement
- objection handling
- trust signals
- friction and form burden
- accessibility of conversion controls
- mobile clarity
- analytics event coverage

Return:
1. Conversion blockers by severity.
2. The decision each blocker prevents.
3. Recommended changes.
4. Hypothesis, not promised lift.
5. Verification method.
6. Immediate and delayed measurement horizons.

Rule:
- Do not claim a conversion-rate increase as fact until measured.
```

## Prompt: Dual-Surface Scorecard

```text
Score [URL] across two surfaces.

Search surface:
- intent match
- crawl/render availability
- extraction readiness
- entity clarity
- internal linking
- schema eligibility

Business surface:
- offer clarity
- proof strength
- objection handling
- CTA fit
- trust/disclosure
- measurement readiness

Return:
1. Score per dimension: 0-5.
2. Weakest dimension.
3. One change most likely to improve qualified action.
4. Evidence gaps.
5. Next owner.
```

## Prompt: Stakeholder Win Summary

```text
Turn the Win-stage findings into a plain-language summary for a non-technical stakeholder.

Return:
- what was reviewed
- what is blocking business impact
- what should change first
- why it matters
- what will be measured
- what cannot be promised yet

Rules:
- No jargon.
- No unexplained SEO acronyms.
- No unsupported impact claims.
```

## Output Contract

Return:

- Minimum JSON keys: `"stage"`, `"business_outcome"`, `"win_plan"`,
  `"conversion_blockers"`, `"recommended_changes"`, `"claims_for_compliance_review"`,
  `"measurement_plan"`, `"verification_horizon"`, `"plain_language_summary"`.
- `"stage": "win"`
- `business_outcome`
- `win_plan`
- `conversion_blockers`
- `recommended_changes`
- `claims_for_compliance_review`
- `measurement_plan`
- `verification_horizon`
- `plain_language_summary`
