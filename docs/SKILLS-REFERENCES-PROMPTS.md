# Skills, References, and Prompt Production

Phase 4 replaces the hand-maintained skill index with generated metadata, adds packages for the 20 highest-priority skills, introduces a current reference registry, and composes content-production prompts from shared controls.

## Sources of truth

- Skill inventory: `skills/skill-catalog.json`
- Package mapping: `skills/package-registry.json`
- Procedure authority: `skills/deep-skill-procedures.md`
- Generated index: `skills/SKILL_INDEX.md`
- Reference metadata: `knowledge/reference-registry.json`
- Prompt composition: `prompts/prompt-manifest.json`

## Validation

```bash
python scripts/generate_skill_index.py --check
python scripts/validate_canonical_skill_consistency.py
python scripts/validate_reference_freshness.py
pytest -q tests/test_phase4_skill_reference_prompt_pack.py
```

Prompt composition produces instructions only. It does not retrieve evidence, generate claims, publish content, or bypass editorial approval.

## Rollback

Revert the phase commits. No database migration, credential, external write, or provider dependency is introduced.
