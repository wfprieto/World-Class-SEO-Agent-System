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