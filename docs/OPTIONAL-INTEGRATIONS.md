# Optional Integrations, Bing, and IndexNow

**Verified:** 2026-07-12  
**Canonical provider registry:** `adapters/mcp_extensions.py`

This phase turns the optional-provider registry into an executable operator surface without
adding paid providers to the core install. Discovery, preflight, configuration rendering, and
cost estimation perform no provider calls. IndexNow is the only write path added, and it is
blocked unless the operator explicitly requests execution and supplies the exact confirmation
phrase.

## Commands

```text
seoctl integrations list
seoctl integrations preflight --provider <id>
seoctl integrations config --provider <id> --client generic|codex|claude
seoctl integrations estimate --provider <id> --units <n> [--unit-cost <usd>] [--ceiling <usd>] [--approve]
seoctl bing preflight
seoctl indexnow validate --urls <json-or-text-file> [--key-location <url>]
seoctl indexnow submit --urls <json-or-text-file> --execute --confirm INDEXNOW_SUBMIT
```

## Provider controls

The registry covers DataForSEO, Ahrefs, Firecrawl, SE Ranking, Profound, Unlighthouse,
Bing Webmaster Tools, and optional image generation.

Every provider record declares:

- provider and capability ownership;
- free or metered cost class;
- allowed and forbidden operations;
- required credential variables;
- official documentation;
- verified transport and authentication mode when confirmed;
- current live state;
- removal instructions.

Multiple credentials are conjunctive. For example, DataForSEO is not considered configured
unless both `DATAFORSEO_USERNAME` and `DATAFORSEO_PASSWORD` are present.

Generated client templates contain placeholders only. Environment values are never copied into
JSON output, command previews, warnings, exceptions, or generated URLs.

## Metered provider gate

No provider pricing is hard-coded because pricing and unit definitions change.

A metered operation remains `BLOCKED` until the operator supplies:

1. a unit count;
2. a current verified unit cost;
3. an approved maximum ceiling;
4. explicit approval.

Existing credentials are not cost approval.

## Provider-specific contract notes

### DataForSEO

Official documentation confirms a hosted Streamable HTTP MCP endpoint at
`https://mcp.dataforseo.com/mcp`, OAuth support for hosted clients, and Basic authentication
for direct MCP configuration using the API login and password.

Source: https://dataforseo.com/model-context-protocol

### Ahrefs

The hosted MCP endpoint is `https://api.ahrefs.com/mcp/mcp`. Ahrefs documents plan and API-unit
limits, dedicated MCP-scoped keys, and states that custom standalone HTTP/JSON-RPC clients are
unsupported. The registry therefore marks this integration `HOST_CLIENT_ONLY`; `seoctl` renders
host-client configuration but does not call the hosted MCP endpoint directly.

Source: https://docs.ahrefs.com/en/mcp/docs/introduction

### Firecrawl

Firecrawl documents MCP tools for scrape, batch scrape, map, crawl, and search. Calls use normal
account rate limits. The registry keeps URL-fetching controls explicit and forbids private-host
crawling.

Source: https://docs.firecrawl.dev/use-cases/developers-mcp

### SE Ranking

SE Ranking documents a hosted Streamable HTTP endpoint at `https://api.seranking.com/mcp`,
OAuth 2.1, API-key alternatives, and a large provider-controlled tool surface. The kit keeps
the provider optional and read-only by default.

Source: https://seranking.com/api/integrations/mcp/

### Profound

Profound documents organization, model, category, domain, prompt, visibility, sentiment,
citation, referral, and bot-report tools with explicit date scopes and pagination. The kit
does not flatten these provider-specific metrics into universal SEO facts.

Source: https://docs.tryprofound.com/mcp/capabilities/analytics-capabilities

## Bing Webmaster Tools

`seoctl bing preflight` reports credential presence and governance state only. The registry
marks live direct Bing Webmaster API execution `BLOCKED_BY_CONTRACT` because a current official,
safe authentication contract was not verified during this phase. No legacy query-string API-key
behavior is implemented or guessed.

IndexNow is implemented separately from Bing Webmaster Tools.

## IndexNow

IndexNow accepts one URL by request or up to 10,000 URLs in one JSON POST. URLs in one request
must belong to one host. Keys are 8-128 letters, numbers, or dashes. Ownership is proven by a
UTF-8 key file hosted at the root or by a scoped `keyLocation`.

The implementation:

- reads the key only from `INDEXNOW_KEY`;
- never accepts a key as a command-line argument;
- never returns or logs the key;
- validates one-host and key-location scope;
- restricts the endpoint to approved HTTPS hosts and `/indexnow`;
- sends no request without `--execute --confirm INDEXNOW_SUBMIT`;
- performs no automatic retries for the write;
- caps response size;
- treats 200/202 as receipt or pending validation, not proof of crawling or indexing;
- preserves 400, 403, 422, and 429 as distinct failure states.

Official sources:

- https://www.indexnow.org/documentation
- https://www.bing.com/indexnow

## Live evidence state

The fixture and governance contracts are executable without credentials. No paid-provider,
Bing Webmaster, or IndexNow live request is claimed by this phase unless a separate authorized
smoke record exists. Those parity rows remain open until live evidence is available.
