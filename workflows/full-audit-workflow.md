# Full Audit Workflow

1. Define target domain, business model, market, competitors, and goals.
2. SEO Diagnostic Infrastructure Agent checks whether the diagnostic stack and data access are sufficient.
3. Gather first-party data if available.
4. Crawl site and collect technical evidence.
5. Run SEO Technical Agent.
6. Run SEO Copywriter/Content Agent.
7. Run SEO Information Architecture Agent.
8. Run SEO Accessibility Agent.
9. Run SEO CRO Agent.
10. Run GEO / AIO Optimization Agent.
11. Run Local SEO Agent or International & Multilingual SEO Agent when applicable.
12. Run Negative SEO & Security Agent.
13. Run Competitive Intelligence Agent.
14. SEO Full Audit/Analyst Agent normalizes scores and writes the audit.
15. SEO Scrummaster Agent challenges high-impact findings.
16. Senior SEO Strategist Agent converts accepted findings into a roadmap.
17. SEO Output Report Agent creates a plain-language stakeholder report.

## Definition of Done

- Audit report complete
- Missing data disclosed
- Issues prioritized
- Owners assigned
- Risk levels assigned
- Verification methods defined
- Roadmap ready

## Decision Tree

```mermaid
flowchart TD
  A["Full audit request"] --> B["Collect business context"]
  B --> C{"First-party data available?"}
  C -->|Yes| D["Use first-party data as Tier 1 evidence"]
  C -->|No| E["Mark missing data and lower confidence"]
  D --> F["Run crawl and technical evidence collection"]
  E --> F
  F --> G["Run specialist agents"]
  G --> H{"Critical risk found?"}
  H -->|Yes| I["SEO Scrummaster Agent challenge"]
  H -->|No| J["Normalize scores"]
  I --> J
  J --> K{"Implementation needed?"}
  K -->|Yes| L["Create handoff to Senior SEO Engineer Agent"]
  K -->|No| M["Create roadmap"]
  L --> M
  M --> N["SEO Output Report Agent creates plain-language report"]
  N --> O["Publish audit report and stakeholder summary"]
```

## Failure Handling

- If crawl data is incomplete, scope findings to sampled URLs and request a complete crawl.
- If analytics are missing, separate technical findings from performance claims.
- If agents disagree, create a decision record before scoring.
