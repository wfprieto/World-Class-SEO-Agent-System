# Claude Code Plugin Packaging and Business-Type Routing

**Status:** Build specification  
**Last verified against official Claude Code plugin documentation:** 2026-07-10  
**Canonical source path:** `docs/plugin-packaging.md`

## 1. Scope and boundary

This document defines conversion of the SEO kit source into a Claude Code plugin. It does not claim compatibility with Cowork or other hosts.

The source repository is canonical; the plugin is generated. Do not edit generated files as source. Treat the current official Claude Code plugin documentation and strict validator output as authoritative.

This specification covers packaging only. It does not define the SEO methods, change host governance, grant connector permissions, select an outbound license, or authorize metered calls. Do not infer unsupported manifest fields, silently copy unapproved files, expose secrets in generated configuration, or treat successful packaging as proof of audit correctness or production readiness.

## 2. Current Claude Code requirements

A Claude Code plugin is a self-contained directory. The optional manifest is located at `.claude-plugin/plugin.json`. Components live at the plugin root, not inside `.claude-plugin/`.

Default component locations include:

- `skills/<skill-name>/SKILL.md`
- `agents/*.md`
- `hooks/hooks.json`
- `.mcp.json`
- `.lsp.json`
- `scripts/`, `bin/`, and supporting files inside the plugin root

Installed marketplace plugins are copied into a local cache and cannot depend on `../` paths outside the plugin directory. Every runtime dependency and reference file must be included within the plugin root.

Official references:

- https://code.claude.com/docs/en/plugins
- https://code.claude.com/docs/en/plugins-reference
- https://code.claude.com/docs/en/plugin-marketplaces

Compatibility policy:

- Build and validate against the current supported Claude Code release in CI.
- Treat manifest fields and experimental components as version-sensitive.
- Use `claude plugin validate <plugin-root> --strict`; warnings are release failures.
- Record the Claude Code version used for validation and smoke testing.
- Keep `plugin.json` limited to supported fields. Internal SEO metadata belongs in separate files.

## 3. Why the source tree is not yet plugin-ready

The supplied source groups multiple skills inside single Markdown files. Claude Code's current skill layout expects one directory per skill with a `SKILL.md` file. The source agent files may also require plugin-agent frontmatter such as `name` and `description`.

Therefore, packaging requires a deterministic build step. Copying the current source folders into a plugin directory is not sufficient.

## 4. Canonical build model

### 4.1 Source tree

```text
agents/
skills/
knowledge/
adapters/
docs/
runtime/
workflows/
templates/
```

### 4.2 Generated plugin tree

```text
dist/world-class-seo-agent-system/
  .claude-plugin/
    plugin.json
  agents/
    seo-ecommerce-agent.md
    ...
  skills/
    product-page-seo-audit/
      SKILL.md
      references/
    product-schema-validate-generate/
      SKILL.md
      references/
    single-page-audit/
      SKILL.md
      references/
    ...
  knowledge/
    ...
  docs/
    ...
  scripts/
    ...
  templates/
    ...
```

`knowledge/`, `docs/`, and `templates/` are supporting files, not auto-discovered plugin components. Skills and agents must reference them using paths that remain inside the plugin root. Shell commands should use `${CLAUDE_PLUGIN_ROOT}` rather than assuming the current working directory.

## 5. Build requirements

The build must:

1. Start from a clean, versioned source state.
2. Parse each source skill file and emit exactly one `skills/<canonical-name>/SKILL.md` per skill.
3. Add valid skill frontmatter, including a clear description and invocation controls where needed.
4. Copy agent files and validate required agent frontmatter.
5. Copy only required knowledge, docs, templates, and scripts.
6. Rewrite or reject references that escape the plugin root.
7. Fail on duplicate skill names, agent namespaces, route precedence, or output paths.
8. Fail on unresolved references.
9. Generate a duplicate-content report and centralize shared governance.
10. Exclude `.seo-cache/`, evidence databases, screenshots, credentials, local settings, and client data.
11. Emit `dist/plugin-file-map.json` mapping every source file or section to its generated destination and content hash.
12. Generate `.claude-plugin/plugin.json` from the reviewed manifest template.
13. Produce a hashed release inventory and load only listed files; fail closed on missing or extra executable components.

## 6. Plugin manifest

Use `.claude-plugin/plugin.json` only for supported plugin metadata and component configuration. Do not use it as the SEO kit's internal architecture manifest.

