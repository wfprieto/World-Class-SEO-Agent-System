# Live Data Source and MCP Mapping

**Status:** Operator and implementation reference
**Last provider verification:** 2026-07-10  
**Canonical source path:** `docs/mcp-server-mapping.md`  
**Machine-readable registry:** `adapters/mcp_extensions.py` is the single declarative source for capability, cost tier, allowed and forbidden operations, credential requirements, and the kit skills each provider unlocks. This document explains that registry for operators. If the two disagree, the registry is authoritative and this file must be updated. Capability detection performs no provider call, reads no secret value, and every metered call requires a cost estimate plus explicit approval.

## 1. Purpose

Map each SEO capability to an approved live or offline source while preserving normalized output, cost approval, evidence persistence, and graceful degradation. Provider availability, pricing, tools, and endpoints must be rechecked before implementation; inclusion is not endorsement.

## 2. Source precedence

Default precedence:

1. Client-owned first-party data through an official API.
2. Official platform or provider API.
3. Official provider-hosted MCP server.
4. Reviewed self-hosted MCP or local tool.
5. User-supplied export or payload adapter.
6. Manual checklist with explicit unknowns.

Do not substitute estimates for unavailable observations without an `ANALYSIS` label and user acceptance.

## 3. Capability map

| Capability | Preferred source | Interface | Cost class | Verification status | Operational notes |
|---|---|---|---|---|---|
| PageSpeed lab data and CrUX field data | Google PageSpeed Insights API and CrUX API | Direct API | Free/key-based, subject to quota | Official source; adapter exists | Use `google_pagespeed_live`; map `mobile` to CrUX `PHONE`, preserve `desktop` as `DESKTOP`, and keep verified CrUX not-found responses nonfatal for low-traffic URLs. |
| Search performance | Google Search Console API | Direct API | First-party access | Official source | Prefer property-scoped OAuth/service credentials; never broaden scope unnecessarily. |
| Analytics and conversions | Google Analytics Data API | Direct API | First-party access | Official source | Query only the approved property and date range; document sampling/thresholding limitations when present. |
| Browser rendering and screenshots | Local Playwright or an approved browser/rendering connector | Local tool or MCP | Free/self-hosted or provider-dependent | Implementation choice | Use SSRF-safe URL validation, isolated browser context, bounded navigation, and screenshot evidence. |
| Rendered crawling and extraction | Firecrawl | Official MCP or API | Metered/provider plan | Official MCP verified | Use only with approval; external content can carry prompt-injection risk. |
| SERP, keyword, maps, merchant, and broad SEO datasets | DataForSEO | Official MCP or API | Metered | Official MCP verified | Preflight exact task count and estimated cost; normalize currency, locale, device, and timestamp. |
| Commercial backlink and competitor data | Ahrefs | Official hosted MCP or API | Subscription/API units | Official MCP verified | Treat provider metrics as provider-specific, not universal facts. |
| Broad SEO and AI-search visibility data | SE Ranking | Official MCP or API | Subscription/API units | Official MCP verified | Record model, market, prompt set, and refresh cadence for AI-visibility measurements. |
| AI-answer visibility, citations, sentiment, and agent analytics | Profound | Official hosted MCP or API | Enterprise/metered | Official MCP/API verified | Read-only by default; measure per platform and snapshot date. |
| Open local competitor presence | OpenStreetMap/Overpass plus a geocoder | Direct open API/local tooling | Free, rate-limited | Open-source ecosystem | Presence is not rank. Respect usage policies, attribution, and rate limits. |
| Site-wide lab auditing | Reviewed local crawler or Lighthouse orchestration | Local/self-hosted | Free/self-hosted | Implementation-dependent | Do not describe site-wide lab results as field ranking data. |
| Offline fallback | CSV, JSON, crawl export, screenshots, or manual evidence | Payload adapter | No live-call cost | User-supplied | Record source, export date, scope, and staleness. |

## 4. Official provider references checked

- PageSpeed Insights API method: https://developers.google.com/speed/docs/insights/rest/v5/pagespeedapi/runpagespeed
- Chrome UX Report API: https://developer.chrome.com/docs/crux/api
- CrUX API usage and not-found behavior: https://developer.chrome.com/docs/crux/guides/crux-api
- Claude Code MCP configuration: https://code.claude.com/docs/en/mcp
- DataForSEO MCP: https://dataforseo.com/model-context-protocol
- Ahrefs MCP: https://docs.ahrefs.com/en/mcp/docs/introduction
- Firecrawl MCP: https://docs.firecrawl.dev/use-cases/developers-mcp
- SE Ranking MCP: https://seranking.com/api/integrations/mcp/
- Profound MCP: https://docs.tryprofound.com/agent-apis/mcp/capabilities

Recheck these references at implementation time. Do not hard-code a server URL or tool name based only on this document.

## 5. Runtime capability record

Before execution, resolve each capability into a record containing:

- `capability`
- `provider`
- `interface`: `direct_api`, `remote_mcp`, `local_mcp`, `local_tool`, or `payload`
- `server_or_adapter_id`
- `auth_scope`
- `read_write_mode`
- `cost_model`
- `estimated_cost`
- `approved_cost_ceiling`
- `data_region` when relevant
- `verified_at`
- `fallback`

