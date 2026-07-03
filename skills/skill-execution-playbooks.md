# Skill Execution Playbooks

Use this file to add procedural depth to the grouped skill definitions. When a grouped skill in `core-skills.md`, `content-ia-skills.md`, `specialist-skills.md`, or `strategy-governance-skills.md` is invoked, apply the matching playbook below in addition to the skill's purpose and quality gate.

## Universal Skill Execution Pattern

System prompt: Execute the skill as a senior SEO operator. Use evidence first, disclose missing data, avoid speculative certainty, and produce an output another agent can act on.

Execution steps:

1. Confirm the user goal and operating mode.
2. Identify required inputs and evidence.
3. Check whether evidence is available, missing, partial, or stale.
4. Execute the skill-specific analysis.
5. Produce structured findings and actions.
6. Apply quality gates.
7. Create handoffs if another agent must act.
8. Define verification and monitoring.

Failure conditions:

- Required evidence unavailable.
- Target URLs or business context unclear.
- Requested action violates anti-patterns or approval gates.
- Tool output conflicts with first-party data.

Fallback:

- Lower confidence, disclose limitations, and request the minimum missing evidence.

## Audit and Technical Discovery Skills

Use for:

- `full-site-audit`
- `technical-audit`
- `crawl-map`
- `indexation-reality-check`
- `sitemap-audit`
- `schema-detect-validate-generate`
- `core-web-vitals-triage`
- `seo-drift-monitor`

Execution steps:

1. Build a URL inventory and classify URLs by status, canonical, indexability, template, and value.
2. Compare intended search behavior against observed technical signals.
3. Check sitewide controls before page-level issues.
4. Separate crawl, render, index, performance, and structured data findings.
5. Prioritize template-level issues before one-off issues.
6. Create engineering-ready tickets for implementation work.

Output:

- Use `templates/audit-report.md` for audits or `templates/technical-seo-ticket.md` for implementation issues.

## Content and IA Skills

Use for:

- `content-brief`
- `content-audit`
- `content-decay`
- `keyword-cluster`
- `content-inventory`
- `sxo-page-fit`
- `internal-link-map`
- `metadata-generation`

Execution steps:

1. Identify search intent and page type before writing or restructuring.
2. Compare existing content against user need, SERP patterns, and business goals.
3. Define information gain and entity coverage.
4. Map content to site architecture and internal links.
5. Add metadata and citable passage requirements where relevant.
6. Escalate legal, medical, financial, privacy, or unsupported claims.

Output:

- Use `templates/content-brief.md`, `templates/content-refresh-plan.md`, `templates/metadata-set.md`, or `templates/ia-map.md`.

## Specialist Skills

Use for:

- Local, international, media, GEO/AIO, entity, backlink, security, compliance, and digital PR work.

Execution steps:

1. Confirm the specialist context: location, market, entity, media type, authority profile, or risk class.
2. Gather specialist evidence.
3. Apply relevant quality gates and anti-pattern checks.
4. Produce a prioritized specialist report.
5. Create handoffs for engineering, content, compliance, or strategy.

Output:

- Use the closest specialist template in `templates/`.

## Strategy and Governance Skills

Use for:

- `seo-roadmap`
- `prioritization-matrix`
- `scrummaster-debate`
- `experiment-design`
- `knowledge-sync`
- `compliance-review`
- `decision-record`
- `definition-of-done`

Execution steps:

1. Gather accepted findings and unresolved risks.
2. Rank work by impact, effort, risk, reversibility, and dependency.
3. Challenge high-impact or high-risk recommendations.
4. Convert decisions into owners, milestones, and verification.
5. Record durable decisions and knowledge updates.

Output:

- Use `templates/seo-roadmap.md`, `templates/decision-record.md`, `templates/seo-sprint-plan.md`, or `templates/knowledge-update.md`.

