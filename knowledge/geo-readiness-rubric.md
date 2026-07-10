# Generative Search Readiness Rubric

**Status:** Primary-source reconciled operational rubric  
**Version:** 2.0.0  
**Last reconciled:** 2026-07-10  
**Next scheduled review:** 2026-08-10 for crawler directives; 2026-10-10 for the full rubric  
**Primary consumers:** GEO/AIO Optimization Agent, single-page audit, and content strategy  
**Canonical source path:** `knowledge/geo-readiness-rubric.md`

## Purpose and boundary

This internal planning rubric evaluates technical eligibility, usefulness, trust, and measurement across generative search. It is not a ranking factor, citation probability, certification, or guarantee. For Google, generative visibility remains grounded in normal Search systems; no special AI markup, `llms.txt`, content “chunking,” ideal page length, or special schema is required.

## Evidence labels

- `VERIFIED_CURRENT`: confirmed against a current platform-owned primary source.
- `OBSERVED`: directly measured on the audited site or platform.
- `ANALYSIS`: reasoned recommendation supported by evidence, but not a platform rule.
- `REVERIFY_AT_RUN`: bot names, IP ranges, reporting, or behavior must be checked immediately before implementation.
- `UNKNOWN`: not measured or unavailable.

## Hard gates

Return `NOT_ELIGIBLE` for the relevant platform when content is intentionally blocked from that platform's required crawler, not publicly accessible, not indexable where index eligibility is required, or disallowed from snippets where the platform requires snippets.

Return `CRITICAL_RISK` instead of a readiness score when content is materially deceptive, unsafe, unsupported on a YMYL topic, or generated at scale primarily to manipulate rankings.

## Platform-score rule

Score platforms separately when access, eligibility, or measurement differs. A secondary portfolio summary must not hide an individual hard gate, and one platform's result is not evidence of visibility on another.

## Weighted operational score

| Dimension | Weight | What it measures |
|---|---:|---|
| Technical eligibility and access | 25 | Crawlability, indexability, render parity, canonical clarity, and platform access decisions |
| User value and answer usefulness | 25 | Originality, task completion, clear explanations, and content that resolves the query |
| Evidence and trust | 20 | Accurate claims, primary sources, qualified creators, dates, disclosures, and corrections |
| Entity and ecosystem consistency | 15 | Consistent brand/person/product facts across owned and authoritative external sources |
| Relevant multimodal and structured support | 10 | Useful images/video, accessible media, accurate structured data, product feeds, and business profiles where applicable |
| Measurement and governance | 5 | Dated query set, platform-specific observations, referral/reporting data, and change controls |

Banding:

- `80–100`: strong operational readiness
- `60–79`: workable with material opportunities
- `40–59`: partial readiness
- `<40`: weak or poorly evidenced readiness

A numeric score does not override a hard gate.

## Dimension checks

### 1. Technical eligibility and access

- Public URL returns an appropriate status and is not accidentally blocked.
- Canonical and index directives are coherent.
- Important content is present after the crawler/rendering path used by the platform. Server-side rendering is not a universal requirement; measure crawl/render parity instead of assuming JavaScript is invisible.
- Google generative Search eligibility uses normal Search technical requirements and snippet eligibility.
- Platform-specific search crawlers are allowed or blocked intentionally, with the business tradeoff recorded.
- WAF rules verify official IP sources where the provider publishes them; do not trust a user-agent string alone for security decisions.

### 2. User value and answer usefulness

- The page directly resolves the target task without burying the answer behind irrelevant material.
- Explanations are complete enough to stand on their own and include the context needed to avoid misinterpretation.
- Original information, expert analysis, first-party data, useful tools, or meaningful synthesis adds value beyond commodity summaries.
- Headings, tables, lists, and concise passages are used when they improve human comprehension. Do not force fixed word counts or artificial “AI chunks.”

### 3. Evidence and trust

- Material factual claims are attributable to current, reliable sources.
- Author, organization, ownership, commercial relationships, and update dates are transparent where relevant.
- High-risk content has qualified review, clear limitations, and stronger primary evidence.
- Corrections and content freshness are governed by the actual volatility of the topic, not a universal refresh schedule.

### 4. Entity and ecosystem consistency

