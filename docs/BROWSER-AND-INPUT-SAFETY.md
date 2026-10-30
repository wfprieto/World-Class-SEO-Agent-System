# Browser and imported-evidence safety

The SEO mission remains evidence-first, model-agnostic inspection. These controls
bound inspection and preserve truthful failure states; they do not certify legal
compliance, ranking outcomes, or arbitrary hostile-browser containment.

## Reproducible browser validation

Use CPython 3.11, 3.12, or 3.13 on Windows or Ubuntu:

```console
python -m pip install --require-hashes -r requirements-dev.txt
python -m pip install --no-deps --no-build-isolation -e .
python -m pip install --require-hashes -r requirements-browser.txt
python -m playwright install --with-deps chromium
python -m pytest -q --browser-security
```

The separate browser hash lock pins Playwright 1.64.1. Default development
dependencies do not install it. The `render` extra is still optional
for ordinary installations; it now requires Playwright 1.64.1 or newer within 1.x.
The browser-profile event-emitter constraint keeps its generated lock installable on
Python 3.11 as well as newer supported interpreters.

Ordinary local pytest runs skip actual-browser cases unless `--browser-security`
or `WCSEO_BROWSER_SECURITY=1` is set. Certification mode does not skip a missing
Chromium runtime. The required six-cell CI validation matrix installs Chromium
and uses the explicit flag; reviewed workflow metadata binds both commands.
The TLS fixtures also require OpenSSL (available on the supported CI images).

All runtime security fixtures are controlled local servers. Test-scoped public
numeric destinations map to those servers; private-address classification stays
intact. Private sentinels record accepted TCP connections, not only HTTP responses.
Test certificates are ephemeral and never installed into the OS trust store.

## Shared connection boundary

`security.url_safety` remains the canonical HTTP(S) target policy. Each outbound
connection resolves and validates its complete address set, then dials only a
vetted numeric destination. HTTP Host and HTTPS SNI retain the original hostname;
certificate and hostname verification remain enabled. Mixed public/private DNS
answers fail closed. Ambient proxy settings do not select another upstream.

Both renderer interfaces use `security.browser_capture`. Each inspection gets a
new non-persistent Chromium context and a short-lived, authenticated loopback
forward proxy. That proxy applies the same numeric socket boundary to redirects,
subresources, popups, workers, and WebSocket destinations. Chromium's implicit
loopback proxy bypass, QUIC, and nonproxied WebRTC UDP are disabled. Service
workers and downloads are disabled for inspection.

Public HTTP WebSocket upgrades preserve their handshake and use the bounded
relay. Public secure WebSockets use verified end-to-end TLS through CONNECT.
Neither path substitutes a mocked successful WebSocket connection. Individual
`websocket` resource blocking is unsupported and is rejected explicitly; other
supported resource-type blocks remain available. This avoids silently accepting
an ineffective block or a blocking SDK interception callback.

HTTPS CONNECT can inspect the destination but not encrypted paths, queries, or
redirect headers. Initial/context-routed HTTP URLs also receive URL-policy checks,
but this is **not** proof that every encrypted redirect or WebSocket query is
visible to the proxy. Do not claim comprehensive URL-content or secret detection.

The connection deadline includes elapsed DNS time before dialing. An OS resolver
call itself is not forcibly interruptible; after it returns, expired/cancelled
connections are not opened. Active relays and context cleanup are bounded.

RDAP/authority and both real-model clients use the same pinned public sockets,
including custom model endpoints. Endpoint approval does not authorize a private
address. Injected transports remain trusted test/application dependencies.

Technical HTTP operations share one elapsed-time budget across DNS, TCP/TLS,
headers, body consumption and redirects. Authority requests share one budget
across retries, retry sleeps and accepted HTTP-error bodies. Deadline expiry shuts
down registered raw/TLS sockets; TLS handshakes are registered before they start.
Responses, including accepted and rejected HTTP errors, are closed on all paths.
An in-flight OS DNS call cannot be forcibly stopped; expiry prevents subsequent
lookups/dials after it returns. Arbitrary injected openers/adapters may still run
after a dispatcher timeout, so the generic indeterminate-work warning remains.

Redirect evidence is a separate display projection: it strips URL credentials,
queries/fragments and non-allowlisted headers. Raw response headers and Location
values remain internal so routing and SEO decisions use the original values.

## Browser output and work ceilings

Per inspection, the proxy permits at most 1,000 authenticated requests, 64 active
connections, and 50,000,000 relayed/request bytes. Inspection timeouts range from
1 to 120 seconds. Exceeding a budget fails the render instead of producing verified
partial evidence.

Returned HTML and text each have a 12,000,000-byte ceiling. Console/page-error
lists retain at most 500 bounded entries each; failed requests retain at most
1,000. PNG output is limited to 25,000,000 bytes, with a 50-million-pixel ceiling
for full-page captures. Accessibility output is limited to 20,000 Chromium AX nodes.

The legacy accessibility dictionary now contains Chromium CDP `nodes`, including
role/name properties. This replaces Playwright's removed accessibility snapshot
API; consumers must not assume the old nested snapshot shape.

