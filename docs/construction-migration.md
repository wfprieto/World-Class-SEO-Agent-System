# Explicit construction migration

This pre-release migration changes library construction, not the CLI evidence
contract. Existing scripts that relied on implicit cross-layer construction must
choose explicit ports or use the public factories in `seoctl.composition`.

```python
from pathlib import Path
from seoctl.composition import build_orchestrator, default_adapters

root = Path("/path/to/source-or-installed-assets")
orchestrator = build_orchestrator(root)  # offline echo, fully wired tools
adapters = default_adapters(root)
```

`default_adapters` replaces `adapters.registry.default_adapters`; the old module
contains neutral contract exports only. The 47 ordered keys and adapter classes
remain unchanged. Alias entries remain separate instances, as before.

| Consumer | Explicit dependency | Composed factory |
| --- | --- | --- |
| Runtime | `ToolDispatcher(mapping)`; omitted executor tools are empty | `build_orchestrator` |
| Live LLM | `opener=`; echo/dry-run still needs none | `build_llm_client` |
| PageSpeed | neutral `JsonClient` | `build_pagespeed_adapter` |
| GSC example | token provider and JSON client | `build_gsc_example_adapter` |
| Rendered-page adapter/module | `raw_fetch=` callable | `default_adapters` / `build_raw_fetch` |
| Drift | context-manager factory and canonical URL identity | `build_drift_service` |
| Common Crawl | canonical URL identity | `build_commoncrawl_service` |
| Optional providers | neutral provider controls | `build_provider_service` |
| Content intelligence | explicit provider service | `build_content_service` |
| Product-proof audit | explicit claim-registry path | `build_product_proof_service` |
| Technical CWV | optional narrow PageSpeed port | `build_technical_service` |

`build_orchestrator` accepts `provider="echo"`, `model=None`, and explicit
`llm_client`, `tool_dispatcher`, and `memory` overrides. Explicit instances are
retained, including an empty dispatcher. `ToolDispatcher()` or `None` raises a
configuration error directing callers here; a raw orchestrator still supports
routing and offline execution, but cannot silently acquire live tools.

Live clients retain credential and endpoint validation before checking the opener.
The composed opener disables ambient proxies, rejects credential redirects, and
uses the existing numeric-pinned HTTP/HTTPS handlers with original TLS identity.
Retry budgets, 120-second LLM request timeout, 10 MB response ceiling, parsing and
response closure remain in the runtime. No raw client silently constructs another
transport. `LLMConfigurationError` and `GoogleAPIError` remain shared identities.

Raw rendered-page and live technical CWV calls without their ports return explicit
`not_configured` results. Fixture-only technical operations remain available.
PageSpeed retains its missing-key error and rejects live execution without a JSON
client. GSC similarly reports missing token/client configuration without fallback.

The raw-fetch factory binds the existing bounded HTTP client with a 30-second
timeout, 12 MB response ceiling, ten redirects, and the original user-agent.
Browser egress continues through the canonical isolated numeric-egress boundary.
Provider cost/approval gates and truthful availability states remain authoritative;
construction performs no provider request or background monitoring.

Product-proof construction resolves the canonical source or installed asset root,
then passes `knowledge/seo-claim-registry.json` explicitly. Direct construction
requires `claim_registry=`. No import-time integration-to-runtime asset lookup
remains. The audit CLI supplies its existing canonical root.

Architecture retirement requires the actual exception list, expected count, and
retirement plans to be empty and the digest to bind the newline-encoded empty edge
set. `RETIRED` does not authorize new dependencies or disable the architecture gate.
Historical reauthorization negatives use frozen c5a47c3 fixtures rather than treating
old authorization as current approval.

Rollback is a reviewed revert of the complete construction-and-policy slice. It
must not reset local changes, modify evidence databases, or replace credentials.
Focused tests do not establish release authorization or external provider readiness.
