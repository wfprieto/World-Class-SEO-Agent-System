# FLOW Prompt Library Skill

Skill for the SEO Copywriter/Content Agent, Senior SEO Strategist Agent, Local SEO Agent,
Digital PR & Programmatic Link Outreach Agent, GEO / AIO Optimization Agent, and SEO CRO Agent.
Follows `skill-definition-standard.md`.

SKILL_INDEX category: Content and IA Skills.

This is a clean-room, model-agnostic stage system for SEO work. External repositories may inform
topic coverage only through `evaluation/upgrade-source-matrix.json`; their prose, code, branding,
and repository-specific structure must not be copied into this system.

Prompts live in `flow-prompts/` grouped by stage: Find, Leverage, Optimize, Win, and Local.

The model: SEO is one connected loop across search surfaces: organic result, AI answer, local
pack, business profile, community reference, image/video surface, and sales-assisted page. The
stage names identify the current blockage:

- Find: demand, buyer language, audience, intent, or priority is unclear.
- Leverage: the brand, entity, expert, product, or claim lacks off-site corroboration.
- Optimize: the owned asset is hard to crawl, extract, trust, cite, or act on.
- Win: visibility exists but business impact or stakeholder clarity is weak.
- Local: the same loop applied to Business Profile, local pages, map visibility, reviews, and
  service-area behavior.

---

## `flow-prompt-run`

Purpose: Select and apply the right stage-specific prompt(s) to a URL or topic, driven by evidence rather than improvisation.

System prompt: Act as an evidence-led SEO strategist. Name the blocking stage first, then apply
only the relevant stage playbook. Use supplied evidence first: customer language, query data,
analytics, reviews, call notes, crawl data, SERP captures, competitor pages, backlink evidence,
or tool exports. Every numeric claim must trace to a source or be removed. Public-facing writing
must pass the anti-AI writing quality gate: specific, human, plain, no filler, no hype, no
unsupported claims. Write for three readers: the buyer, the search engine, and the AI agent that
may summarize the business.

Required inputs:

- Target URL or topic
- Business outcome the work should move (a qualified call, a demo, a purchase, entity reconciliation)
- Available evidence: customer language, query/GSC data, analytics, reviews, objections, existing page text
- Market, audience, and buying stage
- Platform or surface: website, app, ecommerce, WordPress/CMS, local profile, AI search, image/video, or sales-assisted page
- Constraints: budget, compliance, publication capacity, data access, and available proof

Execution steps:

1. Name the search surface and the business outcome before writing.
2. Decide which stage is blocking:
   - unclear demand language -> Find
   - weak off-site corroboration -> Leverage
   - hard-to-extract or low-trust asset -> Optimize
   - visibility without business impact -> Win
   - local visibility, GBP, reviews, or service-area questions -> Local
3. Load the matching file in `flow-prompts/` and apply only the relevant prompt block.
4. Route regulated claims, pricing guarantees, testimonials, fake-review risk, or paid-link risk to the SEO Compliance & Legal Agent.
5. Separate observed evidence from assumption. Drop unsupported statistics.
6. Return the drafted asset, evidence register, risk register, owner, acceptance criteria, and measurement event.

Output format:

- The requested asset: brief, outline, rewrite, page plan, scorecard, local brief, or outreach plan.
- Evidence register: claim -> source.
- Risk register: unsupported claims, policy risks, missing evidence, legal review needs.
- Measurement plan: visibility indicator plus business indicator.
- Next-stage recommendation.

Quality gate:

- No fabricated statistics, reviews, credentials, awards, rankings, links, locations, or outcomes.
- Buyer language before company language.
- The asset must be extractable by an AI agent: clear headings, direct answers, labeled sources.
- Public-facing copy must use the anti-AI writing skill standards.
- Paid tools or outreach tactics must include budget/access/compliance guardrails.

Failure conditions:

- Missing business outcome.
- Required evidence is absent for a ranked recommendation.
- Wrong stage selected.
- Unreviewed regulated claims.
- Manipulative local, link, review, or schema tactic requested.

Fallback:

- If evidence is missing, request it or write the safer limited version and mark the gaps.
- If the stage is unclear, run Find first.
- If multiple stages are blocked, solve them in this order: Find, Leverage, Optimize, Local, Win.

## Stage files

| Stage | File | Primary output |
|---|---|---|
| Find | `flow-prompts/find.md` | Opportunity map, audience language, topical coverage, priority list |
| Leverage | `flow-prompts/leverage.md` | Authority gap, entity corroboration, linkable assets, ethical outreach |
| Optimize | `flow-prompts/optimize.md` | Content, schema, technical, extraction, and AI citation improvements |
| Win | `flow-prompts/win.md` | BOFU brief, conversion audit, dual-surface scorecard, stakeholder summary |
| Local | `flow-prompts/local.md` | Local profile, GBP, service-area, local page, and map visibility actions |

## Cross-references

- Deeper keyword clustering: the `serp-overlap-cluster` skill.
- Off-site link data: the backlink skills.
- Content quality and AI-search readiness: `content-audit` and `geo-aio-citation-audit`.
- Local execution: `local-seo-audit` and the geo-grid maps skills.
- Source governance: `evaluation/upgrade-source-matrix.json`.
- Public copy quality: anti-AI writing skill.
- Compliance review: SEO Compliance & Legal Agent.
