# Legacy Checklist Triage Reference Pack

- Owner: SEO Research and Development Agent
- Last verified: 2026-07-12
- Freshness class: quarterly
- Evidence posture: checklist items are candidates until reconciled with current primary sources, runtime evidence, or a controlled test.

## Primary sources

- https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- https://developers.google.com/search/docs/essentials/spam-policies
- https://www.w3.org/WAI/standards-guidelines/wcag/

<a id="checklist-status-taxonomy"></a>
## Checklist status taxonomy

Classify every imported checklist idea as `current`, `needs-primary-source-confirmation`, `dated`,
`deprecated`, `implementation-specific`, or `rejected`. Only `current` items with matching evidence
may become deterministic rules.

<a id="checklist-rule-promotion-gate"></a>
## Checklist rule promotion gate

A checklist item can become an enforced rule only when it has a current primary source or direct
runtime evidence, a fixture, expected findings, severity logic, and a rollback path if it proves too noisy.

<a id="checklist-advisory-use"></a>
## Checklist advisory use

Checklist items without enough evidence may still support training, audit prompts, and analyst review.
They must be labeled advisory and must not block releases or claim ranking impact.
