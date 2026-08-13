# FLOW Prompts - Optimize

## Use When

Use when an owned page, template, or asset exists but is hard to crawl, extract, trust, cite, or
act on. The Optimize stage improves the asset without inventing evidence or over-promising
rankings.

## Owner Agents

- SEO Copywriter/Content Agent
- SEO Technical Agent
- Senior SEO Engineer Agent
- SEO Accessibility Agent
- GEO / AIO Optimization Agent
- SEO Compliance & Legal Agent

## Required Inputs

- Target URL, template, draft, or page text.
- Target query, intent, and desired business outcome.
- Supplied evidence: crawl, render, SERP, GSC, analytics, reviews, expert sources, product facts,
  schema, Lighthouse/CWV, screenshots, or competitor examples.
- Public-facing copy requirements and anti-AI writing quality gate.

## Stop Conditions

- The page makes claims without evidence.
- Required public-facing copy would violate compliance, privacy, or brand rules.
- Technical recommendations require code access that is not available.

## Decision Tree

1. If content is vague or generic, run `content-quality-audit`.
2. If the page has no clear structure, run `outline-or-restructure`.
3. If copy is being drafted for public viewing, run `public-copy-draft`.
4. If schema is requested, run `schema-eligibility-check`.
5. If extraction or crawlability is weak, run `technical-extraction-audit`.
6. If SERP CTR is weak, run `title-meta-paa-refinement`.
7. If AI citation is desired, run `ai-citation-readiness-check`.
8. If multiple exports or tool results disagree, run `tool-evidence-merge`.

## Prompt Blocks

## Prompt: Content Quality Audit

```text
Audit [URL or draft] against [target query] and [buyer decision].

Return:
1. Primary answer clarity: does the page answer the main question immediately?
2. Information gain: what original evidence, experience, example, data, or perspective does it add?
3. E-E-A-T signals: experience, expertise, authoritativeness, trustworthiness.
4. Extraction readiness: heading hierarchy, direct answer blocks, tables, lists, named entities,
   dates, authors, and labeled sources.
5. Accuracy risks and unsupported claims.
6. Priority fixes with acceptance criteria.

Rules:
- Do not fabricate examples, statistics, credentials, awards, reviews, or outcomes.
- For public-facing copy, enforce the anti-AI writing quality gate: plain human language,
  specificity, no filler, no hype, no unsupported claims.
```

## Prompt: Outline Or Restructure

```text
Create or revise the structure for [topic/page] targeting [intent].

Required structure:
- direct answer or value statement near the top
- sections mapped to buyer questions
- proof sections where claims need support
- comparison/objection sections when relevant
- internal links in and out
- next action matching intent

Return:
1. H1.
2. H2/H3 outline.
3. Required evidence per section.
4. Internal link plan.
5. Schema candidates, if visible content supports them.
6. Sections to remove because they are duplicative, generic, or unsupported.
```

## Prompt: Public Copy Draft

```text
Write [page/section] from the supplied outline and evidence.

Rules:
- Buyer language first.
- Short paragraphs.
- Direct answers.
- Concrete nouns and specific proof.
- No hype.
- No filler.
- No unsupported facts.
- No em dashes.
- No fake scarcity, guarantees, reviews, rankings, or credentials.
- Every factual claim must trace to supplied evidence or be removed.

Return:
1. Draft copy.
2. Evidence register.
3. Claims needing review.
4. Suggested title/meta if requested.
5. Measurement event.
```

## Prompt: Schema Eligibility Check

```text
For [URL] and its visible content, recommend structured data only when eligible.

Check:
- page purpose
- visible content support
- current rich-result eligibility
- deprecated or retired schema patterns
- required and recommended properties
- conflicts with canonical, robots, or page type

Return:
1. Recommended schema types.
2. Types explicitly rejected and why.
3. Required visible content changes before markup.
4. Validation method.

Rule:
- Valid markup creates eligibility, not a guarantee of display, ranking, or AI citation.
```

## Prompt: Technical Extraction Audit

```text
Review [URL/template] for crawl, render, and extraction blockers.

Check:
- status code and redirects
- robots.txt and robots meta
- canonical intent
- SSR/render availability for main content
- title and meta accuracy
- heading order
- internal links
- image alt and format
- accessibility blockers
- LCP, INP, CLS risk indicators
- schema validity

Return:
1. Findings by severity.
2. Affected scope.
3. Evidence refs.
4. Owner: content, engineering, design, analytics, or legal.
5. Verification method.
6. Rollback or safety note for code-level fixes.
```

## Prompt: Title, Meta, And PAA Refinement

```text
Given [query], [current title], [current meta], and supplied SERP/PAA evidence, produce improved
variants.

Return:
- 3 title options.
- 3 meta descriptions.
- direct-answer rewrites for PAA-style questions.
- risk notes for clickbait, unsupported claims, or intent mismatch.

Rules:
- Match the page's actual content.
- Do not promise outcomes.
- Do not stuff keywords.
- Keep local modifiers natural when local intent exists.
```

## Prompt: AI Citation Readiness Check

```text
Assess [URL] for AI answer and citation readiness.

Check:
- direct answer near the top
- entity clarity
- factual consistency across owned profiles
- source labels and dates
- original evidence or experience
- server-rendered extractable content
- crawler accessibility
- off-site corroboration
- concise definitions and comparison tables

Return:
1. Citation readiness score: High / Medium / Low.
2. Why the page would or would not be cited.
3. Highest-leverage improvement.
4. Measurement plan: prompt, model/search surface, date, and citation outcome.

Rules:
- Do not claim AI visibility without observed prompt/search evidence.
- Date every AI-search observation.
```

## Prompt: Tool Evidence Merge

```text
Merge SEO evidence from [tool/export list] for [URL/template/topic].

Classify each input as:
- first-party observed: GSC, GA4, logs, crawl, rendered page, field data
- third-party estimated: rank tracker, keyword database, backlink index, SERP API
- manual observation: screenshot, SERP capture, AI-answer observation
- assumption or missing evidence

Return:
1. Evidence table: source, date range, scope, filters, strengths, limitations.
2. Conflicts: where tools disagree and why that might happen.
3. Decision-ready facts: what can be acted on now.
4. Blocked claims: what cannot be concluded.
5. Next best evidence: the smallest additional export or test needed.

Rules:
- First-party observed data beats third-party estimates for the same property and period.
- A paid-tool metric is not a cause by itself.
- Do not merge URL-level data unless URL normalization and date windows are explicit.
```

## Output Contract

Return:

- Minimum JSON keys: `"stage"`, `"asset"`, `"blocking_issue"`, `"recommended_changes"`,
  `"evidence_register"`, `"claims_for_review"`, `"verification_plan"`,
  `"recommended_next_stage"`.
- `"stage": "optimize"`
- `asset`: URL, template, or draft
- `blocking_issue`: content, technical, schema, trust, extraction, CTR, or AI citation
- `recommended_changes`
- `evidence_register`
- `evidence_merge`: source classes, conflicts, decision-ready facts, and blocked claims
- `claims_for_review`
- `verification_plan`
- `recommended_next_stage`
