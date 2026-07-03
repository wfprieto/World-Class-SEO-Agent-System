# System Map

This is the fast navigation file for humans and LLMs. Start here when you need to understand how the repository fits together.

## Fast Start

1. Read `SYSTEM_SPEC.md` for rules, evidence standards, approval gates and output expectations.
2. Use `workflows/request-routing.md` or `runtime/routing.py` to choose the lead agent.
3. Open the lead agent in `agents/`.
4. Load the agent's primary skills from `skills/SKILL_INDEX.md`.
5. Use `skills/deep-skill-procedures.md` for the step-by-step procedure.
6. Pull evidence through `adapters/` or supplied exports.
7. Return output with the right file from `schemas/` or `templates/`.
8. Validate with `scripts/validate-repository.ps1`, `scripts/validate_schema_examples.py` and `pytest`.

## Directory Roles

| Directory | Purpose | Start File |
| --- | --- | --- |
| `agents/` | Specialist SEO roles and responsibilities | `agents/AGENT_INDEX.md` |
| `skills/` | Reusable SEO procedures called by agents | `skills/SKILL_INDEX.md` |
| `workflows/` | Multi-agent flows and routing logic | `workflows/request-routing.md` |
| `knowledge/` | Quality gates, evidence rules, anti-patterns and scoring | `knowledge/seo-quality-gates.md` |
| `schemas/` | Machine-valid output contracts | `schemas/agent-output.schema.json` |
| `templates/` | Human-readable report and work artifacts | `templates/audit-report.md` |
| `adapters/` | Tool/export connectors and live adapter examples | `adapters/README.md` |
| `runtime/` | Executable routing, LLM execution, memory and tool dispatch | `runtime/orchestrator.py` |
| `orchestration/` | Session state and handoff rules | `orchestration/README.md` |
| `examples/` | Valid examples, sample exports and schema fixtures | `examples/README.md` |
| `tests/` | Semantic and runtime test coverage | `tests/test_repository_semantics.py` |

## Agent Lookup

| Need | Lead Agent | File |
| --- | --- | --- |
| Full audit, scorecard, analytics synthesis | SEO Full Audit/Analyst Agent | `agents/seo-full-audit-analyst-agent.md` |
| Crawlability, rendering, indexation, schema, canonicals, robots, sitemaps | SEO Technical Agent | `agents/seo-technical-agent.md` |
| Code-level fixes and regression tests | Senior SEO Engineer Agent | `agents/senior-seo-engineer-agent.md` |
| Content briefs, copy, metadata, refreshes | SEO Copywriter/Content Agent | `agents/seo-copywriter-content-agent.md` |
| URL taxonomy, navigation, internal links | SEO Information Architecture Agent | `agents/seo-information-architecture-agent.md` |
| WCAG, headings, alt text, accessible UX | SEO Accessibility Agent | `agents/seo-accessibility-agent.md` |
| Organic landing page conversion and testing | SEO CRO Agent | `agents/seo-cro-agent.md` |
| GBP, local listings, citations, reviews | Local SEO Agent | `agents/local-seo-agent.md` |
| Strategy, priorities, roadmap, sequencing | Senior SEO Strategist Agent | `agents/senior-seo-strategist-agent.md` |
| Coordination, debate, sprint planning, decisions | SEO Scrummaster Agent | `agents/seo-scrummaster-agent.md` |
| Plain-language stakeholder reporting | SEO Output Report Agent | `agents/seo-output-report-agent.md` |
| Budget-aware tool stack, dashboards, monitoring setup | SEO Diagnostic Infrastructure Agent | `agents/seo-diagnostic-infrastructure-agent.md` |
| AI Overviews, AI citations, entity clarity | GEO / AIO Optimization Agent | `agents/geo-aio-optimization-agent.md` |
| Image, video, YouTube, transcripts, media schema | Visual & Video Search Agent | `agents/visual-video-search-agent.md` |
| Spoken queries and conversational Q&A | Voice Search & Conversational Agent | `agents/voice-search-conversational-agent.md` |
| Legal, compliance, claims, policies, disclosures | SEO Compliance & Legal Agent | `agents/seo-compliance-legal-agent.md` |
| Hacked pages, spam attacks, toxic links, malware | Negative SEO & Security Agent | `agents/negative-seo-security-agent.md` |
| Hreflang, localization, multilingual architecture | International & Multilingual SEO Agent | `agents/international-multilingual-seo-agent.md` |
| Digital PR, outreach, unlinked mentions, linkable assets | Digital PR & Programmatic Link Outreach Agent | `agents/digital-pr-programmatic-link-outreach-agent.md` |
| Trend forecasting and seasonality | Predictive SEO Trend Agent | `agents/predictive-seo-trend-agent.md` |
| Competitor gaps, SERP movement, backlinks, AI citations | Competitive Intelligence Agent | `agents/competitive-intelligence-agent.md` |
| SEO experiments and research design | SEO Research and Development Agent | `agents/seo-research-and-development-agent.md` |
| Entities, sameAs, brand SERP, knowledge graph consistency | SEO Knowledge Graph Sync Agent | `agents/seo-knowledge-graph-sync-agent.md` |
| Search changes, knowledge sync, rule updates | AI Principal SEO Scientist | `agents/ai-principal-seo-scientist.md` |

## Skill Lookup

Use `skills/SKILL_INDEX.md` to find the skill name, then use `skills/deep-skill-procedures.md` for the execution procedure. Skill definitions live in:

- `skills/core-skills.md`
- `skills/content-ia-skills.md`
- `skills/specialist-skills.md`
- `skills/strategy-governance-skills.md`
- `skills/missing-skills.md`
- `skills/public-facing-writing-skills.md`

Every indexed skill must have a matching deep procedure. This is enforced by tests.

## Runtime Lookup

| Runtime Need | File |
| --- | --- |
| CLI entrypoint | `main.py` |
| Orchestrator facade | `runtime/orchestrator.py` |
| Request router | `runtime/routing.py` |
| LLM clients | `runtime/llm.py` |
| Tool dispatch | `runtime/tools.py` |
| Memory | `runtime/memory.py` |
| Session state | `runtime/state.py` |

## Adapter Lookup

Read `adapters/README.md` before adding or using adapters. Use `adapters/TOOLS.md` to decide which SEO tools should be connected. All runtime-callable adapters are registered in `adapters/registry.py`.

## Output Lookup

Use schemas for machine-readable outputs:

- `schemas/agent-output.schema.json`
- `schemas/handoff-payload.schema.json`
- `schemas/decision-record.schema.json`
- `schemas/rule-update.schema.json`

Use templates for stakeholder-readable outputs in `templates/`.

## Validation

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate-repository.ps1
python scripts\validate_schema_examples.py
python -m pytest -q
```

If these pass, the repository links, schemas, agent references, runtime routing, adapters and semantic checks are working together.
