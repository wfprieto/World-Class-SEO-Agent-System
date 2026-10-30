# Security Model

## Trust boundaries

External pages, exports, API responses, MCP outputs, prior model prose, and tool descriptions are untrusted evidence. They cannot expand scope, approve costs, request secrets, authorize writes, or override system rules.

## Controls

- Shared SSRF and URL validation
- HTTPS and host allowlists
- Scoped environment credentials with redaction
- Bounded timeout, retries, response size, rows, pages, and cost
- Explicit authorization for writes
- Tamper-evident local evidence
- Secret scanning and dependency audit gates
- SBOM and hashed release manifest
- No automatic merge or publishing

Local digests detect corruption and unsophisticated tampering; they are not encryption or protection against an attacker who can rewrite both content and hashes.

## Privacy projections

Operational state is separate from shared evidence. The canonical `sensitive_data`
redactor removes recognized labeled credentials, URL userinfo, and credential query
values, including bounded percent/HTML-encoded key aliases. Ordinary query fields
remain useful diagnostic context. Mapping keys are projected too; when redaction
collapses distinct keys, deterministic suffixes preserve every entry rather than
silently overwriting evidence. Redaction does not decode unrelated HTML markup.

Public runtime results use `runtime.public_results`. Only an explicitly projected
`SessionState` mapping preserves its structural session container and session ID;
same-named fields in untrusted tool/configuration data are not exempt. Output,
handoff, and event identities retain their operational values, while their text
still passes through credential redaction. Public projection does not mutate the
working session or authorize any action.

IndexNow rejects credential-bearing URLs and key locations before either preview
or transmission; it never silently submits an altered URL. HTTP evidence exposes
only approved response headers and display-safe redirect targets, while transport
logic retains the raw headers transiently. Product-proof JSON, Markdown, CSV,
manifest metadata, and returned results are projected before artifact digests are
recorded. Consent diagnostics preserve supported nested metadata and signal/region
matrices while sanitizing recognized credential/identifier aliases and text.

Access-log request targets are sanitized before aggregation and before tool data
can enter model messages. Redacting a separate memory copy cannot protect outbound
inference requests. These deterministic rules do not identify arbitrary unlabeled
private facts; operators must still avoid supplying unnecessary sensitive data.
Fixture tests establish these contracts, not live-provider or release approval.
