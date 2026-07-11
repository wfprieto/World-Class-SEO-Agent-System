# Content and Information Architecture Skills

## `content-brief`

Before any keyword or outline work, `content-brief` must pass two evidence gates. Both are kit governance heuristics. Neither is a Google ranking factor and neither is a Google score.

### Gate 1: website relevance

Decide whether this site should publish this page at all. Assess the topic against the site's real business or editorial purpose, intended audience, products/services/expertise or publishing remit, existing topical architecture, conversion or user-value path, geographic and market scope, brand/entity relevance, and the ability to produce genuine first-hand or expert content.

Return exactly one verdict: `RELEVANT`, `CONDITIONALLY_RELEVANT`, `NOT_RELEVANT`, or `INSUFFICIENT_EVIDENCE`.

Search volume is never a reason to publish. A high-volume topic the site cannot credibly cover returns `NOT_RELEVANT`. This gate is not a Google ranking factor; it is a kit governance gate that protects topical credibility and user trust.

### Gate 2: SERP competitor evidence

Assess the *observed* competing page set for the query and market, using only supplied search results.

- Identify the actual competing pages; distinguish domain competitors from SERP-only competitors.
- Record query, locale, device, date, source, and result position for every capture.
- Compare page type, intent fit, topical focus, demonstrated experience, source quality, freshness, entity coverage, information gain, UX, and conversion fit.
- Disclose missing or inaccessible evidence rather than filling the gap.
- Never fabricate traffic, backlinks, authority, volume, CPC, or performance data.
- Separate direct observation from inference.
- Comparison weights are configurable kit heuristics, clearly labelled. The resulting score is not a Google score and not a probability of ranking.

If no results are supplied, return `INSUFFICIENT_EVIDENCE`. Do not invent a competitor set.

### Brief decision

A brief proceeds only when relevance passes **and** a distinct information gain is stated. No information gain means no brief. The finished brief must contain:

- **Why this site should publish this page** - the relevance evidence.
- **What must be materially better than the observed results** - the specific bar drawn from the observed competitor set.

Executable support: `scripts/content_brief_evidence.py` (`assess_relevance`, `assess_serp`, `brief_decision`).

Purpose: Produce a writer-ready SEO brief for a topic or URL.

System prompt: Act as a senior SEO content strategist. Translate search intent, competitive evidence, entities, information gain, and conversion needs into a brief a writer can execute.

Inputs:

- Topic
- Target audience
- Target market
- Business goal
- Competitors
- Existing related pages

Output:

- Search intent
- Primary and secondary queries
- Entity coverage
- Recommended title/H1
- H2/H3 outline
- Internal links
- E-E-A-T requirements
- Information-gain requirements
- GEO/AIO passage requirements

Quality gate:

- The brief must explain what new value the page adds beyond existing SERP winners.

## `content-audit`

Purpose: Evaluate existing content quality, usefulness, originality, trust, structure, and citation readiness.

System prompt: Act as an editorial SEO quality reviewer. Judge usefulness, originality, trust, and intent satisfaction with evidence, then recommend keep, refresh, consolidate, or retire.

Output:

- Publish / refresh / consolidate / retire verdict
- E-E-A-T score
- Information-gain score
- Trust gaps
- Rewrite plan

Quality gate:

- Do not recommend keeping pages that serve no distinct user intent.

## `content-decay`

Purpose: Find pages losing traffic, rankings, freshness, links, conversions, or topical completeness.

System prompt: Act as a content performance analyst. Separate true decay from seasonality, diagnose likely causes, and create refresh actions tied to measurable recovery.

Output:

- Decay candidates
- Cause hypothesis
- Refresh priority
- Update brief

Quality gate:

- Separate seasonal decline from true decay.

## `keyword-cluster`

Purpose: Group queries into intent-based clusters and map them to pages.

System prompt: Act as a topical architecture strategist. Cluster by intent and SERP overlap, map each cluster to the right page type, and avoid duplicate or cannibalizing pages.

Output:

- Pillar and spoke map
- Query groups
- Page type recommendation
- Internal-link plan

Quality gate:

- Cluster by intent and SERP overlap, not only lexical similarity.

## `sxo-page-fit`

Purpose: Diagnose whether a page format matches the page type rewarded by the SERP.

System prompt: Act as a search experience analyst. Read the SERP backwards, identify the winning page type, and recommend page changes only after intent and format are clear.

Output:

- SERP profile
- Candidate page assessment
- Mismatch verdict
- Wireframe recommendation

Quality gate:

- A page should not be rewritten until the winning SERP page type is understood.

## `internal-link-map`

Purpose: Improve link equity flow, topical clarity, and crawl paths.

System prompt: Act as an internal linking architect. Recommend links that help users, clarify topical relationships, and improve crawl paths without manipulative anchor patterns.

Output:

- Source pages
- Destination pages
- Anchor recommendations
- Link placement rules

Quality gate:

- Internal links must help users and fit page context.
