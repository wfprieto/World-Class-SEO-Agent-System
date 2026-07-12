# Deterministic Content Intelligence

Verified against current official Google Search primary documentation on **2026-07-11**.

This pack measures supplied content and supplied review records. It is designed to support editorial decisions without converting heuristics into unsupported claims about factual accuracy, originality, expertise, user satisfaction, Google rankings, authorship, or causality.

## Commands

```bash
seoctl content quality \
  --input article.md \
  --title "Choosing an SEO Platform" \
  --audience "SEO leaders" \
  --purpose "Support a governed software decision" \
  --author "Bill Example" \
  --sources sources.json

seoctl content verify \
  --claims claims.json \
  --sources sources.json

seoctl content entities \
  --input article.md \
  --catalog entities.json

seoctl content brief \
  --relevance relevance.json \
  --serp serp.json \
  --information-gain information-gains.json \
  --sources sources.json \
  --audience "SEO leaders" \
  --intent "commercial investigation" \
  --primary-question "Which platform fits a governed SEO team?" \
  --section "Decision criteria" \
  --section "Tradeoffs"

seoctl content decay \
  --current current-period.json \
  --prior prior-period.json \
  --decline-threshold 0.20

seoctl content compare \
  --left current.md \
  --right comparison.md \
  --left-label current \
  --right-label comparison

seoctl content humanize \
  --input draft.md \
  --output revised.md
```

The existing `content relevance`, `content serp`, and `content brief-decision` commands remain canonical. The new `content brief` command consumes those evidence products rather than replacing their decision logic.

## Quality diagnostics

`content quality` reports measurable editorial signals such as:

- word, sentence, paragraph, heading, and citation-marker counts;
- average sentence and paragraph length;
- duplicate sentences;
- lexical diversity;
- whether title, audience, purpose, author, reviewer, and source-register fields were supplied.

The diagnostic score is scoped to `measurable_editorial_signals_only`. It is explicitly not:

- a Google score;
- a ranking probability;
- proof of helpfulness;
- proof of factual accuracy or originality;
- proof of author expertise or first-hand experience;
- proof of user satisfaction or search demand.

First-person language is reported as a text signal only. It does not verify that the author performed the described work.

For medical, legal, financial, safety, or other high-stakes content, the command warns that qualified human review and current authoritative sources are required.

## Claim and citation review

`content verify` validates a supplied claims register and source register. A source URL or citation alone does not verify a claim.

A claim can reach `SUPPORTED_BY_SUPPLIED_REVIEW` only when its record includes a declared source and a supplied assessment with:

```json
{
  "source_id": "s1",
  "relation": "supports",
  "reviewer": "reviewer@example.com",
  "reviewed_at": "2026-07-11",
  "note": "The relevant clause was reviewed."
}
```

Supported relation values are:

```text
supports
contradicts
partial
context_only
not_checked
```

Normalized claim states include:

```text
SUPPORTED_BY_SUPPLIED_REVIEW
PARTIALLY_SUPPORTED_BY_SUPPLIED_REVIEW
CONTRADICTED_BY_SUPPLIED_REVIEW
UNVERIFIED
UNSUPPORTED
SOURCE_MISSING
```

The service does not independently fetch, authenticate, or semantically read external sources. Its output says `independent_source_fetch = NOT_RUN` and preserves contradictions and missing evidence for human resolution.

## Entity analysis

`content entities` separates two evidence classes:

1. **Catalog matches:** exact case-insensitive occurrences of operator-supplied names or aliases. These prove string occurrence only.
2. **Heuristic candidates:** capitalized phrases reported with low confidence. These may be sentence starts, dates, brands, people, places, or false positives.

The command does not claim knowledge-graph identity, salience, relationship, or factual correctness. It reports `knowledge_graph_verification = NOT_RUN` unless a later authorized integration supplies that evidence.

## Evidence-gated briefs

`content brief` reuses the canonical relevance, SERP, and brief-decision implementation. A brief is ready for drafting only when:

