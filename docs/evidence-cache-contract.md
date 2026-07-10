# Evidence Cache and Drift Store Contract

**Status:** Controlled integration baseline
**Contract version:** 2.0.0
**Database schema version:** 3
**Last reconciled:** 2026-07-10
**Scope:** `.seo-cache/` JSON cache files and `adapters/evidence_store.py`  
**Canonical source path:** `docs/evidence-cache-contract.md`

## 1. Purpose and success criteria

This contract defines two local storage layers without treating either as a primary source:

1. An optional JSON cache for safe reuse of recent normalized results.
2. A persistent SQLite evidence store for dated snapshots and compatible drift comparison.

Fresh live evidence outranks cached evidence. A cache hit proves reuse, not a current observation.

The subsystem succeeds when callers can safely reuse eligible results, persist normalized evidence, compare compatible snapshots, reject corrupted or sensitive records, enforce retention and deletion, and explain every hit, miss, partial result, and blocker without overstating freshness.

## 2. Authority, ownership, and boundaries

Precedence:

1. Host security, privacy, approval, retention, and release policy.
2. Host `AdapterResult`, registry, routing, and reporting contracts.
3. This contract.
4. Adapter- or metric-specific schemas.

Responsibilities:

- The adapter gathers and normalizes evidence.
- The cache stores reusable copies.
- The evidence store persists dated normalized snapshots.
- The drift monitor interprets compatible changes.
- The host runtime owns orchestration, policy enforcement, and user-facing claims.

The cache and store must not call providers, infer missing observations, or merge provider-specific metrics as if they were universally equivalent. Existing `record(url, metric_group, payload)`, `latest(...)`, `compare(...)`, and `close()` entry points remain supported unless the host approves a breaking migration.

## 3. Evidence and result states

Use the following meanings consistently:

- `ok`: every requested component completed and normalized.
- `partial`: valid evidence remains, but a requested component is unavailable, not found, not configured, rate-limited, or invalid.
- `skipped`: the caller explicitly omitted the component.
- `cache_miss`: no eligible reusable entry exists.
- `schema_mismatch`: snapshots exist but cannot be compared safely.
- `insufficient_history`: fewer than two compatible snapshots exist.
- `integrity_failure`: persisted data failed hash, JSON, or type checks. This is a blocker, not a cache miss.

Do not convert missing metrics to zero. Preserve `null` and an explanatory warning when the reason is known.

## 4. Canonical identity and cache keys

Canonical URL identity:

- Requires HTTP or HTTPS and a host.
- Lowercases and IDNA-normalizes the host.
- Removes fragments and default ports.
- Preserves path and meaningful query parameters.
- Rejects embedded credentials and credential-like query keys.

Cache key procedure:

1. Canonicalize the URL.
2. Serialize request scope as finite, sorted-key JSON.
3. Compute `sha256(canonical_url + "\n" + canonical_scope_json)`.
4. Use at least 24 hexadecimal digest characters in the filename.

Raw URLs and query strings must not become filenames. This avoids path hazards, collisions, and accidental secret exposure.

Recommended layout:

```text
.seo-cache/
  cache/
    <metric-group>/<cache-key>.json
  evidence.db
```

## 5. JSON cache envelope

Every cache file uses this minimum envelope:

```json
{
  "contract_version": "2.0",
  "schema_version": "metric-group.v1",
  "cache_key": "sha256:...",
  "source": "adapter-or-provider",
  "status": "ok",
  "captured_at": "2026-07-10T15:00:00Z",
  "expires_at": null,
  "scope": {},
  "data": {},
  "warnings": [],
  "provenance": {},
  "integrity": {
    "algorithm": "sha256",
    "data_sha256": "..."
  }
}
```

Required provenance includes provider or input type, query scope, locale/device when relevant, source freshness, normalization version, and cost when available. The payload `schema_version` is separate from the SQLite database schema version.

### Cache read and write rules

- Validate envelope version, schema version, key, timestamps, status, and data digest before use.
- A missing, expired, malformed, mismatched, or corrupted entry is not reusable.
- Permission and integrity failures must be reported, not silently swallowed.
- `refresh` and `re-run` bypass cache reads and create a new snapshot.
- Write to a restrictive same-directory temporary file, flush and `fsync`, then replace atomically with `os.replace`.
- Use a per-key lock when concurrent workers may write the same entry.
- Quarantine or delete known-corrupt entries according to host policy.

This contract specifies cache behavior; a separate cache-file implementation is still required unless the host already provides one.

## 6. SQLite evidence-store contract

`adapters/evidence_store.py` stores one normalized snapshot per canonical URL, metric group, payload schema version, and capture time.

Required snapshot fields:

- canonical URL
- metric group
- capture timestamp
- normalized payload object
- payload schema version
- source
- status
- optional run ID
- request scope object
- payload digest
- full-record digest

Supported operations:

- `record(...)`: append one normalized snapshot.
- `latest(...)`: return verified snapshots, newest first.
- `compare(...)`: compare the two latest compatible snapshots.
- `purge(...)`: apply age retention while preserving the newest N per series.
- `delete(...)`: delete evidence for a URL, optionally one metric group.
- `integrity_check(...)`: run SQLite and snapshot verification.
- context-manager and explicit `close()` lifecycle.

Equal timestamps are ordered by descending row ID. Comparisons require matching payload schema versions unless the caller explicitly filters to one version.

### Drift representation

Nested object differences use JSON-Pointer-style paths and distinguish:

- `added`
- `removed`
- `changed`

A removed field is not equivalent to an explicit `null`. Arrays remain ordered values unless the metric schema normalizes them before storage.

