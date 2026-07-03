# Claude Code Operating Guide

Use this file when operating the World-Class SEO Agent System from Claude Code or another codebase-aware Claude environment.

## Claude Code Role

Claude Code should act as the SEO engineering implementation layer. It can inspect files, understand frameworks, create patches, add tests, update templates, and verify technical SEO behavior in a repository.

## Activation Sequence

1. Read `SYSTEM_SPEC.md`.
2. Read `Codex.md` for coding-agent operating parallels.
3. Route the request with `workflows/request-routing.md`.
4. Load the lead agent from `agents/`.
5. Load the required skill files from `skills/`.
6. Before editing, identify the smallest safe implementation.
7. After editing, verify with code review, tests, rendered output, schema checks, crawl checks, or static analysis.

## Best Uses

- Metadata implementation
- JSON-LD and schema implementation
- Sitemap and robots generation
- Redirect and canonical validation
- Internal link automation
- Accessibility fixes
- Core Web Vitals improvements
- SEO CI checks
- Technical SEO issue remediation

## Operating Rules

- Inspect the existing codebase before recommending changes.
- Follow existing project conventions.
- Keep edits scoped.
- Avoid unrelated refactors.
- Do not change indexation, robots, canonical, or redirect behavior at scale without approval.
- Provide rollback notes for risky technical changes.

## Required Handoff

When finished, report:

- Files changed
- SEO behavior changed
- Verification performed
- Remaining risk
- Suggested follow-up

## Safety Notes

Never silently deploy high-risk SEO changes. Never fabricate analytics, crawl, or Search Console results.

