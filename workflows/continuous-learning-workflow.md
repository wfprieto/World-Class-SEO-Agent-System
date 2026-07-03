# Continuous Learning Workflow

1. AI Principal SEO Scientist monitors official search, structured data, accessibility, and policy sources.
2. SEO Research and Development Agent tests or validates uncertain tactics.
3. SEO Full Audit/Analyst Agent reports performance anomalies.
4. SEO Scrummaster Agent reviews proposed rule changes.
5. SEO Knowledge Graph Sync Agent updates entity and source-of-truth data where relevant.
6. Accepted updates are written using `schemas/rule-update.schema.json`.
7. Agents adopt new rule only after versioned approval.

## Decision Tree

```mermaid
flowchart TD
  A["New source, anomaly, or experiment result"] --> B{"Source type?"}
  B -->|Official guidance| C["AI Principal SEO Scientist drafts rule update"]
  B -->|First-party anomaly| D["SEO Full Audit/Analyst Agent validates pattern"]
  B -->|Experiment result| E["SEO Research and Development Agent evaluates result quality"]
  B -->|Industry hypothesis| F["Mark as hypothesis, not rule"]
  C --> G{"Operational impact?"}
  D --> G
  E --> G
  F --> H["Add to watchlist or experiment backlog"]
  G -->|High or system-wide| I["SEO Scrummaster Agent review"]
  G -->|Low and clear| J["Draft low-risk knowledge update"]
  I --> K{"Approved?"}
  J --> K
  K -->|Yes| L["Write rule update using schemas/rule-update.schema.json"]
  K -->|Revise| M["Return to originating agent"]
  K -->|Reject| H
  L --> N["Notify affected agents and define validation check"]
  M --> G
```

## Source Confidence

High:

- Official documentation
- First-party data
- Controlled internal experiment with adequate evidence

Medium:

- Repeated field observations
- Multiple independent credible tests

Low:

- Industry commentary
- Anecdotal reports
- One-off examples