## 7. Normalization and provenance rules

Store machine-comparable numeric values with explicit units, not localized display strings. Preserve:

- provider and adapter identity
- requested and resolved URL where available
- query scope and form factor/device
- capture and provider-analysis timestamps
- source collection period or freshness
- runtime warnings and normalization details
- actual provider cost when available

Do not persist raw API responses by default. Store only approved normalized fields needed for the audit or drift use case. Provider-specific metrics retain provider-specific names unless equivalence is established and documented.

## 8. End-to-end integration sequence

1. Resolve an approved source and authorization.
2. Gather evidence with bounded network and cost controls.
3. Normalize into the host `AdapterResult` contract.
4. Classify the resulting data.
5. Persist only approved normalized fields with stable metric and payload schema versions.
6. Optionally write a cache envelope.
7. Compare only compatible verified snapshots.
8. Report active source, freshness, missing components, confidence, and blockers.

## 9. Network and provider failures

- Retry only transient transport failures and retryable HTTP statuses.
- Use bounded exponential backoff and honor bounded `Retry-After` values.
- Enforce timeouts and response-size limits.
- Do not retry authentication, permission, malformed-request, or normalization-contract failures as if transient.
- Sanitize errors so API keys and credential-bearing URLs do not reach logs or reports.
- A verified CrUX `NOT_FOUND` response means eligible field data is unavailable for that URL/form factor. It does not invalidate successful Lighthouse lab evidence.

## 10. Security, privacy, and outbound data

Data classes:

- `PUBLIC`: public pages and public listings.
- `CLIENT_CONFIDENTIAL`: first-party analytics, paid-provider output, screenshots, strategy, and evidence stores.
- `PERSONAL_DATA`: identifiers or user-level data requiring an approved purpose and handling rule.
- `SECRET`: keys, tokens, cookies, credentials, and signing material.

`SECRET` values are forbidden in cache and evidence payloads. Store `PERSONAL_DATA` only with an approved purpose, minimum fields, retention period, access rule, and deletion path.

Target validation rejects non-HTTP(S) schemes, embedded credentials, credential-like query parameters, nonstandard ports by default, DNS failures, and any resolved non-global address. Provider redirects remain HTTPS, use an exact approved endpoint, and cannot cross hosts.

These controls reduce common SSRF and accidental-secret risks but do not eliminate DNS rebinding or a third-party provider's independent resolution behavior. High-risk environments require egress controls or an approved URL proxy.

## 11. Migration, concurrency, and lifecycle

- Inspect `PRAGMA user_version` and actual columns before migration.
- Run migrations transactionally and roll back on failure.
- Additive migrations may preserve existing callers.
- Destructive or semantic migrations require backup, owner approval, and a tested rollback or export path.
- Never advance the database version before all migration steps succeed.
- Use WAL mode, a bounded busy timeout, deterministic ordering, and one transaction per write.
- Serialize connection use inside one store instance.
- Serialize first-use migration inside one process. Cross-process contention relies on SQLite locking and the configured timeout.
- Sustained multi-process write volume requires a queue or dedicated writer.

## 12. Integrity, retention, deletion, and backup

Every row stores:

1. A digest of canonical payload JSON.
2. A digest covering URL, metric group, timestamp, payload, payload schema, source, status, run ID, and scope.

Reads and comparisons verify both digests before decoding. Malformed JSON or hash mismatch is an integrity failure. Run SQLite `quick_check` plus payload/record verification before release, migration, or backup.

The hashes detect corruption and unsynchronized edits. They do not authenticate against a writer who can alter the database and recompute hashes. Authenticity requires a separately protected signature or append-only external log. The database is not encrypted by this module.

Retention rules:

- Define freshness and retention per metric group and data class.
- Purging may preserve the newest N snapshots per URL, metric group, and payload schema version.
- User- or policy-driven deletion must cover cache entries, database rows, exports, and governed backups.
- Backups inherit the same classification, access, retention, and deletion controls.

## 13. Duplicate and adversarial controls

Cache writers must use deterministic identities and atomic replacement so retries do not create competing cache files. The SQLite layer may retain repeated observations when they represent separate captures, but consumers must not present identical evidence records as independent corroboration. Challenge tests must cover payload and metadata tampering, malformed-but-rehashed JSON, schema mismatch, clock ties, partial writes, concurrent initialization, and stale-cache conflict with fresh evidence.

## 14. Minimum verification suite

Before host release, prove:

- migration from the original four-column schema
- canonical URL identity and secret-bearing URL rejection
- equal-timestamp ordering
- nested added/removed/changed drift and schema mismatch
- payload and metadata tampering detection
- malformed JSON handling
- retention and deletion
- concurrent writers and closed-store behavior
- PageSpeed and CrUX numeric parsing
- mobile-to-CrUX-`PHONE` mapping
- private-address and nonstandard-port rejection
- exact endpoint and same-host redirect enforcement
- retry, timeout, response-size, and secret-redaction behavior
- CrUX not-found, unavailable, and explicit-skip states

Unit tests must use fixtures or mocked transport. Live API testing is separate, opt-in, credential-controlled, and never required for deterministic unit success.

## 15. Known limitations

- The host `AdapterResult`, adapter registry, routing, retention policy, and drift-monitor implementation were not supplied.
- The package does not implement JSON cache-file reads/writes.
- Live provider behavior must be verified with opt-in credentials in the host environment; this contract does not prove provider availability.
- File-permission behavior varies by operating system.
- Threaded independent-connection concurrency was tested; sustained multi-process contention was not load-tested.
- Hashes provide corruption detection, not encryption or writer-proof authenticity.
