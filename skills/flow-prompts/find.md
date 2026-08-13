# FLOW Prompts - Find

## Use When

Use when demand, buyer language, audience segments, or content priorities are unclear.
The Find stage turns raw market signals into a defensible opportunity map.

## Owner Agents

- SEO Copywriter/Content Agent
- Senior SEO Strategist Agent
- Competitive Intelligence Agent
- SEO Research and Development Agent

## Required Inputs

- Business model, offer, audience, market, and conversion goal.
- Existing pages, products, services, or topical areas.
- At least one evidence source: GSC queries, analytics, sales notes, reviews, support tickets,
  CRM objections, SERP captures, competitor pages, paid-search queries, or keyword exports.
- Known constraints: budget, geography, compliance limits, publication capacity, and proof
  available.

## Stop Conditions

- No business outcome is supplied.
- No evidence source exists and the user asks for ranked priorities or demand strength.
- The topic is YMYL or regulated and the required expertise, review, or compliance evidence is
  unavailable.

## Decision Tree

1. If the audience and buyer trigger are unknown, run `buyer-language-discovery`.
2. If the user has a broad topic but no query set, run `keyword-demand-map`.
3. If a query set exists but no page plan exists, run `intent-serp-map`.
4. If there are too many possible topics, run `content-prioritization`.
5. If the site needs topical authority, run `topical-coverage-map`.
6. If all evidence is weak or inferred, return a research request instead of a content plan.
7. If paid keyword, SERP, or rank-tracking APIs are requested, run `cost-aware-keyword-tool-plan`
   before any recommendation that depends on metered data.

## Prompt Blocks

## Prompt: Buyer Language Discovery

```text
Act as an evidence-led SEO demand researcher for [business/topic] serving [audience] in [market].

Use only supplied evidence: reviews, sales calls, support tickets, CRM notes, query exports,
competitor pages, forum posts, SERP captures, or analytics. Do not invent search volume,
conversion rates, quotes, or market size.

Return:
1. Search triggers: what event starts the search.
2. Jobs-to-be-done: what the buyer is trying to accomplish.
3. Buyer phrases: exact wording from evidence, with source labels.
4. Objections and risks: what could stop the buyer from acting.
5. Proof needed: examples, credentials, prices, reviews, demos, data, or policies.
6. Assumptions to validate: any inference not directly observed.

Quality gate:
- Every buyer phrase must cite the supplied source.
- Inferred motivations must be labeled as assumptions.
- Do not translate buyer language into company jargon.
```

## Prompt: Keyword Demand Map

```text
For [business/topic], build a keyword opportunity map using the supplied query and market
evidence.

Group queries into:
- informational
- commercial investigation
- comparison
- transactional
- local
- branded
- support or retention

For each group, return:
1. Primary query pattern.
2. Secondary and long-tail variants.
3. Buyer intent.
4. Recommended page type.
5. Required proof or source material.
6. Fit score: High / Medium / Low, based on business relevance and credibility.

Rules:
- Do not invent search volume.
- If volume, difficulty, or CPC appears, label the exact source.
- Flag queries the site should not target because it lacks expertise, evidence, or a real offer.
```

## Prompt: Cost-Aware Keyword Tool Plan

```text
For [business/topic], decide whether free evidence is enough or whether a paid keyword/SERP API is
justified.

Inputs:
- budget tier
- required market, location, language, and device
- existing GSC/GA4/query evidence
- expected number of keywords, SERP pulls, competitor domains, or rank checks
- decision the data must support

Return:
1. Free-first path: what can be done with GSC, GA4, crawl data, sales notes, and manual SERP review.
2. Paid-data path: what API/tool data is needed and why.
3. Estimated request class: keyword ideas, SERP capture, rank tracking, backlinks, or domain overview.
4. Cost and quota risk: Low / Medium / High, with assumptions.
5. Stop condition: what evidence gap remains if budget is not approved.
6. Data retention note: what can be stored, anonymized, or discarded.

Rules:
- Do not recommend paid API calls without a business decision they support.
- Do not imply that third-party volume, difficulty, or rank data is exact truth.
- If credentials or budget approval are missing, return a free-first plan.
```

## Prompt: Intent And SERP Map

```text
For the keyword set [keywords], classify the dominant intent and the current SERP pattern.

Use supplied SERP evidence only. For each cluster, identify:
1. Dominant result type: guide, product, category, comparison, local pack, video, forum, tool,
   documentation, marketplace, or AI answer.
2. Page type Google appears to reward.
3. Searcher next action.
4. Content format required to compete.
5. Whether the query needs a new page, a page refresh, an internal link, or no action.
6. AI/search-surface notes: AI Overview, local pack, image/video, PAA, or forum dominance.

Output:
- Cluster table.
- Recommended URL/page type.
- Evidence gaps.
- One highest-leverage action.
```

## Prompt: Content Prioritization

```text
Rank these candidate topics: [list].

Score each topic from 1-5 on:
- Business outcome proximity.
- Evidence strength.
- Organic demand signal.
- Credibility to publish.
- Competitive feasibility.
- Reuse across search, AI answer, social, sales, or support.

Return:
1. Prioritized table.
2. Why this should or should not be built now.
3. Required source material before publication.
4. Recommended owner agent.
5. First three topics to build or refresh.

Rules:
- If the evidence does not support a score, mark it `Unknown`.
- Do not prioritize vanity traffic over business relevance.
```

## Prompt: Topical Coverage Map

```text
For the pillar topic [topic], build a topical authority map.

Return:
1. Core entity set.
2. Subtopics a credible source must cover.
3. Questions that need direct answers.
4. Comparison and alternative pages needed.
5. Internal links in and out.
6. Evidence needed for information gain.
7. Pages that should not be created because they would be thin, duplicative, or unsupported.

Quality gate:
- The map must separate what the site can publish now from what needs new evidence first.
- Programmatic page ideas must include uniqueness criteria and anti-thin-content safeguards.
```

## Prompt: Audience Avatar

```text
Create a concise buyer profile for [offer] using supplied evidence only.

Return:
- Trigger.
- Role or persona.
- Context of need.
- Decision risk.
- Objections in the buyer's words.
- Proof needed.
- Search phrases.
- Readiness-to-act signal.
- Next research question.

Rules:
- Keep it evidence-bound.
- Label assumptions.
- Do not include demographic stereotypes unless directly supplied and relevant.
```

## Output Contract

Return:

- Minimum JSON keys: `"stage"`, `"recommended_next_stage"`, `"evidence_register"`,
  `"opportunity_map"`, `"page_or_asset_recommendations"`, `"risks"`, `"verification"`.
- `"stage": "find"`
- `recommended_next_stage`: `Leverage`, `Optimize`, `Win`, `Local`, or `Stop for evidence`
- `evidence_register`: claim to source mapping
- `opportunity_map`: prioritized opportunities
- `tool_plan`: free-first or paid-data path with budget and credential guardrails
- `page_or_asset_recommendations`: page type, owner, evidence needed
- `risks`: unsupported claims, compliance concerns, thin-content risks
- `verification`: how the Scrummaster can confirm the Find output is evidence-backed
