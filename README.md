# World-Class SEO Agent System

[![Validate repository](https://github.com/wfprieto/World-Class-SEO-Agent-System/actions/workflows/validate.yml/badge.svg)](https://github.com/wfprieto/World-Class-SEO-Agent-System/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

A model-agnostic, evidence-first operating system for technical SEO, content strategy, GEO/AIO, local SEO, accessibility, CRO, compliance, security, digital PR, competitive intelligence, and continuous SEO research.

It gives SEO professionals and coding teams a structured way to route work, use specialist agents and skills, apply evidence and quality gates, and produce verifiable implementation plans.

## Get a working result in 60 seconds

Requires Python 3.11 or later.

```bash
python -m pip install -e .
seoctl --registry-check
python main.py "Run a full SEO audit" --domain https://example.com
```

For a safe dry-run execution:

```bash
python main.py "Run a full SEO audit" --domain https://example.com --execute
```

Start with [SYSTEM_MAP.md](SYSTEM_MAP.md), then route a request with [workflows/request-routing.md](workflows/request-routing.md).

## Safe and authorized use

Only assess websites, data, APIs, and accounts you are authorized to access. Never commit credentials, client exports, personal data, or generated private artifacts. Live integrations are optional and read credentials from local environment variables; see [.env.example](.env.example).

## What This Is

This is not a prompt dump. It is a structured SEO operating system made of:

- 25 specialist SEO agents
- Reusable SEO skills
- Shared evidence standards
- Cross-agent workflows
- Lightweight executable runtime and router
- Tool adapter contracts and offline-safe parsers
- Knowledge-source rules
- Quality gates and anti-patterns
- JSON output schemas
- Semantic validation and tests
- Practical report and implementation templates
- LLM-specific operating guides for Codex, ChatGPT, Claude, Claude Code, Replit, and Manus

The core system is LLM agnostic. Any capable coding or reasoning model can use the files. The top-level model control files provide environment-specific operating guidance without changing the system itself.

## Who It Is For

- SEO engineers
- Technical SEO specialists
- SEO strategists
- Content SEO teams
- Agency operators
- Growth engineers
- Product teams responsible for organic acquisition
- Developers building SEO-aware sites and applications
- AI/coding-agent users who want repeatable SEO workflows

## Core Operating Rule

Every SEO recommendation must be evidence-backed, user-first, policy-safe, technically verifiable, and mapped to an owner, risk level, acceptance criteria, and measurement plan.

## Repository Structure

```text
World-Class-SEO-Agent-System/
|-- README.md
|-- Codex.md
|-- ChatGPT.md
|-- Claude.md
|-- Claudecode.md
|-- Replit.md
|-- Manus.md
|-- SYSTEM_SPEC.md
|-- agents/
|-- adapters/
|-- skills/
|-- workflows/
|-- knowledge/
|-- schemas/
|-- orchestration/
|-- runtime/
|-- tests/
|-- examples/
|-- scripts/
`-- templates/
```

## Start Here

1. Read [`SYSTEM_MAP.md`](SYSTEM_MAP.md) for the fastest navigation path through the repository.
2. Read [`SYSTEM_SPEC.md`](SYSTEM_SPEC.md) for the system mission, evidence hierarchy, operating modes, and approval gates.
3. Use [`workflows/request-routing.md`](workflows/request-routing.md) to choose the right agent or workflow.
4. Open [`agents/AGENT_INDEX.md`](agents/AGENT_INDEX.md) to find the specialist agents.
5. Use [`skills/SKILL_INDEX.md`](skills/SKILL_INDEX.md) to select reusable SEO capabilities.
6. Apply [`knowledge/seo-quality-gates.md`](knowledge/seo-quality-gates.md) before accepting any recommendation.
7. Return structured outputs using [`schemas/agent-output.schema.json`](schemas/agent-output.schema.json) or the closest file in [`templates/`](templates/).
8. For multi-agent work, use [`orchestration/README.md`](orchestration/README.md) and [`orchestration/session-state.schema.json`](orchestration/session-state.schema.json).
9. For executable routing or integration work, use [`main.py`](main.py), [`runtime/`](runtime/), and [`adapters/`](adapters/).

## Agent Roster

| Agent | Primary Role |
| --- | --- |
| SEO Technical Agent | Crawlability, indexation, rendering, schema, canonicals, robots, sitemaps, Core Web Vitals |
| SEO Copywriter/Content Agent | Content briefs, metadata, E-E-A-T, information gain, refreshes, intent matching |
| SEO Information Architecture Agent | Taxonomy, URL structures, internal links, topic clusters, crawl depth |
| SEO Accessibility Agent | WCAG-oriented checks, headings, alt text, labels, keyboard access, screen reader usability |
| SEO CRO Agent | Organic landing page conversion, CTA-intent fit, funnel friction, testing ideas |
| Local SEO Agent | GBP, NAP, citations, reviews, local landing pages, local pack visibility |
| Senior SEO Strategist Agent | Roadmaps, prioritization, business alignment, KPI planning |
| Senior SEO Engineer Agent | Code-level SEO implementation, tests, templates, deployment readiness |
| SEO Scrummaster Agent | Agent coordination, challenge loops, sprint planning, risk gates |
| SEO Full Audit/Analyst Agent | Full audits, health scoring, analytics synthesis, reporting |
| SEO Output Report Agent | Plain-language reports of findings, completed work, recommendations, and next steps for non-technical stakeholders |
| SEO Diagnostic Infrastructure Agent | Budget-aware diagnostic stack setup, audit tooling, dashboards, grading models, and monitoring infrastructure |
| GEO / AIO Optimization Agent | AI Overviews, generative search visibility, entity clarity, passage citability |
| Visual & Video Search Agent | Image SEO, video SEO, transcripts, media schema, visual search readiness |
| Voice Search & Conversational Agent | Spoken queries, Q&A structures, conversational answer formats |
| SEO Compliance & Legal Agent | Spam policies, disclosures, privacy, claims, regulated content escalation |
| Negative SEO & Security Agent | Toxic links, hacked pages, malware, scraping, spam attacks |
| International & Multilingual SEO Agent | Hreflang, localization, regional targeting, multilingual site architecture |
| Digital PR & Programmatic Link Outreach Agent | Linkable assets, unlinked mentions, backlink gaps, outreach strategy |
| Predictive SEO Trend Agent | Trend forecasting, seasonality, emerging search demand |
| Competitive Intelligence Agent | Competitor gaps, new pages, SERP movement, backlink patterns, AI citations |
| SEO Research and Development Agent | Controlled SEO experiments, hypotheses, test design, results interpretation |
| SEO Knowledge Graph Sync Agent | Entities, sameAs, schema consistency, brand SERP, knowledge graph readiness |
| AI Principal SEO Scientist | Search change monitoring, rule updates, knowledge sync, system learning |
| SEO E-commerce Agent | Product/category SEO, Product/Offer/ProductGroup schema, faceted navigation, Google Shopping/Merchant eligibility, marketplace intelligence |

## Best Use Cases

- Full SEO audits
- Technical SEO implementation in codebases
- Content briefs and refresh plans
- GEO/AIO and AI citation readiness
- Local SEO and multi-location scaling
- International and hreflang audits
- SEO security and negative SEO monitoring
- Programmatic SEO governance
- E-commerce, product schema, and marketplace SEO
- Competitive intelligence
- SEO experiment design
- SEO sprint planning and issue prioritization
- Digital PR and authority-building workflows
- SEO knowledge-base maintenance

## How To Use It With Codex

Use [`Codex.md`](Codex.md) when working inside a coding-agent environment.

Codex is best for:

- Inspecting codebases
- Implementing metadata, schema, sitemaps, robots, redirects, and internal-link logic
- Creating SEO regression checks
- Fixing accessibility and performance issues
- Running validation and tests

Recommended flow:

1. Read `Codex.md`.
2. Route the task.
3. Load the relevant agent and skill files.
4. Make the smallest safe code change.
5. Verify the rendered result, tests, schema, crawl signals, or performance signal as appropriate.

## How To Use It With ChatGPT

Use [`ChatGPT.md`](ChatGPT.md) for conversation-first analysis, planning, drafting, and review.

ChatGPT is best for:

- SEO strategy synthesis
- Content briefs
- Public-facing copy cleanup with `anti-ai-public-writing`
- Agent debate simulation
- Competitive analysis summaries
- Local and international SEO planning
- Compliance review checklists
- Experiment design
- Executive reporting

Recommended flow:

1. Read `ChatGPT.md`.
2. Route the request.
3. Ask for missing first-party evidence when needed.
4. Produce a structured recommendation with assumptions and risks clearly labeled.

## Other Model Control Files

- [`Claude.md`](Claude.md): conversation-first Claude strategy, review, and orchestration.
- [`Claudecode.md`](Claudecode.md): Claude Code technical SEO implementation in codebases.
- [`Replit.md`](Replit.md): SEO-ready app building, previewing, and rapid implementation.
- [`Manus.md`](Manus.md): autonomous multi-step SEO project coordination and execution.

## Workflows

- [`request-routing.md`](workflows/request-routing.md): choose the right lead and support agents.
- [`full-audit-workflow.md`](workflows/full-audit-workflow.md): run a complete SEO audit.
- [`content-production-workflow.md`](workflows/content-production-workflow.md): produce search-ready, user-first content.
- [`technical-deployment-workflow.md`](workflows/technical-deployment-workflow.md): safely ship SEO code changes.
- [`continuous-learning-workflow.md`](workflows/continuous-learning-workflow.md): keep the system current.
- [`monitoring-workflow.md`](workflows/monitoring-workflow.md): monitor drift, anomalies, security issues, and competitor movement.
- [`system-improvement-loop.md`](workflows/system-improvement-loop.md): improve the agent system itself.

## Knowledge and Governance

- [`knowledge/seo-quality-gates.md`](knowledge/seo-quality-gates.md): required acceptance gates.
- [`knowledge/knowledge-sources.md`](knowledge/knowledge-sources.md): source hierarchy and trusted references.
- [`knowledge/anti-patterns.md`](knowledge/anti-patterns.md): tactics the system must reject.
- [`knowledge/scoring-model.md`](knowledge/scoring-model.md): default scoring model for audits.

## Public-Facing Writing Rule

Any text a website or app visitor can read should pass [`skills/public-facing-writing-skills.md`](skills/public-facing-writing-skills.md). Use `anti-ai-public-writing` for page copy, headings, metadata, buttons, form text, alt text, captions, transcripts, local pages, product/service copy, blog content, error messages and onboarding text.

## Output Schemas

- [`schemas/agent-output.schema.json`](schemas/agent-output.schema.json): standard agent response.
- [`schemas/handoff-payload.schema.json`](schemas/handoff-payload.schema.json): agent-to-agent handoff contract.
- [`schemas/decision-record.schema.json`](schemas/decision-record.schema.json): Scrummaster decision record.
- [`schemas/rule-update.schema.json`](schemas/rule-update.schema.json): knowledge-base rule update.

## Examples

See [`examples/`](examples/) for worked sample outputs:

- Full audit example
- Content brief example
- Technical deployment example
- Plain-language SEO report example
- Diagnostic infrastructure example
- Anonymized production-style example with crawl, GSC, and GA4-style inputs

## Validation

Run repository validation locally with:

```powershell
./scripts/validate-repository.ps1
```

Run semantic schema validation and tests with:

```powershell
python -m pip install -r requirements-dev.txt
python scripts/validate_schema_examples.py
pytest -q
```

The GitHub Actions workflow in [`.github/workflows/validate.yml`](.github/workflows/validate.yml) validates JSON, internal markdown links, agent skill references, template references, schema conformance for example outputs, runtime routing, adapter behavior, and semantic repository contracts.

## Runtime and Adapters

The executable layer is intentionally lightweight and model-agnostic. [`runtime/`](runtime/) provides session state, request routing, async execution, memory, tool dispatch and LLM clients. [`adapters/`](adapters/) provides normalized contracts for crawl exports, server logs, PageSpeed/Lighthouse payloads, schema validation, rank tracking, backlinks, GSC exports, and GA4 exports. Live API credentials are not stored in the repository; adapters are designed so teams can plug in authenticated fetchers while still testing with safe local exports.

Adapter implementation details live in [`adapters/README.md`](adapters/README.md). Recommended tools to connect are listed in [`adapters/TOOLS.md`](adapters/TOOLS.md). A safe OAuth2 Google Search Console pattern is provided in [`adapters/gsc_live_example.py`](adapters/gsc_live_example.py). A live key-only PageSpeed Insights and CrUX adapter with SSRF-safe URL validation is provided in [`adapters/google_pagespeed_live.py`](adapters/google_pagespeed_live.py), and a persistent cross-session drift store in [`adapters/evidence_store.py`](adapters/evidence_store.py).

Dry-run routing:

```powershell
python main.py "Run a full SEO audit" --domain https://example.com
```

Dry-run execution with the built-in echo client:

```powershell
python main.py "Run a full SEO audit" --domain https://example.com --execute
```

Optional live execution:

```powershell
$env:OPENAI_API_KEY="..."
python main.py "Run a full SEO audit" --domain https://example.com --execute --llm-provider openai
```

See [`.env.example`](.env.example) for optional provider settings. Do not commit real API keys.

Tool dispatch before execution:

```powershell
python main.py "Run a technical crawl audit" --execute --tool crawler_csv=examples/anonymized-production-style-example/inputs/crawl.csv
```

## Templates

The [`templates/`](templates/) folder includes practical starting points for:

- SEO audits
- Content briefs
- Technical SEO tickets
- SEO roadmaps
- Decision records
- GEO/AIO reports
- SEO experiments
- Knowledge updates
- Outreach campaigns
- Engineering change plans

## Non-Negotiables

- Do not recommend manipulative link schemes.
- Do not create doorway pages, fake locations, fake reviews, or scaled low-value pages.
- Do not hide text or create content that differs materially for bots and users.
- Do not auto-apply indexation, canonical, redirect, robots, disavow, or legal/compliance changes without explicit approval.
- Do not claim certainty when evidence is incomplete.
- Do not treat industry speculation as official search guidance.

## Contribution Standard

Every contribution must improve SEO capability, operating clarity, evidence quality, safety, or implementation usefulness. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT. See [`LICENSE`](LICENSE).
