# Monitoring Workflow

Use this workflow for ongoing SEO drift, anomaly, risk, and opportunity monitoring.

## Decision Tree

```mermaid
flowchart TD
  A["Monitoring trigger"] --> B{"Trigger type?"}
  B -->|Traffic or ranking drop| C["SEO Full Audit/Analyst Agent"]
  B -->|Deployment detected| D["SEO Technical Agent"]
  B -->|Indexation change| E["SEO Technical Agent"]
  B -->|Security/manual action| F["Negative SEO & Security Agent"]
  B -->|Competitor movement| G["Competitive Intelligence Agent"]
  B -->|Search policy/update| H["AI Principal SEO Scientist"]
  C --> I{"Critical impact?"}
  D --> I
  E --> I
  F --> I
  G --> J["Create monitoring report"]
  H --> K["Draft knowledge update"]
  I -->|Yes| L["SEO Scrummaster Agent escalation"]
  I -->|No| J
  L --> M{"Implementation needed?"}
  M -->|Yes| N["Senior SEO Engineer Agent"]
  M -->|No| J
  N --> O["Verify and monitor"]
  J --> O
  K --> L
```

## Trigger Thresholds

Escalate to SEO Scrummaster Agent when:

- Organic clicks or conversions drop materially outside expected seasonality.
- Indexed valuable pages decline unexpectedly.
- A deployment changes canonical, robots, redirects, sitemap, or schema behavior.
- Manual action, security warning, or hacked content is detected.
- Competitor movement affects a priority topic cluster.
- Official search guidance changes an operating rule.

## Required Output

- Trigger
- Evidence
- Affected pages or markets
- Severity
- Likely cause
- Owner
- Next action
- Verification date

