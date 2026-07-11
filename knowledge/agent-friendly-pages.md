# Agent-Friendly Pages

How to build pages that a person, a search engine, and a permitted AI agent can all understand. The goal is one good page for users, not a machine-only variant.

**Evidence labels:** `FACT` confirmed against a primary source on the check date. `ANALYSIS` reasoned from evidence. `VERIFY` time-sensitive; re-check before client-facing use.
**Crawler rules checked:** 2026-07-11. Crawler tokens and platform behaviour change; re-verify against each provider's own documentation.

This file does not duplicate two existing authorities. Use them together:

- `knowledge/geo-readiness-rubric.md` scores generative-search readiness (citability, structure, authority, accessibility, multi-modal). This file covers page construction, not scoring.
- The `rendered-visual-audit` skill produces the rendered-versus-source evidence this file depends on. This file does not re-specify rendering methodology.

## What this file will not claim

- `llms.txt` is **not** required for Google Search or for AI visibility. Google states that machine-readable AI files are not used by Google Search and will not help or harm visibility (`FACT`, May 2026 generative-AI optimization guide).
- No special AI-only markup or schema is required.
- Chunking content does **not** guarantee citation.
- AI crawlers do **not** all behave identically.
- Crawler access **does not guarantee** inclusion, indexing, or citation.
- A separate agent-only page must not replace the primary user page. Serving different content to agents than to users is cloaking risk and a trust failure.

## Construction requirements

**Accessible primary content.** The main content must exist in the server response or be reliably rendered. AI crawlers generally do not execute JavaScript, so client-only content is invisible to them (`FACT` for the common case; confirm per crawler). Prove it with rendered-versus-source evidence from `rendered-visual-audit`, not by assumption.

**Semantic HTML.** Real headings in order, lists, tables for comparative data, `<main>`, `<nav>`, `<article>`. Structure carries meaning; styled `<div>` soup does not.

**Stable URLs.** One canonical URL per resource. No session identifiers or volatile parameters in the primary content URL.

**Crawlable internal links.** Real `<a href>` elements. Router-only click handlers are not links.

**Clear page purpose.** State what the page is and who it is for, near the top, in plain language.

**Self-contained answers where useful.** A reader (or an agent) should be able to lift the answer to the page's primary question without needing the rest of the page. This helps extraction. It does not guarantee citation (`ANALYSIS`).

**Source attribution.** Cite primary sources for factual claims and link them.

**Visible authorship and accountability** where it matters (YMYL, expertise-dependent, and commercial-advice content): author, credentials, publisher, contact route.

**Accurate structured data** describing content that is actually visible. Check every type against `knowledge/schema-deprecation-registry.md` before recommending it. Markup creates eligibility only; it never guarantees display or ranking.

**Canonical and indexation controls** that are intentional and consistent: self-referencing canonical, no conflict between canonical, `noindex`, sitemap inclusion, and internal links.

**Accessible navigation and content.** Keyboard reachable, sensible focus order, sufficient contrast, meaningful alt text. Accessibility and agent-readability are largely the same work.

**Media context.** Captions, transcripts, and surrounding text that explain what the media shows. Label AI-generated imagery per `knowledge/ai-image-labeling.md`.

**Update dates and freshness.** Publish and meaningful last-updated dates. Do not fake freshness by touching timestamps.

**Content provenance.** Be honest about what is original, what is synthesised, and what is sourced.

**User benefit over machine-only optimisation.** If a change helps only machines, it is not an improvement.

## Crawler controls (`VERIFY` — re-check per provider)

`robots.txt` expresses a request. It is not enforcement: several crawlers have been documented ignoring it, so blocking at the server or CDN is the only real control (`FACT`, widely documented 2025-2026).

Training and retrieval are separate decisions, and the tokens differ:

| Purpose | Tokens (checked 2026-07-11) |
|---|---|
| OpenAI training vs search/user | `GPTBot` (training) vs `OAI-SearchBot`, `ChatGPT-User` (search/retrieval) |
| Anthropic training vs search/user | `ClaudeBot` vs `Claude-SearchBot`, `Claude-User` |
| Perplexity | `PerplexityBot`, `Perplexity-User` |
| Google generative AI | `Google-Extended` |

`Google-Extended` is unusual and often misunderstood: it is a **robots.txt token only, not a real user-agent string that appears in server logs**, and it controls use of the content for Google's generative AI products. It does **not** affect classic Google Search indexing (`FACT`, checked 2026-07-11).

Consequence: blocking training crawlers protects content from model training but does not remove you from AI search. Blocking the search/retrieval agents (`OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`) removes eligibility for citation in those answers. Decide those two questions separately, and record the decision.

## Rendered-versus-source evidence

Never claim a page is agent-friendly from source HTML alone. Capture both, and state which one produced the finding. If the primary content only appears after JavaScript, say so and treat the page as invisible to non-rendering crawlers until fixed. Use the `rendered-visual-audit` skill; do not build a second rendering method.

## What good looks like

One URL. Server-accessible primary content. Honest structure. A clear answer near the top. Named sources. A real author where it matters. Accurate schema for visible content. Intentional indexation. Accessible to a keyboard, a screen reader, a crawler, and an agent — because they all want the same thing: a page that plainly says what it is.

## Primary sources

- Google, optimizing for generative AI features in Search: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- Google Search Central, crawling and indexing documentation: https://developers.google.com/search/docs/crawling-indexing
- OpenAI crawler documentation: https://platform.openai.com/docs/bots
- Anthropic crawler documentation: https://support.anthropic.com
- Perplexity crawler documentation: https://docs.perplexity.ai
- Bing/Microsoft webmaster guidelines: https://www.bing.com/webmasters/help/webmaster-guidelines-30fba23a
- W3C WCAG: https://www.w3.org/WAI/standards-guidelines/wcag/

Re-verify each crawler token against its own provider before publishing client guidance.
