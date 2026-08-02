# Command and Evidence Contracts

`seoctl/command-registry.json` plus its approved overlay remain the source of command identity, path, handler, owner, skills, execution class, and network class. `seoctl.command_contracts` derives exactly one runtime contract for every effective command and rejects missing, stale, duplicate, or contradictory mappings.

Each command contract binds:

- one callable handler with exactly one family-level definition;
- `schemas/seoctl-command-input.schema.json` and `schemas/seoctl-command-output.schema.json`;
- the executable reconciliation tests in `tests/test_command_contracts.py`;
- `DETERMINISTIC` evidence mode for commands with no network access and `LIVE_CAPABLE` for provider or live-capable commands;
- typed `INPUT_ERROR`, `UNAVAILABLE`, `BLOCKED`, and `FAILED` states with exit codes 2 through 5.

The contract does not claim that a live-capable command was live-verified. Provider, deployed, and operational evidence remain separate proof classes.

`runtime.finding_registry.FindingRegistry` reconciles each finding reference against the output evidence inventory. Its `evidence_state` is one of `VALID`, `MISSING`, `STALE`, `DUPLICATE`, or `CONTRADICTORY`; higher-risk states take precedence and are never silently converted to accepted evidence. Non-valid evidence produces `EVIDENCE_REVIEW`, while contradictory specialist conclusions retain the existing `CONFLICTED` lifecycle state.

Run the bounded checks with:

```text
python scripts/validate_command_contracts.py
python -m pytest tests/test_command_contracts.py tests/test_world_class_runtime.py
python -m ruff check seoctl/command_contracts.py runtime/finding_registry.py tests/test_command_contracts.py
python -m mypy seoctl/command_contracts.py runtime/finding_registry.py
```