- the canonical relevance and SERP gate permits it;
- information gain is supplied;
- a source register is supplied;
- audience, target intent, primary question, and at least one required section are supplied.

A passed brief authorizes drafting, not publishing. Claim-level verification remains required during drafting and review.

## Content-decay comparison

`content decay` compares two non-overlapping periods and reports:

- prior and current values;
- absolute and percentage change;
- direction, including lower-is-better handling for position, latency, error, and Core Web Vitals metrics;
- metrics that exceeded the operator's decline threshold.

The command reports observed changes only. It sets `cause = NOT_ASSESSED` because traffic or conversion decline can result from technical changes, SERP changes, competition, seasonality, attribution changes, market shifts, content changes, or other causes.

The command does not automatically change publication dates. Google Search documentation advises against changing dates merely to make pages appear fresh when content has not substantially changed.

## Content comparison

`content compare` reports measurable differences in:

- word and sentence counts;
- headings;
- citation markers;
- exact sentence overlap;
- shared and unique terms;
- shared and unique headings.

It returns `winner = null` and `quality_superiority = NOT_ASSESSED`. Structural and lexical differences do not establish usefulness, originality, copyright status, factual accuracy, or ranking superiority.

## Clarity-focused transformation

`content humanize` is a bounded clarity tool. It removes a small allowlist of generic filler phrases and normalizes whitespace and punctuation. It preserves detected numbers, URLs, and citation tokens and can write a reviewable output file.

The command explicitly reports:

```text
purpose = clarity_and_readability
ai_detector_evasion = NOT_SUPPORTED
authorship_concealment = NOT_SUPPORTED
facts_verified = false
```

It does not attempt to evade AI detectors, conceal authorship, misrepresent human involvement, or make unverified content sound authoritative.

Google Search guidance focuses on whether content is helpful and created primarily for people, not on whether automation was used. Google spam policies prohibit scaled content abuse when content is generated primarily to manipulate search rankings. This pack therefore evaluates supplied evidence and clarity without offering detector-evasion or mass-ranking-manipulation features.

## Input ceilings and failure behavior

- Text input is limited to 2,000,000 characters per operation.
- Claims, sources, entity records, and assessment lists are bounded to 2,000 records.
- Duplicate IDs, duplicate source references, invalid dates, nonfinite metrics, overlapping comparison periods, malformed source URLs, and unsupported relation values fail explicitly.
- Source URLs may use HTTP or HTTPS and may not contain embedded credentials.
- File parsing errors return structured nonzero CLI results rather than stack traces.
- No command performs external network calls or writes to a website or content management system.

## Runtime wiring

The canonical adapter registry exposes:

```text
content_intelligence
```

It passes normalized `AdapterResult` evidence through `runtime.tools.ToolDispatcher`. Command ownership and skill mappings remain in `seoctl/command-registry.json`.

## Official sources

Verified on 2026-07-11:

- Creating helpful, reliable, people-first content: https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- Google Search spam policies: https://developers.google.com/search/docs/essentials/spam-policies
- Publication dates and bylines: https://developers.google.com/search/docs/appearance/publication-dates
- Google Search guidance about AI-generated content: https://developers.google.com/search/blog/2023/02/google-search-and-ai-content

## Verification status

Deterministic tests cover:

- measurable editorial scoring and explicit exclusions;
- no invented experience or expertise;
- supplied review relationships, missing sources, and contradictions;
- catalog matches versus low-confidence entity candidates;
- canonical brief gating plus source and information-gain requirements;
- noncausal period-over-period decay analysis;
- comparison without an unsupported winner;
- clarity-only transformation with number, URL, and citation preservation;
- duplicate IDs, malformed dates, and bounded inputs;
- all seven installed command routes and combined content help;
- runtime ToolDispatcher wiring;
- canonical command registry and generated documentation synchronization;
- Windows and Ubuntu, Python 3.11 and 3.13 repository validation.

## Rollback

Rollback requires reverting the phase commit. No credentials, external writes, database migration, persistent model state, or optional dependency are introduced.
