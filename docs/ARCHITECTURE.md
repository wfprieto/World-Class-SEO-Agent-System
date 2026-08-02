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
- Dependency direction and direct-network boundaries: `governance/architecture-contract.json`
- Complexity, annotation, lint, and coverage ceilings: `governance/code-quality-ratchet.json`

No integration may bypass `ToolDispatcher`, evidence validation, run budgets, or approval gates. Optional provider packs are adapters, not forks of the core.

## Dependency direction

`seoctl` is the outer composition layer and may assemble runtime, adapter, and integration components. All other cross-layer imports fail unless the architecture contract names the exact source module, exact target module, accountable owner, rationale, and removal phase. The validator also rejects internal module cycles, stale exceptions, missing packages, and any new module that directly imports a network client without explicit registration.

`runtime.adapter_contracts` owns the one generic `AdapterResult` class and runtime-checkable adapter protocol. `adapters.base` is a temporary compatibility re-export, so integrations and callers cannot create competing result identities. `ToolDispatcher` validates source, status, warning types, secret safety, and finite JSON serializability before evidence crosses the runtime boundary.

## Flagship boundary

`seoctl audit technical` (`audit.technical`) is the sole flagship command. It performs bounded read-only diagnosis and produces the ten-artifact decision-ready technical SEO evidence package defined by the product contract. Fixture execution proves deterministic contract behavior only; bounded live execution reports authorized observations at a stated time. Neither proves complete site coverage or search-engine, ranking, traffic, conversion, production-readiness, or comparative outcomes.

`system.run` and `full-site-audit` are evidence-dependent multi-agent orchestration capabilities. They must disclose missing evidence and unexecuted domains and must not be presented as alternate flagship paths or completeness guarantees.
