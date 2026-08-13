# Capability certification

`governance/capability-certification.json` is the machine-readable authority for live-capability
certification profiles. `seoctl/capability_certification.py` is the only receipt validator and
promotion authority. This control plane is static and offline: it never calls a provider, reads a
credential value into output, or creates a passing receipt.

## Proof boundary

`LIVE_CAPABLE_NOT_VERIFIED` means an executable network path exists but lacks current live proof.
`LIVE_VERIFIED` requires a current, schema-valid, sanitized receipt whose issuer was authenticated
by a separately implemented external attestation verifier. It does not prove complete coverage, SEO effectiveness,
ranking, traffic, conversion, production readiness, or another command.

This repository currently has no authenticated external issuer or attestation verifier. Therefore
`trusted_issuers` is deliberately empty: locally authored and self-asserted external receipts may
validate as structural candidates, but they cannot promote any command to `LIVE_VERIFIED`.

Every network-capable command belongs to exactly one certification profile. A profile fixes the
provider, transport, side-effect class, credential-name alternatives, relevant source files,
responsible owner, and authorization requirements. A receipt binds to an exact repository commit;
the validator reconstructs its relevant-source fingerprint from that commit and compares it with
the current files. Each typed evidence item is confined to the receipt's evidence directory,
individually hashed, bound to the same tested commit, and prohibited from reusing a path or hash.

## Required live process

A separate operator-controlled runner must complete all of these steps before proposing a receipt:

1. Confirm prerequisites without displaying credential values.
2. Require the explicit `--execute-live` intent and exact `LIVE_CERTIFY` confirmation.
3. Record authorization as a SHA-256 identifier for the approved target, never raw sensitive data.
4. Obtain cost approval when the profile requires it and separate write approval for a write path.
5. Pass fixture or replay checks and the profile's adverse-state tests.
6. Perform one bounded live probe through the real adapter and transport.
7. Preserve sanitized provider and application log evidence with a safe request identifier.
8. Run the repository redaction check, calculate the relevant-source fingerprint and receipt digest,
   and submit the receipt for review.

Fixtures, mocked clients, environment-variable presence, successful authentication alone, or a
provider HTTP success without normalized evidence and logs cannot produce `LIVE_VERIFIED`.

## Validation and expiry

Run:

```bash
python scripts/validate_capability_certification.py
python scripts/generate_capability_evidence_registry.py --check
python scripts/validate_product_contract.py
seoctl system doctor
```

The validator rejects unknown and duplicate profiles, incomplete live-command coverage, unsafe
paths, symlinks, schema drift, legacy five-field receipts, extra fields, mismatched capability or
provider bindings, altered digests, changed implementation fingerprints, missing evidence files,
credential-shaped text, future timestamps, excessive lifetimes, expiry, and missing cost/write
approval. A missing or expired receipt leaves the capability unverified; an invalid committed
receipt fails validation so evidence corruption cannot be silently ignored.

Repository CI validates profiles and committed receipts but must not execute provider calls. Live
certification is an owner-authorized operation using an approved target and appropriately scoped
credentials. No passing receipt is included by default.
