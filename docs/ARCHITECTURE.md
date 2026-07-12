# Architecture

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

- Agent capabilities: `orchestration/capability-registry.json`
- Operator commands: `seoctl/command-registry.json`
- Skills: `skills/skill-catalog.json`
- Priority packages: `skills/package-registry.json`
- Evidence persistence: `adapters/evidence_store.py`
- URL safety: `adapters/url_safety.py`
- Optional providers: `adapters/mcp_extensions.py`
- Comparative scoring: `evaluation/comparative/`

No integration may bypass `ToolDispatcher`, evidence validation, run budgets, or approval gates. Optional provider packs are adapters, not forks of the core.