The reviewed `plugin.example.json` contains supported metadata only and relies on default component discovery in the generated plugin tree. The license field is omitted until the owner selects and documents an outbound license.

Run strict validation before every release:

```bash
claude plugin validate ./dist/world-class-seo-agent-system --strict
```

Unrecognized fields generate warnings and should fail CI under `--strict`. Wrong types on recognized fields can prevent the plugin from loading.

## 7. MCP and external services

Do not place a list of vendor names in `plugin.json` and assume they become connectors. Claude Code MCP servers are configured through `.mcp.json`, manifest `mcpServers`, or user-level configuration.

Default release policy:

- Do not bundle metered MCP servers in the base plugin.
- Provide operator instructions and example configurations separately.
- Require explicit user action to connect each external server.
- Prefer read-only access and least-privilege scopes.
- Never store API keys in the repository or manifest.
- Require cost approval inside the SEO workflow even when the connector is already authenticated.

If a future edition bundles MCP configuration, verify transport, endpoint, authentication, permissions, and server identity against current official provider documentation.

## 8. Local development and release

Local smoke test:

```bash
claude --plugin-dir ./dist/world-class-seo-agent-system
```

After changes, reload with `/reload-plugins`. Test namespaced skills, agent discovery, file access, missing-connector behavior, and cost gates.

For marketplace distribution, create a separate `.claude-plugin/marketplace.json` at the marketplace repository root. The marketplace entry must point to the complete plugin directory and use a nonreserved marketplace name. Version changes must be deliberate and synchronized with the release process.

## 9. Business-type detection

Business-type detection is a routing aid, not a factual classification. It must produce evidence, a confidence score, and a reversible decision.

### 9.1 Supported profiles

- `generic`
- `ecommerce`
- `local-service`
- `saas`
- `publisher`
- `agency-b2b`

A site can be multi-profile.

### 9.2 Evidence signals

Use observable signals from the homepage and a small representative sample:

| Profile | Strong signals | Supporting signals |
|---|---|---|
| E-commerce | Buyable `Product`/`Offer` data, cart or checkout, visible prices and purchase actions | Product grids, collections, shipping/returns, merchant feed references |
| Local service | `LocalBusiness` data, verified NAP, location pages, service area | Map embed, appointment action, local phone and hours |
| SaaS | Software product, signup/trial flow, pricing plans | Documentation, integrations, changelog, `SoftwareApplication` data |
| Publisher | High article volume, article schema, bylines | Sections, subscriptions, editorial policies, ad inventory |
| Agency/B2B | Service offerings and contact-sales flow | Case studies, client outcomes, industries served, lead forms |

Do not infer protected classes, sensitive personal traits, or regulated status from audience language.

### 9.3 Scoring model

This is an internal routing model, not an SEO standard:

- Strong signal: 3 points
- Supporting signal: 1 point
- Contradictory signal: minus 2 points
- Strong classification: at least 6 points and a margin of at least 2 over the next profile
- Multi-profile: two or more profiles each score at least 6
- Low confidence: top score below 6 or margin below 2

Explicit user selection overrides the model. Low confidence routes to `generic` and asks at most one material clarifying question when the answer changes execution. It must never silently guess.

## 10. Routing output contract

Return:

- Observed signals labeled `FACT`.
- Inferred profile labeled `ANALYSIS`.
- Score and confidence.
- Selected agent/skill profile.
- Any user override.
- Missing evidence and resulting limitations.

## 11. Acceptance tests

Packaging is blocked until all pass. Browser and workflow claims require observable proof rather than narrative confirmation:

- Strict plugin validation.
- Every generated skill appears under the expected namespace.
- Every packaged agent loads with a unique name.
- No external path traversal or missing supporting file.
- No secrets or client artifacts in the release.
- Offline mode works with explicit limitations.
- Missing MCP connectors degrade without invented data.
- Metered actions remain approval-gated.
- Business-type fixtures route correctly for single-profile, multi-profile, conflicting, and unknown sites.
- User override wins over auto-detection.
- A browser-render smoke test captures desktop and mobile screenshots for a static page and a JavaScript-rendered page, with the URL, viewport, capture time, and artifact path recorded.
- A single-page workflow smoke test records the selected route, invoked skills, skipped skills, connector tier, approval events, and final deduplication result.
- A blocked or unreachable URL produces an explicit partial/failure report without fabricated visual findings.

## 12. Known limitations

The full host repository, build tooling, source indexes, and runtime router were not included. This document specifies the packaging contract but does not implement or prove the required build transformation.
