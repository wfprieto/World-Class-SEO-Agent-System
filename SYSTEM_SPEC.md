# System Specification

## Mission

Create the most effective model-agnostic SEO agent system for senior SEO engineering teams. The system must improve organic visibility, qualified traffic, conversion quality, brand/entity trust, AI search visibility, accessibility, compliance, and long-term site resilience.

## Design Philosophy

The system uses specialist agents because world-class SEO requires different forms of expertise. Technical SEO, content strategy, accessibility, CRO, local SEO, international SEO, digital PR, and SEO engineering are connected, but they are not the same job.

The system uses shared skills because specialist agents should not duplicate work. A crawl, schema audit, content brief, hreflang validation, or backlink review should produce one reliable artifact that other agents can reuse.

The system uses governance because SEO changes can break revenue, compliance, crawlability, and user trust if they are deployed casually.

## Evidence Hierarchy

1. First-party performance data: Google Search Console, Bing Webmaster Tools, analytics, server logs, CRM, conversion data, rank tracking, CMS exports.
2. Direct technical evidence: raw HTML, rendered DOM, HTTP headers, robots.txt, XML sitemaps, structured data, screenshots, accessibility tree, codebase inspection.
3. Search evidence: live SERPs, AI Overviews, AI citation snapshots, local packs, image/video SERPs, competitor SERP movements.
4. Authority evidence: backlink data, citation data, brand mentions, digital PR coverage, entity databases, review platforms.
5. Official standards: search engine documentation, structured data standards, accessibility standards, privacy/compliance requirements.
6. Industry research and experiments: useful for hypotheses, not sufficient for final rules.

## Standard Agent Output

Every agent output must include:

- Summary
- Evidence used
- Confidence level
- Findings
- Recommended actions
- Impact
- Effort
- Risk
- Owner
- Dependencies
- Acceptance criteria
- Verification method
- Follow-up date or trigger

## Plain-Language Reporting Standard

Any completed audit, implementation, sprint, or multi-agent workflow should be eligible for translation by the SEO Output Report Agent into a non-technical stakeholder report.

The plain-language report must clearly separate:

- What was reviewed
- What was fixed or changed
- What was created or added
- What was recommended but not yet done
- Why each item matters
- What benefit is expected
- What still needs to be checked
- What the next step is

The report must avoid jargon, avoid guaranteed ranking claims, and explain missing evidence in simple language.

## Public-Facing Writing Standard

Any text a website or app visitor can read must pass `anti-ai-public-writing` before publication. This includes page copy, headings, metadata, navigation labels, button text, form helper text, alt text, captions, transcripts, local landing page copy, product/service copy, blog content, error messages and onboarding text.

The writing must be clear, direct, useful, specific and natural when read out loud. It must avoid obvious AI phrasing, generic SEO filler, fake polish, hype, stiff corporate wording, em dashes, unsupported claims and keyword stuffing.

If proof is missing, write the safer version and mark the missing proof. If the copy includes legal, medical, financial, privacy, pricing, guarantee or regulated claims, route it to the SEO Compliance & Legal Agent before publication.

## Diagnostic Infrastructure Standard

SEO audits and monitoring are only as reliable as the diagnostic setup behind them. When a project requires tool selection, reporting infrastructure, audit systems, dashboards, grading tools, or recurring monitoring, use the SEO Diagnostic Infrastructure Agent.

The diagnostic setup must:

- Ask budget and context questions before recommending paid tools.
- Ask what type of website or app is being built or audited, including CMS/framework and code/deployment access.
- Include a free baseline wherever possible.
- Recommend paid tools only when justified by site size, business needs, reporting needs, or operational complexity.
- Identify who owns each tool or data source.
- Define setup effort, data quality checks, alert thresholds, and reporting cadence.
- Avoid overlapping paid tools unless each tool has a distinct role.

## Runtime and Adapter Standard

The system must be usable as both a documentation-first operating system and an executable integration layer.

The runtime layer must:

- Route requests to the correct lead and support agents.
- Create session state with business context, evidence inventory, decisions, risks, and outputs.
- Execute routed workflows through a pluggable LLM client when requested.
- Support async execution, streaming output, memory and adapter/tool dispatch.
- Keep orchestration model-agnostic so Codex, ChatGPT, Claude, Replit, Manus, or another runtime can use the same contracts.
- Preserve human approval gates for high-risk SEO actions.

The adapter layer must:

- Normalize first-party and diagnostic data into predictable outputs.
- Support local exports for safe testing and credential-free operation.
- Keep live API credentials outside the repository.
- Distinguish unavailable data from clean data.
- Return warnings when fields are missing, stale, sampled, or incomplete.

Required adapter categories include GSC, GA4, crawler exports, server logs, Lighthouse/PageSpeed payloads, schema validation, rank tracking, and backlink data.

## Risk Classes

Critical:

- Sitewide indexation, crawling, canonical, redirect, security, legal, or revenue-impacting risks.

High:

- Important template-level SEO issues, major content quality issues, serious accessibility blockers, local visibility defects, international targeting conflicts.

Medium:

- Page group issues, content gaps, schema enhancements, metadata improvements, internal link improvements, performance refinements.

Low:

- Nice-to-have enhancements, formatting cleanup, supporting optimizations, monitoring improvements.

## Approval Gates

Human approval is required before:

- Sitewide robots.txt changes
- Mass noindex changes
- Canonical rules affecting many URLs
- Redirect migrations
- Disavow submissions
- Large programmatic page creation
- Legal/compliance-sensitive publication
- Medical, legal, financial, or regulated content publication
- Changes to checkout, lead forms, pricing pages, or revenue-critical funnels

## Operating Modes

Audit Mode:

- Diagnose, score, and prioritize.

Implementation Mode:

- Make safe, scoped code or content changes with validation.

Strategy Mode:

- Build roadmap, budgets, owners, and sequencing.

Monitoring Mode:

- Detect drift, ranking movement, indexation changes, security issues, content decay, and competitor movement.

Research Mode:

- Explore new algorithm changes, tactics, tests, and knowledge updates.

Debate Mode:

- Scrummaster forces agents to defend assumptions before important decisions.

## System Success Metrics

- Indexed valuable URLs
- Reduced technical defects
- Improved crawl efficiency
- Improved Core Web Vitals where relevant, explicitly including LCP, INP, and CLS
- More qualified organic clicks
- Higher conversion rate from organic traffic
- Higher content quality and information gain
- Better local pack visibility
- Better international targeting accuracy
- Improved AI citation and brand mention visibility
- Reduced security, spam, and compliance risk
- Faster SEO engineering throughput
