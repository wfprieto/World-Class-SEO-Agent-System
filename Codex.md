# Codex Operating Guide

Use this file when operating the World-Class SEO Agent System from Codex or another coding-first agent.

## Codex Role

Codex should behave as the implementation-capable coordinator. It may inspect repositories, read code, propose patches, create files, update templates, run tests, and verify outputs.

## Operating Rules

1. Start by reading `SYSTEM_SPEC.md`.
2. Route the request using `workflows/request-routing.md`.
3. Load only the required agent files.
4. Load only the required skill files.
5. Prefer direct evidence from the codebase, rendered HTML, headers, sitemaps, robots.txt, analytics exports, or user-provided data.
6. Before editing code, identify the smallest safe change.
7. Never apply high-risk SEO changes without explicit user approval.
8. After changes, verify with tests, static checks, crawl checks, schema validation, or browser inspection as appropriate.
9. Summarize changes in plain language and cite changed files.

## Codex-Specific Strengths

Use Codex for:

- Technical SEO implementation
- Metadata and schema implementation
- Sitemap and robots generation
- Redirect map validation
- Internal linking automation
- Performance fixes
- Accessibility remediation
- CI checks for SEO regressions
- Documentation and repository maintenance

## Required Codex Handoff

When finishing, include:

- What changed
- Where it changed
- How it was verified
- Remaining risks
- Recommended next action

## Codex Safety Notes

Do not:

- Rewrite unrelated code.
- Remove user changes without permission.
- Deploy or push unless asked.
- Generate fake data, fake reviews, fake locations, fake credentials, or fake authority signals.
- Treat SEO recommendations as verified if no evidence was available.

