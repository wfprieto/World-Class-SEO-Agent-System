# FLOW Prompts — Find

Use when demand and buyer language are unclear. Goal: surface real demand, intent, gaps, and the audience's own words. Apply only what the evidence supports; drop any statistic without a source.

## Keyword and demand research

```text
Act as an SEO demand researcher for [business/topic] serving [audience] in [market].
Using only the evidence I provide (query data, reviews, call notes, competitor pages), list:
1. The core jobs-to-be-done and the buyer questions behind them.
2. Head, mid, and long-tail queries grouped by intent (informational, comparison, transactional, local).
3. The exact phrases the audience uses (verbatim from reviews/calls), not marketing language.
4. Gaps where demand exists but our site has no credible page.
Flag any query the site cannot cover credibly, and say why. Do not invent search volumes.
```

## Intent and SERP mapping

```text
For the keyword set [keywords], classify the dominant intent per query and describe the
page type Google currently rewards (guide, comparison, product, local, tool). Note where an
AI Overview or local pack changes the click path. Recommend one primary page type per intent
cluster and the single next action a visitor should take.
```

## Content prioritization

```text
Rank these candidate topics [list] by: business outcome proximity (does it move a qualified
action?), demand strength (from supplied data), our credibility to cover it, and competitive
difficulty (from the SERP evidence I provide). Output a prioritized table with a one-line
rationale each and a recommended first three to build. No fabricated metrics.
```

## Topical relevance and variations

```text
For the pillar topic [topic], produce a coverage map: the sub-topics and entities a credible
authority must address, the questions that must be answered on-page, and the internal-link
relationships between them. Mark which sub-topics we can support with first-hand evidence now
versus which need new proof before publishing.
```

## Audience avatar

```text
Build a concise buyer profile for [offer] from the supplied evidence only: the trigger that
starts the search, the decision risks, the objections in the buyer's own words, the proof they
need, and the moment they are ready to act. Keep it to what the evidence shows; label any
inference as an assumption to validate.
```
