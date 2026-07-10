# E-E-A-T Evidence Rubric

**Status:** Primary-source reconciled operational rubric  
**Version:** 2.0.0  
**Last reconciled:** 2026-07-10  
**Primary guideline edition:** Google Search Quality Rater Guidelines, 2025-09-11  
**Primary consumers:** SEO Content Agent, GEO/AIO Agent, and Senior SEO Strategist Agent  
**Canonical source path:** `knowledge/eeat-quality-rubric.md`

## Purpose and boundary

This **kit-defined editorial risk and quality rubric** draws on Google's Search Quality Rater Guidelines and people-first guidance. It is not a Google ranking-factor score, ranking prediction, or substitute for specialist review. Google states that individual rater assessments do not directly move a particular page; use these concepts to judge purpose, helpfulness, and reliability, not to claim Google uses this numeric score.

## Evidence labels

- `OBSERVED`: directly visible on the page, site, source, or verified external record.
- `CORROBORATED`: supported by independent, reliable evidence.
- `INFERRED`: reasoned assessment based on observed evidence; state the basis.
- `UNKNOWN`: evidence was unavailable or not checked.
- `CONTRADICTED`: reliable evidence conflicts with the page or creator claim.

Unknown evidence is not automatically negative. Contradicted or deceptive evidence is.

## Hard gates before scoring

Do not produce an ordinary quality score when a page has a harmful purpose, materially deceptive claims, spam-policy violations, unsafe transactions, impersonation, or unsupported high-risk advice. Return `CRITICAL_FAIL`, identify the evidence, and route to the appropriate owner.

Apply higher evidence and review standards to YMYL topics that could significantly affect health, financial stability, safety, or the welfare or well-being of society.

## Purpose-fit and creator-identification rules

Do not apply a universal byline or credential requirement to every page. Identify who is responsible for the content when that information is important to trust, especially for YMYL, reviews, advice, original research, and professional claims. Official organization pages may establish authority through the organization itself; community content may derive trust from the quality of the discussion and moderation rather than formal credentials.

Reputation research must be topic-specific and independent where possible. Record the search scope, sources checked, date, and whether the result concerns the site, organization, or individual creator. Absence of reputation evidence is `UNKNOWN`, not proof of low quality.

## Operational scoring model

The weights below are an internal prioritization model, not Google weights:

| Dimension | Weight | Core question |
|---|---:|---|
| Experience | 20 | Is relevant first-hand or lived experience demonstrated when the topic benefits from it? |
| Expertise | 25 | Does the creator have the knowledge or skill required for this purpose and risk level? |
| Authoritativeness | 20 | Is the creator or site recognized as a dependable source for this topic? |
| Trustworthiness | 35 | Is the page accurate, honest, safe, transparent, reliable, and fit for its stated purpose? |

Trust is the central gate. Strong-looking experience, expertise, or reputation cannot rescue a materially untrustworthy page.

### Rating each dimension

Rate each dimension from `0` to `4`:

- `4 Strong`: multiple relevant, current, corroborated signals; no material contradiction.
- `3 Adequate`: sufficient evidence for the page purpose; minor gaps remain.
- `2 Limited`: some relevant evidence, but important gaps reduce confidence.
- `1 Weak`: little relevant evidence or material quality concerns.
- `0 Failed`: absent where essential, contradicted, deceptive, unsafe, or materially inaccurate.
- `N/A`: the dimension is genuinely not relevant to the page purpose; explain and renormalize the remaining weights. Trust may not be marked `N/A`.

`weighted_score = sum((dimension_rating / 4) * active_weight)`

Report the numeric result only with an evidence-completeness percentage and confidence level. Do not use false precision beyond a whole number.

## Dimension evidence

### Experience

Relevant signals may include original observations, process detail, first-party tests, original photos or data, use cases, and evidence that the creator actually performed or encountered what is described. First-hand experience is not automatically sufficient for high-risk advice when formal expertise is needed.

### Expertise

Evaluate the expertise appropriate to the purpose. Signals may include demonstrated technical accuracy, relevant credentials, professional history, cited primary evidence, transparent methodology, and appropriate handling of uncertainty. Verify credentials when they materially affect trust.

### Authoritativeness

Evaluate topic-specific recognition, not generic fame. Signals may include citations by reliable sources, professional or institutional recognition, high-quality references, consistent entity information, and being the official source for first-party facts. Lack of a public reputation is not automatically disqualifying for small or new creators.

### Trustworthiness

Check accuracy, honesty, safety, ownership, contact and customer-service information where relevant, transaction security, editorial and commercial disclosures, corrections, sourcing, review authenticity, and alignment between claims and evidence. For commerce, verify policies, price/availability claims, and the identity of the seller. For YMYL, require stronger sourcing and qualified review.

## AI-assisted content rule

Do not penalize content merely because AI tools were used. Evaluate the resulting purpose, originality, accuracy, usefulness, transparency, and risk. Scaled or automated content created primarily to manipulate rankings and offering little user value is a separate spam-policy concern. High-risk AI-assisted content requires accountable human review and source verification.

## Evidence completeness and confidence

Track how many required checks were actually performed:

- `HIGH`: essential on-page, creator, source, and reputation checks were completed with current evidence.
- `MEDIUM`: the page and key sources were checked, but external reputation or credentials are incomplete.
- `LOW`: the assessment relies mainly on the page itself or significant evidence is unavailable.

A high score with low evidence completeness must be reported as provisional.

## Failure and consolidation controls

If creator identity, purpose, source quality, or material claims cannot be verified, return `PARTIAL` or `BLOCKED` for the affected dimension rather than assigning an optimistic score. Reuse claim and author evidence already captured by content, comparison, or compliance workflows; merge by evidence ID instead of duplicating findings. Conflicting evidence remains visible and lowers confidence until resolved.

## Required output

Return:

- Page purpose and YMYL classification with rationale
- Hard-gate result
- Per-dimension rating, evidence, unknowns, and contradictions
- Weighted operational score, evidence completeness, and confidence
- Weakest trust-critical dimension
- Prioritized fixes tied to observable evidence
- Required specialist or compliance review
- Acceptance criteria and verification method

## Primary sources

- Google Search Quality Rater Guidelines: https://guidelines.raterhub.com/searchqualityevaluatorguidelines.pdf
- Google guidance on creating helpful, reliable, people-first content: https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- Google guidance on generative AI content: https://developers.google.com/search/docs/fundamentals/using-gen-ai-content