The raw-fetch adapter continues to validate every redirect through the shared
bounded HTTP client in `auto`, `always`, and `never` modes. Missing or failed
optional rendering retains raw evidence with `partial`/`Not Run`, not fabricated
rendered or accessibility evidence. Network-policy counters describe constraints;
they are not a security certification or proof that a site has no defects.

Chromium still executes untrusted JavaScript. These controls are not an OS-level
CPU/memory sandbox or protection against every browser-engine vulnerability.
Keep the tested browser dependency current and use appropriate process isolation
when inspecting hostile content.

## HTML, URL and provider-response work bounds

SPA and accessibility HTML analysis uses a shared parser with a 12,000,000-character
input ceiling and a 65,536-character markup-token ceiling. Script/style raw text
is not treated as nested markup. Oversized malformed tags fail explicitly. Heading
analysis avoids repeatedly rescanning internal whitespace across every caller.

Crawl URL evidence is bounded before relative expansion: 8,192 characters per URL,
2,000,000 conservative URL-work characters per page, and 20,000,000 across a crawl.
The budget counts up to four retained representations and covers navigation,
canonical/next/previous links, assets and images. Exhaustion fails that page rather
than silently dropping evidence; failed or queued pages keep the crawl partial.

CrUX History validates returned arrays before constructing period/histogram
cross-products: at most 40 periods/p75/density entries and 50 histogram bins per
metric, with at most 50 requested metrics. These are local resource ceilings, not
a claim that malformed provider output is valid or that a live provider was tested.
Missing values remain missing, not zero-valued observations.

Technical sitemap inspection analyzes at most 50,000 locations and caches DNS
classification for at most 64 normalized host/port pairs within five elapsed
seconds. Every URL still gets its own syntax/privacy validation on cache hits.
Unclassified locations or excess entries produce `PARTIAL` evidence, not an unsafe
classification or complete coverage. One slow OS resolver call can outlast this
budget; after it returns, no additional DNS classification is started.

## Imported data and report integrity

| Input | Explicit ceiling and behavior |
| --- | --- |
| Robots policy | 500 KiB, 10,000 combined groups/agents/rules, 8,192-character paths, 2,000,000 matching work units per permission check; exhaustion means permission unknown, never allowed. |
| Sitemap | 50 MiB and 50,000 locations; bounded reads and one-pass duplicate counting; excess is invalid rather than partial success. |
| SERP import | 16 MiB, 1,000 keywords, 100 result rows per keyword, 4,096-character values, 100,000 edges; standalone and unified CLI use the same bounded loader. |

SERP connectivity is accumulated when edges are created, preserving deterministic
hub tie-breaking without rescanning the entire graph for every keyword. These
remain supplied-evidence analyses, not provider observations or ranking promises.

Consent diagnostics project supported signal states and region identifiers before
deriving findings. Reserved report metadata cannot be supplied through override
keys, and redaction covers retained copies and the CLI envelope. Invalid inputs
produce explicit diagnostic findings; this remains technical assessment, not
legal advice or permission to perform live consent tests.

Only the trusted Echo provider can produce authoritative synthetic provenance.
Live model-declared `SYNTHETIC` output is rejected through bounded structured-output
validation. Missing, invalid, or mismatched node provenance fails closed; trusted
Echo workflows retain their intentionally synthetic, final-`PARTIAL` behavior.

## Integration and rollback

An unresolved region conservatively denies grants until corrected. A supplied
granted-default configuration with an invalid region fails the diagnostic and CLI.

The founder-baseline and cross-platform lock branches were already incorporated
through squash merges. Remaining dependency changes are ported onto current main,
not merged as stale whole-file snapshots. Historical rollback proof steps, current
SEO claim evidence, source-integrity gates, and coverage floors must remain intact.

Changes enter main through a normal squash-only PR after exact-head
`repository-certification` passes and all review threads are resolved, under the
owner-selected solo-maintainer policy in `governance/github-controls.json` and
SECURITY.md. Independent engineering review is not a GitHub human approval. No
force push, historical-branch deletion, or required-check bypass is part of consolidation.
Rollback is a reviewed revert of the integration commit; rerun the same validation
matrix and preserve pre/post source-integrity and evidence receipts.

## Bounded analysis fallback

When SPA analysis refuses an oversized or malformed tag, raw evidence is retained
with `is_spa: null` and an `analysis_failed` warning. Auto/never modes return
truthful partial evidence instead of claiming a negative SPA classification;
always mode still invokes the selected renderer. The analysis bound is not raised.

## Source-only certification

CI keeps routine imports and child processes from writing checkout bytecode with
the exact workflow-level `PYTHONDONTWRITEBYTECODE: "1"` policy. Other Python
environment overrides, including narrower job/step/container overrides of this
setting, remain forbidden in canonical validation and release jobs. Mandatory
`compileall -q .` still checks the entire checkout, but its explicit cache prefix
points to disposable runner storage outside that checkout. Existing cache reads
are not disabled; strict source proofs still reject unauthenticated caches.
This avoids relying on every legitimate compiler serialization matching a cached
payload byte-for-byte and does not certify the external compilation output.