- Organization, people, products, locations, and contact facts are internally consistent.
- Official profiles, Merchant Center, Business Profile, publisher profiles, and reputable external sources do not materially contradict the site.
- Do not manufacture mentions, reviews, citations, or forum activity. External corroboration must be authentic.

### 5. Multimodal and structured support

- Images, video, diagrams, and data visualizations are relevant, accessible, and substantively useful.
- Structured data matches visible content and current Google feature documentation.
- Product feeds and Google Business Profile are used where they independently improve product or local visibility.
- Structured data is not required for Google generative Search and must not be scored as a special AI hack.

### 6. Measurement and governance

- Maintain a dated, versioned query set by platform, locale, device/context, and user intent.
- Record whether the brand/page was linked, cited, mentioned without a link, or absent.
- Use platform-native reporting or referral data where available. For Google, use the current Search Console Generative AI performance reporting when available to the property, alongside ordinary Search performance and conversion data.
- Separate observed inclusion from causal claims. A visibility change near an edit or algorithm update is correlation until stronger evidence exists.

## Platform access matrix

| Platform or purpose | Current access control | Operational guidance |
|---|---|---|
| Google Search AI Overviews / AI Mode | Normal Google Search crawl, index, quality, and snippet eligibility | No separate AI crawler or special markup is required. `llms.txt` has no positive or negative effect on Google Search according to current Google guidance. |
| ChatGPT search | `OAI-SearchBot` | Allow when search discovery, summaries, citations, and links are desired. Treat `GPTBot` separately because it concerns potential model-training collection, not ChatGPT search eligibility. |
| Claude search | `Claude-SearchBot` | Allow when Claude search visibility is desired. `Claude-User` governs user-directed retrieval, and `ClaudeBot` concerns potential model-training collection. Make each decision separately. |
| Perplexity search | `PerplexityBot` | Allow when Perplexity search visibility is desired and keep WAF IP ranges synchronized from the official source. `Perplexity-User` is a separate user-initiated fetcher. |
| Bing/Copilot | Bing search crawl and index controls | Verify current Bing documentation and Webmaster status at execution time. Do not infer Copilot visibility from Google or another platform. |

All bot names, IP endpoints, and behaviors are `REVERIFY_AT_RUN` because providers can change them.

Robots directives express crawl preferences; they are not authentication or a security boundary. User-agent strings can be spoofed. Where a provider publishes IP verification data and a WAF allow rule is needed, match both the documented user agent and current official IP ranges. Do not expose private or authenticated content merely to improve search visibility.

Search indexing, user-initiated retrieval, and model-training collection are separate decisions. Record the business owner's choice for each purpose instead of applying one blanket allow or block rule.

## `llms.txt` policy

- For Google Search: informational only; do not award readiness points or claim a ranking/citation effect.
- For other services: document the consuming service and verified behavior before implementation.
- Presence alone is not a readiness signal. Incorrect or stale content can create governance risk.

## Evidence, privacy, challenge, and escalation controls

Reuse canonical technical, content, entity, and crawler evidence by evidence ID; repeated mention across platforms is not independent corroboration. Do not retain private prompts, account-only answer logs, personal data, or confidential query sets beyond the approved measurement purpose. When platform evidence conflicts, coverage is weak, or a recommendation would change crawler access or expose content to a new service, require an independent challenge and escalate the policy decision to the accountable owner before implementation.

## Required output

Return:

- Platform(s), locale, date, and tested query set
- Hard-gate result by platform
- Per-dimension score with evidence and unknowns
- Crawler/robots/WAF decision matrix
- Top improvements with impact, effort, owner, acceptance criteria, and verification method
- Measurement baseline and next comparison date
- Explicit statement that inclusion, links, mentions, and citations are not guaranteed
- Per-platform score and hard-gate state; any portfolio summary shown separately

## Primary sources

- Google AI features and website eligibility: https://developers.google.com/search/docs/appearance/ai-features
- Google generative-AI optimization guide: https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- OpenAI publisher guidance: https://help.openai.com/en/articles/12627856-publishers-and-developers-faq
- Anthropic crawler guidance: https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler
- Perplexity crawler guidance: https://docs.perplexity.ai/docs/resources/perplexity-crawlers
