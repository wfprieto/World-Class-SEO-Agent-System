# Troubleshooting

## `NOT_CONFIGURED`
Run `seoctl integrations preflight --provider <id>` and set every required environment variable. Credential presence is not cost approval.

## Browser unavailable
Install the optional render extra and Chromium, then run `seoctl render health`. Network-blocked browser installation must remain `BLOCKED_BY_NETWORK`.

## Drift says insufficient history
Create at least two compatible snapshots. Missing history is not “no drift.”

## Registry or generated docs stale
Run the corresponding generator and commit both the canonical metadata and generated artifact.

## Clean wheel cannot find repository assets
Use a source checkout for the complete operating system until packaged data files are verified in the release candidate.

## CI status missing
Treat the gate as `NOT_OBSERVABLE`; do not infer success from the absence of a failure.