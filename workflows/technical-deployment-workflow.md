# Technical Deployment Workflow

1. SEO Technical Agent documents issue with evidence.
2. SEO Scrummaster Agent verifies priority and risk.
3. Senior SEO Engineer Agent designs smallest safe implementation.
4. SEO Accessibility Agent reviews UI-impacting changes.
5. SEO Compliance & Legal Agent reviews regulated or policy-sensitive changes.
6. Senior SEO Engineer Agent implements patch.
7. SEO Technical Agent validates output.
8. SEO Full Audit/Analyst Agent monitors drift after release.

## Required Verification

- Tests pass where applicable
- Rendered output checked
- Indexation/canonical/robots behavior checked if affected
- Structured data checked if affected
- Core Web Vitals checked if affected
- Rollback path documented

## Decision Tree

```mermaid
flowchart TD
  A["Technical SEO issue"] --> B["SEO Technical Agent creates evidence-backed ticket"]
  B --> C{"Risk level?"}
  C -->|Critical or High| D["SEO Scrummaster Agent approval gate"]
  C -->|Medium or Low| E["Senior SEO Engineer Agent implementation plan"]
  D --> E
  E --> F{"Approval needed?"}
  F -->|Yes| G["Pause for approval"]
  F -->|No| H["Implement scoped change"]
  G --> H
  H --> I["Run verification"]
  I --> J{"Verification passed?"}
  J -->|Yes| K["Monitor drift"]
  J -->|No| L["Rollback or revise"]
  L --> I
```

## Failure Handling

- If the app cannot run, produce a manual verification plan.
- If rendered output cannot be checked, do not claim implementation verified.
- If validation fails, rollback or keep change unmerged.
