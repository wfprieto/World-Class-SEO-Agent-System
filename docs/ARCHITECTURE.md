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

`seoctl` is the outer composition layer and may assemble runtime, adapter, and integration components. All other cross-layer imports fail unless the architecture contract names the exact source module, exact target module, accountable owner, rationale, and removal phase. Absolute, relative, package-`__init__`, and literal reflective imports participate in the same dependency and cycle graph, including aliased built-in imports, positional or keyword `import_module` forms, and module-global, source-ordered exact Name or Attribute assignments to `importlib`, `builtins`, `import_module`, or `__import__`. Dynamic expressions and arbitrary cross-scope data flow are not claimed as assignment-alias analysis; once an exact reflective alias is observed, an unresolved reassignment remains fail-closed. Literal relative reflection is resolved against its literal package and fails closed when resolution is impossible. The validator also rejects stale exceptions, missing packages, and new modules that directly import a declared network or browser client, dynamically import a declared client by a literal name, or launch a statically identifiable network command without explicit registration. Process detection resolves positional and keyword arguments, quoted or byte-string executables, normalized executable path, case, and `.exe` suffix. A literal `executable=` override selecting `sh`, `bash`, `env`, or their `.exe` forms is composed with its literal argv and the same finite grammar; unresolved selected-wrapper argv fails closed while non-wrapper argv remains data. The quote-aware wrapper grammar covers `sh`/`bash` command options (including combined `-lc` and `--noprofile -c`), `env` flags and option operands, shell `exec`, leading environment assignments, and the POSIX `command` builtin; `command -v` and `command -V` are treated as non-executing queries. Unquoted control operators, redirects, newlines, command substitution, backticks, or supported wrappers with dynamic or unrecognized grammar fail closed as network-capable. Quoted punctuation and punctuation in non-shell argument values remain data and are negative controls. This remains an import-and-literal-call egress inventory, not whole-program data-flow proof; indirect calls and dynamically constructed non-wrapper command strings remain the responsibility of security review.

Every registered direct network sink must also have an exact `network_transports` entry naming its policy and canonical delegate. The rendered-page adapter delegates raw HTTP to the bounded technical HTTP client, which validates every redirect hop, caps redirects, response bytes, and time, and closes every response. Evidence exports strip URL credentials, queries, fragments, sensitive headers, and credential-like console or error text. Playwright requests are revalidated before continuation, but validation and browser resolution are separate: this is not DNS pinning and does not claim to eliminate DNS rebinding.

Credential-bearing LLM requests reject redirects and retry only bounded transient transport failures. The GSC example delegates OAuth and API calls to the approved-host Google transport instead of implementing a separate credential path. The generated development dependency lock includes SHA-256 artifact hashes for every exact pin, and validation fails when any pin loses its hash.

`runtime.adapter_contracts` owns the one generic `AdapterResult` class and runtime-checkable adapter protocol. `adapters.base` is a temporary compatibility re-export, so integrations and callers cannot create competing result identities. `ToolDispatcher` validates source, status, warning types, secret safety, and finite JSON serializability before evidence crosses the runtime boundary.

## Flagship boundary

`seoctl audit technical` (`audit.technical`) is the sole flagship command. It performs bounded read-only diagnosis and produces the ten-artifact decision-ready technical SEO evidence package defined by the product contract. Fixture execution proves deterministic contract behavior only; bounded live execution reports authorized observations at a stated time. Neither proves complete site coverage or search-engine, ranking, traffic, conversion, production-readiness, or comparative outcomes.

`system.run` and `full-site-audit` are evidence-dependent multi-agent orchestration capabilities. They must disclose missing evidence and unexecuted domains and must not be presented as alternate flagship paths or completeness guarantees.
