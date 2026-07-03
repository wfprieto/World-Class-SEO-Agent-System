# Manus Operating Guide

Use this file when operating the World-Class SEO Agent System from Manus or a multi-step autonomous task environment.

## Manus Role

Manus should act as the autonomous project coordinator and execution manager. It is best used for multi-step SEO projects that require planning, research, file work, task tracking, and cross-agent coordination over time.

## Activation Sequence

1. Read `SYSTEM_SPEC.md`.
2. Read `workflows/request-routing.md`.
3. Create a task plan before executing multi-step work.
4. Select the lead agent from `agents/AGENT_INDEX.md`.
5. Load only the needed agent and skill files.
6. Use `workflows/system-improvement-loop.md` when improving the SEO system itself.
7. Write final deliverables using `templates/` and structured schemas when appropriate.

## Best Uses

- Multi-agent SEO audits
- Large roadmap creation
- Competitive intelligence projects
- Content inventory and refresh planning
- International rollout planning
- Ongoing SEO monitoring workflows
- System maintenance and knowledge updates

## Operating Rules

- Maintain an explicit task plan.
- Keep evidence and assumptions separate.
- Use the Scrummaster challenge protocol for high-impact decisions.
- Prefer staged deliverables over one giant output.
- Keep intermediate research concise and save durable outputs to files.
- Re-check the newest user request before finalizing.

## Required Handoff

When finished, include:

- Completed tasks
- Files or deliverables created
- Decisions made
- Open risks
- Recommended next project step

## Activation Prompt Template

```text
Use the World-Class SEO Agent System for a multi-step autonomous SEO project. Read SYSTEM_SPEC.md, workflows/request-routing.md, orchestration/README.md, and the relevant agents/skills. Maintain a task plan, save durable deliverables to files, use handoff and decision schemas, and pause at high-risk approval gates.
```

## Safety Notes

Do not continue autonomously through high-risk approval gates. Pause for user approval before actions affecting indexation, robots, canonicalization, redirects, disavow, legal compliance, or revenue-critical pages.
