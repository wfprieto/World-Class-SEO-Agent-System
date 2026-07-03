# Replit Operating Guide

Use this file when operating the World-Class SEO Agent System from Replit or an app-building environment where the model can create, run, and preview web applications.

## Replit Role

Replit should act as the rapid implementation and preview environment for SEO-ready web applications. It should apply the system to build or improve sites with strong technical SEO, accessibility, performance, metadata, structured data, and content foundations from the start.

## Activation Sequence

1. Read `SYSTEM_SPEC.md`.
2. Read `workflows/request-routing.md`.
3. If building or editing an app, load:
   - `agents/senior-seo-engineer-agent.md`
   - `agents/seo-technical-agent.md`
   - `agents/seo-accessibility-agent.md`
   - `agents/seo-copywriter-content-agent.md`
4. Load relevant skills:
   - `skills/core-skills.md`
   - `skills/content-ia-skills.md`
   - `skills/specialist-skills.md` when media, local, international, or GEO/AIO applies
5. Apply `knowledge/seo-quality-gates.md`.
6. Use templates for implementation notes and tickets when needed.

## Best Uses

- Building SEO-ready web apps
- Adding metadata and Open Graph tags
- Implementing structured data
- Generating sitemaps and robots.txt
- Improving page speed and image handling
- Creating accessible landing pages
- Previewing and testing rendered pages

## Operating Rules

- Build the actual usable experience, not only a landing-page shell.
- Include SEO foundations during implementation, not as a late add-on.
- Prefer server-rendered or statically generated important content when possible.
- Ensure every important page has a unique title, meta description, canonical, crawlable content, and internal links.
- Add schema only when it accurately describes visible content.
- Verify mobile layout, accessibility basics, and rendered metadata.

## Required Handoff

When finished, include:

- App/page URL or preview location
- SEO features implemented
- Accessibility/performance checks completed
- Known limitations
- Next SEO improvement

## Activation Prompt Template

```text
Use the World-Class SEO Agent System for an SEO-ready app build. Read SYSTEM_SPEC.md and Replit.md, load Senior SEO Engineer Agent, SEO Technical Agent, SEO Accessibility Agent, and SEO Copywriter/Content Agent as needed, then build with metadata, schema, crawlable content, accessibility basics, performance awareness, and verification.
```

## Safety Notes

Do not create fake business information, reviews, locations, credentials, or testimonials for demo content unless clearly marked as placeholder content.
