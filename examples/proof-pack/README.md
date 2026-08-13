# Proof Pack

This folder is the public proof index for the repository.

It does not contain private client data, provider credentials, or live-site claims. It connects the repository's synthetic, anonymized, and fixture-backed examples into one auditable proof layer.

## Purpose

The proof pack shows that the system can demonstrate:

- a reproducible golden technical audit
- bad SEO failure-mode fixtures
- anonymized search performance and Core Web Vitals exports
- product-proof intelligence fixtures
- schema validation examples
- plain-language stakeholder reporting

Each proof unit names what it proves, what it does not prove, the target agents, the source files, and the validation path.

## Canonical Manifest

Use `proof-pack-manifest.json` as the source of truth for proof-pack coverage.

Every entry must:

- point to files that exist
- declare `fixture_is_live_proof: false`
- name target agents
- name validation commands or tests
- avoid secrets, credentials, account IDs, property IDs, and client-identifying data

## Safety Boundary

The proof pack is evidence for repository behavior and example quality. It is not evidence of live rankings, live indexing, live analytics, live Search Console access, provider authentication, or automatic website mutation.