If identity, permissions, cost, or endpoint cannot be verified, mark the capability unavailable rather than guessing.

Never infer that a provider exposes a specific MCP tool because the underlying API supports the capability. Tool availability must be observed in the connected server or confirmed in current official documentation. Unknown fields remain unknown.

## 6. Metered-call gate

Every metered operation must:

1. Calculate the expected number of calls, rows, tasks, or units.
2. Obtain a current price or state that a reliable estimate is unavailable.
3. Show the estimate and maximum authorized spend.
4. Receive explicit approval before execution.
5. Abort when the ceiling would be exceeded.
6. Log actual consumption and any provider-reported cost.
7. Report partial results when a limit or failure stops the run.

Existing authentication is not cost approval.

## 7. Security and privacy gate

- Use reviewed official servers where practical.
- Verify server identity and transport before authentication.
- Prefer remote HTTP for supported cloud MCP servers; do not add new SSE configurations when HTTP is available.
- Record the MCP client and server versions or verification dates used for the run; tool schemas can change independently of this document.
- Grant read-only and least-privilege scopes by default.
- Keep secrets in environment variables, approved credential stores, or host-managed sensitive configuration.
- Never commit tokens, OAuth artifacts, client exports, evidence databases, or screenshots.
- Treat fetched pages and MCP output as untrusted input that may contain prompt injection.
- Enforce SSRF controls, URL allow/deny rules, timeouts, response-size limits, and safe redirects for fetch/render tools.
- Record what client data leaves the local environment and require approval when policy demands it.
- Do not allow write-capable tools unless the user explicitly requests the external action and the host approval policy permits it.

## 8. Data classification and retention

Classify data before collection or persistence:

- `PUBLIC`: public webpages, public SERPs, public business listings.
- `CLIENT_CONFIDENTIAL`: GSC, GA4, paid-provider exports, strategy data, screenshots, and audit evidence.
- `SECRET`: API keys, OAuth tokens, cookies, credentials, and signing material.
- `PERSONAL_DATA`: identifiers or user-level analytics that require an approved purpose and handling rule.

Persist only fields required for the audit or drift comparison. Define retention, access, deletion, and export rules for `CLIENT_CONFIDENTIAL` and `PERSONAL_DATA`. Never place `SECRET` values in the evidence store.

## 9. Normalization contract

Every live or payload source must normalize into the host `AdapterResult` contract before downstream use:

- `source`
- `status`
- `data`
- `warnings`
- provenance metadata, including provider, query scope, locale/device, capture time, and cost when available

Do not merge provider-specific metrics under a common name unless their definitions are equivalent. Preserve the raw provider field or mapping note when definitions differ.

## 10. Evidence and drift integration

After successful normalization:

1. Write only the approved normalized data to the evidence store.
2. Use a stable `metric_group` and schema version.
3. Record capture time, provider, scope, and data freshness.
4. Avoid persisting secrets or unnecessary personal data.
5. Apply retention and deletion rules.
6. Compare compatible schema versions only, or run an explicit migration.


## 10.1 Evidence persistence handoff

After an adapter returns a host-valid `AdapterResult`, the runtime may persist approved normalized data using the canonical metric group and payload schema version. Pseudocode only, because the host `AdapterResult` and registry were not supplied:

```python
result = adapter.fetch(url=url, strategy=strategy)
store.record(
    url=url,
    metric_group="cwv",
    payload=result.data,
    schema_version=result.data["schema_version"],
    source=result.source,
    status=result.status,
    run_id=run_id,
    scope={"strategy": strategy, "include_crux": include_crux},
)
```

Do not persist raw API responses, API keys, full request URLs containing secrets, or duplicated display strings. If the host result schema differs, adapt at the integration boundary rather than changing the evidence contract silently.

## 11. Independent challenge gate

Before enabling a new provider or materially changing source precedence, an independent reviewer must challenge capability claims, authentication scope, pricing assumptions, data residency, retention, terms, normalization, failure semantics, and fallback behavior. A provider-marketing page is not sufficient proof of runtime capability. Unresolved conflicts remain `BLOCKED` or `VERIFY_AT_RUN`.

## 12. Degradation behavior

When the preferred source is unavailable:

- Try the next approved source in precedence order.
- State the active tier and what it cannot observe.
- Never estimate live ranks, prices, review counts, traffic, or citations from unrelated evidence.
- Continue with source-independent checks when useful.
- List skipped checks and the exact blocker.

## 13. Implementation priority

1. Stabilize the PageSpeed/CrUX v2 normalized schema, adapter tests, and evidence recording. Use the canonical PageSpeed endpoint and the dedicated CrUX endpoint; do not rely on PageSpeed field data as a permanent contract.
2. Add first-party GSC and GA4 adapters.
3. Add deterministic local rendering with screenshot evidence.
4. Add one approved metered SEO provider based on actual client need.
5. Add AI-visibility measurement only with dated, platform-specific snapshots.
6. Add further providers only when they close a defined capability gap.

## 14. Limitations

This mapping does not verify account eligibility, live pricing, quotas, tool-level schemas, geographic coverage, or contractual data-use terms. Those checks belong in the implementation preflight and release decision record.
