# FLOW Prompt Library Skill

Skill for the SEO Copywriter/Content Agent and Senior SEO Strategist Agent. Follows `skill-definition-standard.md`.
SKILL_INDEX category: Content and IA Skills.

Clean-room rebuild of a stage-based SEO prompt system. Original text and attribution were not reused; this is re-authored from the concept. Prompts live in `flow-prompts/` grouped by stage: find, leverage, optimize, win, local.

The model: SEO is one connected loop across search surfaces (organic result, AI answer, local pack, business profile, community reference, sales-assisted page), not separate channels. Four stages name where progress is blocked:

- Find: demand and buyer language are unclear. Research keywords, intent, gaps, and audience.
- Leverage: the brand is not corroborated off-site. Build distributed evidence and authority.
- Optimize: the owned asset is hard to extract or trust. Improve content, structure, schema, and E-E-A-T.
- Win: traffic exists but business impact is weak. Build bottom-funnel pages and connect discovery to revenue.
- Local: the same loop applied to Business Profile, local pages, and map visibility.

---

## `flow-prompt-run`

Purpose: Select and apply the right stage-specific prompt(s) to a URL or topic, driven by evidence rather than improvisation.

System prompt: Act as an evidence-led SEO strategist. Name the blocking stage first, then apply only the relevant prompts. Use only supplied evidence (customer language, query data, analytics, reviews, call notes). Every numeric claim must trace to a source or be removed. Write for three readers: the buyer, the search engine, and the AI agent that may summarize the business.

Required inputs:

- Target URL or topic
- Business outcome the work should move (a qualified call, a demo, a purchase, entity reconciliation)
- Available evidence: customer language, query/GSC data, analytics, reviews, objections, existing page text
- Market, audience, and buying stage

Execution steps:

1. Name the search surface and the business outcome before writing.
2. Decide which stage is blocking: unclear demand language -> Find; weak off-site corroboration -> Leverage; hard-to-extract or low-trust asset -> Optimize; traffic without business impact -> Win; local visibility -> Local.
3. Load the matching file in `flow-prompts/` and apply only the relevant prompts.
4. Separate observed evidence from assumption. Drop unsupported statistics.
5. Return the drafted asset plus a short evidence register and the measurement event that will judge it.

Output format:

- The requested asset (brief, outline, rewrite, page plan), an evidence register (claim -> source), and a measurement plan (visibility indicator + business indicator).

Quality gate:

- No fabricated statistics. Buyer language before company language. The asset must be extractable by an AI agent (clear headings, direct answers, labeled sources) without depending on private examples.

Failure conditions:

- Missing business outcome or evidence. Wrong stage selected.

Fallback:

- If evidence is missing, request it or write the safer version and mark the gaps. If the stage is unclear, run Find first.

## Stage files

- `flow-prompts/find.md`
- `flow-prompts/leverage.md`
- `flow-prompts/optimize.md`
- `flow-prompts/win.md`
- `flow-prompts/local.md`

## Cross-references

- Deeper keyword clustering: the `serp-overlap-cluster` skill.
- Off-site link data: the backlink skills.
- Content quality and AI-search readiness: `content-audit` and `geo-aio-citation-audit`.
- Local execution: `local-seo-audit` and the geo-grid maps skills.
