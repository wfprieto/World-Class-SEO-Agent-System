# Architecture

The product is a model-agnostic, evidence-governed SEO operating system. Its primary layer is documentation-first knowledge, skills, evidence, and orchestration contracts; its executable layer is a bounded CLI runtime with optional integration adapters. The primary operator is a technical SEO practitioner or SEO engineer accountable for an authorized audit and implementation handoff.

```text
Request
  -> router and business-profile resolver
  -> bounded workflow DAG
  -> capability registry
  -> agents + canonical skills + references
  -> ToolDispatcher
  -> normalized AdapterResult evidence
  -> evidence binding and finding normalization
  -> Scrummaster decisions
  -> strategy and report synthesis
```

## Canonical authorities

- Product category, operator, flagship, outcome, and proof boundaries: `governance/product-contract.json`
- Agent capabilities: `orchestration/capability-registry.json`
- Operator commands: `seoctl/command-registry.json`
- Skills: `skills/skill-catalog.json`
- Priority packages: `skills/package-registry.json`
- Evidence persistence: `adapters/evidence_store.py`
- URL safety: `adapters/url_safety.py`
- Optional providers: `adapters/mcp_extensions.py`
- Comparative scoring: `evaluation/comparative/`

No integration may bypass `ToolDispatcher`, evidence validation, run budgets, or approval gates. Optional provider packs are adapters, not forks of the core.

## Flagship boundary

`seoctl audit technical` (`audit.technical`) is the sole flagship command. It performs bounded read-only diagnosis and produces the ten-artifact decision-ready technical SEO evidence package defined by the product contract. Fixture execution proves deterministic contract behavior only; bounded live execution reports authorized observations at a stated time. Neither proves complete site coverage or search-engine, ranking, traffic, conversion, production-readiness, or comparative outcomes.

`system.run` and `full-site-audit` are evidence-dependent multi-agent orchestration capabilities. They must disclose missing evidence and unexecuted domains and must not be presented as alternate flagship paths or completeness guarantees.
