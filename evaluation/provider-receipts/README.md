# Capability certification receipts

This directory may contain sanitized `*.json` receipts conforming to
`schemas/capability-certification-receipt.schema.json`. A receipt is evidence for exactly one
command and never proves SEO outcomes, production readiness, or another capability.

Local receipts are `CANDIDATE` records only and cannot promote `LIVE_VERIFIED`. No authenticated
external issuer exists yet; labeling a locally created receipt as externally issued does not create
trust.

Do not create a passing receipt from fixtures. A passing receipt requires the explicit
`--execute-live` intent, the exact `LIVE_CERTIFY` confirmation, an authorized target, all required
offline and adverse checks, a real bounded provider observation, redacted provider and application
log evidence, and any required cost or write approval. Never commit credentials, response bodies,
client data, raw target identifiers, or personal data.

Receipts expire and are invalidated when their profile's relevant-source fingerprint changes.
Invalid, malformed, stale, future-dated, misbound, or expired receipts fail repository validation;
removing or expiring a receipt demotes the command to `LIVE_CAPABLE_NOT_VERIFIED`.
