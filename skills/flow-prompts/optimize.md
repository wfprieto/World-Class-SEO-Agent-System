# FLOW Prompts — Optimize

Use when the owned asset is hard to extract or hard to trust. Goal: make the page clear for the buyer, the search engine, and the AI agent. Pick the 2-3 prompts that match the current gap; do not run all of them.

## Content audit (core)

```text
Audit [URL] against the query it targets and the buyer's decision. Report:
1. Does the page answer the primary question in the first screen, in plain language?
2. Information gain: what does it add beyond the top competing pages, from real evidence?
3. Extraction readiness: heading hierarchy, direct-answer blocks, tables where useful, labeled sources.
4. E-E-A-T signals present or missing (author, credentials, dates, primary sources, original media).
5. Trust and accuracy risks.
Output prioritized fixes with acceptance criteria. Use only supplied evidence; no invented stats.
```

## Blog/post outline

```text
Create an outline for [topic] targeting [intent]. Lead with the direct answer, then structure
H2/H3 around the questions a buyer actually asks. Mark where original data, examples, or media
must appear. Note the internal links in and out. Keep it extractable by an AI agent.
```

## Draft writing

```text
Write [section/page] from this outline and evidence. Buyer language first. Short paragraphs,
direct answers, concrete specifics. No hype, no filler, no unsupported claims, no em dashes.
Every factual claim traces to a supplied source or is cut. End with the next action for the reader.
```

## Schema recommendation

```text
For [URL] and its visible content, recommend the correct, current structured-data type(s).
Check against the schema-deprecation registry before recommending anything. Mark up only visible
content. State that valid markup creates eligibility, not a guarantee of display or ranking.
```

## Technical/on-page audit

```text
Review [URL] for on-page and technical extraction blockers: title/meta accuracy, heading order,
canonical intent, render dependence (does key content require JS?), internal linking, image and
CWV impact. Return a prioritized, owner-assigned fix list with verification methods.
```

## CTR and PAA refinement

```text
Given the current title/meta and the query, propose title and meta variants that match intent
and improve click likelihood without clickbait. Reword the on-page answers to directly satisfy
the People-Also-Ask questions the SERP shows, keeping answers self-contained.
```

## AI-search visibility check

```text
Assess how well [URL] can be cited by AI answer engines: server-side rendered content, crawler
access, a self-contained answer near the top, entity clarity, and off-site corroboration.
Recommend the highest-leverage change. Date any AI-visibility claim and tie it to a measurement.
```
