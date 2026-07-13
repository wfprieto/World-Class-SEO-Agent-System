# Remediation CI Diagnostic

Commit: a425f59f579d9242d28de3b69aff6e4d076b5869
Generated: 2026-07-13T18:36:31Z

## Command
```text
seoctl --registry-check
```
## Output
```text
{
  "command": "registry.check",
  "data": {
    "agents": 25,
    "commands": 67,
    "errors": []
  },
  "error": null,
  "status": "ok",
  "warnings": []
}

EXIT_CODE=0
```

## Command
```text
python scripts/validate_seo_claims.py
```
## Output
```text
{
  "status": "failed",
  "failures": [
    "internal-link-study: invalid evidence class 'LAGRE_SCALE_OBSERVATIONAL'"
  ]
}

EXIT_CODE=1
```

## Command
```text
python scripts/validate_product_proof_program.py
```
## Output
```text
{
  "status": "PASS",
  "passes": [
    {
      "pass": "1",
      "name": "Requirement identity",
      "status": "PASS",
      "detail": "29 unique requirements"
    },
    {
      "pass": "2",
      "name": "Source traceability",
      "status": "PASS",
      "detail": "Every requirement names report sections"
    },
    {
      "pass": "3",
      "name": "Status vocabulary",
      "status": "PASS",
      "detail": "No ambiguous completion state"
    },
    {
      "pass": "4",
      "name": "Implemented artifacts",
      "status": "PASS",
      "detail": "Every implemented requirement has existing artifacts"
    },
    {
      "pass": "5",
      "name": "Implemented tests",
      "status": "PASS",
      "detail": "Every implemented requirement names tests"
    },
    {
      "pass": "6",
      "name": "External blockers explicit",
      "status": "PASS",
      "detail": "No deferred requirement is silently omitted"
    },
    {
      "pass": "7",
      "name": "Claim registry",
      "status": "PASS",
      "detail": "knowledge/seo-claim-registry.json exists"
    },
    {
      "pass": "8",
      "name": "Deprecation registry",
      "status": "PASS",
      "detail": "knowledge/deprecation-registry.json exists"
    },
    {
      "pass": "9",
      "name": "Primary source pack",
      "status": "PASS",
      "detail": "knowledge/primary-source-technical-seo.md exists"
    },
    {
      "pass": "10",
      "name": "Bounded crawler",
      "status": "PASS",
      "detail": "integrations/product_proof/crawler.py exists"
    },
    {
      "pass": "11",
      "name": "Rule engine",
      "status": "PASS",
      "detail": "integrations/product_proof/rules.py exists"
    },
    {
      "pass": "12",
      "name": "Root-cause reporting",
      "status": "PASS",
      "detail": "integrations/product_proof/report.py exists"
    },
    {
      "pass": "13",
      "name": "CLI product path",
      "status": "PASS",
      "detail": "seoctl/audit_cli.py exists"
    },
    {
      "pass": "14",
      "name": "Command overlay",
      "status": "PASS",
      "detail": "seoctl/command-registry-overlay.json exists"
    },
    {
      "pass": "15",
      "name": "Capability overlay",
      "status": "PASS",
      "detail": "orchestration/product-proof-capability-overlay.json exists"
    },
    {
      "pass": "16",
      "name": "Artifact manifest",
      "status": "PASS",
      "detail": "Service writes a manifest"
    },
    {
      "pass": "17",
      "name": "Agent contribution ledger",
      "status": "PASS",
      "detail": "Contribution artifact is mandatory"
    },
    {
      "pass": "18",
      "name": "Skill convergence",
      "status": "PASS",
      "detail": "Skill and procedure extension exist"
    },
    {
      "pass": "19",
      "name": "Feedback loops",
      "status": "PASS",
      "detail": "Learning and optimization records exist"
    },
    {
      "pass": "20",
      "name": "Release truth",
      "status": "PASS",
      "detail": "External proof remains blocked and explicit: R24, R25"
    }
  ],
  "failures": [],
  "implemented": 27,
  "planned_next_increment": 0,
  "blocked_external_evidence": 2,
  "release_approved": false,
  "note": "Implementation validation does not satisfy authorized live-site, external-review, CI-observability, or public-release gates."
}

EXIT_CODE=0
```

## Command
```text
python scripts/validate_product_claims.py
```
## Output
```text
{
  "status": "ok",
  "failures": []
}

EXIT_CODE=0
```

## Command
```text
python -m pytest -q
```
## Output
```text
........................................................................ [ 20%]
........................................................................ [ 41%]
.............................F.......................................... [ 62%]
.........................F......................F.F..................... [ 83%]
.....F.............................F....................                 [100%]
=================================== FAILURES ===================================
_ test_local_inventory_proves_current_runtime_baseline_without_hardcoded_file_counts _

    def test_local_inventory_proves_current_runtime_baseline_without_hardcoded_file_counts():
        inventory = inventory_repo(ROOT)
        assert inventory["agent_files"] == 25
>       assert inventory["indexed_skills"] >= 80
E       assert 69 >= 80

tests/test_comparative_rebaseline.py:34: AssertionError
_____________ test_skill_catalog_and_generated_index_are_canonical _____________

    def test_skill_catalog_and_generated_index_are_canonical():
        catalog = _json("skills/skill-catalog.json")
        skills = [skill for category in catalog["categories"] for skill in category["skills"]]
>       assert len(skills) == 84
E       AssertionError: assert 89 == 84
E        +  where 89 = len(['full-site-audit', 'product-proof-technical-audit', 'seo-diagnostic-stack-design', 'technical-audit', 'crawl-map', 'indexation-reality-check', ...])

tests/test_phase4_skill_reference_prompt_pack.py:24: AssertionError
________________ test_claim_registry_and_deprecations_validate _________________

    def test_claim_registry_and_deprecations_validate():
>       assert validate(ROOT, as_of=date(2026,7,12)) == []
E       assert ["internal-li...SERVATIONAL'"] == []
E         
E         Left contains one more item: "internal-link-study: invalid evidence class 'LAGRE_SCALE_OBSERVATIONAL'"
E         
E         Full diff:
E         - []
E         + [
E         +     "internal-link-study: invalid evidence class 'LAGRE_SCALE_OBSERVATIONAL'",
E         + ]

tests/test_product_proof_technical_audit.py:63: AssertionError
______________________ test_cli_claims_and_audit_fixture _______________________

tmp_path = PosixPath('/tmp/pytest-of-runner/pytest-0/test_cli_claims_and_audit_fixt0')

    def test_cli_claims_and_audit_fixture(tmp_path: Path):
        claims, code = run(['knowledge','claims','--evidence-class','UNVERIFIED'])
        assert code == 0
        assert claims['data']['count'] >= 2
        check, code = run(['knowledge','validate'])
>       assert code == 0 and check['status']=='ok'
E       assert (5 == 0)

tests/test_product_proof_technical_audit.py:96: AssertionError
_________________ test_every_indexed_skill_has_deep_procedure __________________

    def test_every_indexed_skill_has_deep_procedure():
        index = (ROOT / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
        procedures = (ROOT / "skills" / "deep-skill-procedures.md").read_text(encoding="utf-8")
        indexed_skills = set(re.findall(r"`([a-z0-9-]+)`", index))
        procedure_skills = set(re.findall(r"^## ([a-z0-9-]+)$", procedures, re.MULTILINE))
>       assert not indexed_skills - procedure_skills
E       AssertionError: assert not ({'accessibility-audit', 'agentic-commerce-readiness-check', 'ai-citation-opportunity-map', 'ai-retrieval-timeout-audit', 'analytics-synthesis', 'anti-ai-public-writing', ...} - {'accessibility-audit', 'agentic-commerce-readiness-check', 'analytics-synthesis', 'anti-ai-public-writing', 'backlink-gap', 'backlink-profile', ...})

tests/test_repository_semantics.py:44: AssertionError
_____________ test_command_documentation_matches_registry_exactly ______________

    def test_command_documentation_matches_registry_exactly():
        documented = (ROOT / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
>       assert documented == render()
E       assert '# seoctl Com...oval gates.\n' == '# seoctl Com...oval gates.\n'
E         
E         Skipping 5486 identical leading characters in diff, use -v to show
E         + | `seoctl schema validate` | SEO Technical Agent | `schema-detect-validate-generate` | `none` |
E         - | `seoctl render screenshot` | SEO Diagnostic Infrastructure Agent | `rendered-visual-audit` | `live_optional` |
E         - | `seoctl report render` | SEO Output Report Agent | `plain-language-seo-report` | `none` |
E           | `seoctl schema detect` | SEO Technical Agent | `schema-detect-validate-generate` | `live_optional` |
E           | `seoctl schema generate` | Senior SEO Engineer Agent | `schema-detect-validate-generate` | `none` |
E         - | `seoctl schema validate` | SEO Technical Agent | `schema-detect-validate-generate` | `none` |
E           | `seoctl system route` | SEO Scrummaster Agent | `request-routing` | `none` |
E           | `seoctl system run` | SEO Full Audit/Analyst Agent | `full-site-audit` | `provider_optional` |
E           | `seoctl technical cwv` | SEO Diagnostic Infrastructure Agent | `core-web-vitals-triage` | `live_optional` |
E           | `seoctl technical hreflang` | International & Multilingual SEO Agent | `hreflang-audit` | `live_optional` |
E           | `seoctl technical indexability` | SEO Technical Agent | `indexation-reality-check` | `live_optional` |
E           | `seoctl technical preload` | SEO Technical Agent | `core-web-vitals-triage` | `live_optional` |
E           | `seoctl technical redirect-chain` | SEO Technical Agent | `technical-audit` | `live_optional` |
E           | `seoctl technical robots` | SEO Technical Agent | `technical-audit` | `live_optional` |
E           | `seoctl technical sitemap` | SEO Technical Agent | `technical-audit` | `live_optional` |
E           
E           ## Stable exit codes
E           
E         - | Code | Meaning |
E         ?  -
E         + |Code | Meaning |
E           |---:|---|
E         - | 0 | Completed successfully or truthfully partial without a hard failure |
E         ?                                                                         -
E         + | 0 | Completed successfully or truthfully partial without a hard failur |
E           | 2 | Invalid or missing operator input |
E           | 3 | Optional capability or provider unavailable |
E           | 4 | Blocked by evidence, authorization, privacy or governance gate |
E           | 5 | Execution or validation failure |
E           
E           Every command writes one JSON envelope with `command`, `status`, `data`, `warnings`, and `error`.
E           
E           ## Examples
E           
E           ```bash
E           python -m seoctl --registry-check
E           python -m seoctl audit technical --url https://example.com --output audit-runs/example-com
E           python -m seoctl knowledge validate
E           python -m seoctl knowledge product-claims --status BLOCKED
E           python -m seoctl intelligence ai-timeouts --log access.log --server-stack nginx
E           python -m seoctl system route "Run a full SEO audit" --domain https://example.com --business-type saas
E           python -m seoctl system run "Build an SEO content brief" --domain https://example.com --business-type saas
E           python -m seoctl profile resolve --signal cart --signal checkout --signal visible_price
E           python -m seoctl cluster serp --serps examples/serps.json
E           python -m seoctl privacy consent --config consent-fixture.json
E           python -m seoctl benchmark compare
E           ```
E           
E           Commands that require live providers remain optional and must preserve runtime budgets, credential redaction, and approval gates.

tests/test_seoctl_docs.py:10: AssertionError
=============================== warnings summary ===============================
runtime/schema_registry.py:9
runtime/schema_registry.py:9
  /home/runner/work/World-Class-SEO-Agent-System/World-Class-SEO-Agent-System/runtime/schema_registry.py:9: DeprecationWarning: jsonschema.RefResolver is deprecated as of v4.18.0, in favor of the https://github.com/python-jsonschema/referencing library, which provides more compliant referencing behavior as well as more flexible APIs for customization. A future release will remove RefResolver. Please file a feature request (on referencing) if you are missing an API for the kind of customization you need.
    from jsonschema import Draft202012Validator, RefResolver

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_comparative_rebaseline.py::test_local_inventory_proves_current_runtime_baseline_without_hardcoded_file_counts - assert 69 >= 80
FAILED tests/test_phase4_skill_reference_prompt_pack.py::test_skill_catalog_and_generated_index_are_canonical - AssertionError: assert 89 == 84
 +  where 89 = len(['full-site-audit', 'product-proof-technical-audit', 'seo-diagnostic-stack-design', 'technical-audit', 'crawl-map', 'indexation-reality-check', ...])
FAILED tests/test_product_proof_technical_audit.py::test_claim_registry_and_deprecations_validate - assert ["internal-li...SERVATIONAL'"] == []
  
  Left contains one more item: "internal-link-study: invalid evidence class 'LAGRE_SCALE_OBSERVATIONAL'"
  
  Full diff:
  - []
  + [
  +     "internal-link-study: invalid evidence class 'LAGRE_SCALE_OBSERVATIONAL'",
  + ]
FAILED tests/test_product_proof_technical_audit.py::test_cli_claims_and_audit_fixture - assert (5 == 0)
FAILED tests/test_repository_semantics.py::test_every_indexed_skill_has_deep_procedure - AssertionError: assert not ({'accessibility-audit', 'agentic-commerce-readiness-check', 'ai-citation-opportunity-map', 'ai-retrieval-timeout-audit', 'analytics-synthesis', 'anti-ai-public-writing', ...} - {'accessibility-audit', 'agentic-commerce-readiness-check', 'analytics-synthesis', 'anti-ai-public-writing', 'backlink-gap', 'backlink-profile', ...})
FAILED tests/test_seoctl_docs.py::test_command_documentation_matches_registry_exactly - assert '# seoctl Com...oval gates.\n' == '# seoctl Com...oval gates.\n'
  
  Skipping 5486 identical leading characters in diff, use -v to show
  + | `seoctl schema validate` | SEO Technical Agent | `schema-detect-validate-generate` | `none` |
  - | `seoctl render screenshot` | SEO Diagnostic Infrastructure Agent | `rendered-visual-audit` | `live_optional` |
  - | `seoctl report render` | SEO Output Report Agent | `plain-language-seo-report` | `none` |
    | `seoctl schema detect` | SEO Technical Agent | `schema-detect-validate-generate` | `live_optional` |
    | `seoctl schema generate` | Senior SEO Engineer Agent | `schema-detect-validate-generate` | `none` |
  - | `seoctl schema validate` | SEO Technical Agent | `schema-detect-validate-generate` | `none` |
    | `seoctl system route` | SEO Scrummaster Agent | `request-routing` | `none` |
    | `seoctl system run` | SEO Full Audit/Analyst Agent | `full-site-audit` | `provider_optional` |
    | `seoctl technical cwv` | SEO Diagnostic Infrastructure Agent | `core-web-vitals-triage` | `live_optional` |
    | `seoctl technical hreflang` | International & Multilingual SEO Agent | `hreflang-audit` | `live_optional` |
    | `seoctl technical indexability` | SEO Technical Agent | `indexation-reality-check` | `live_optional` |
    | `seoctl technical preload` | SEO Technical Agent | `core-web-vitals-triage` | `live_optional` |
    | `seoctl technical redirect-chain` | SEO Technical Agent | `technical-audit` | `live_optional` |
    | `seoctl technical robots` | SEO Technical Agent | `technical-audit` | `live_optional` |
    | `seoctl technical sitemap` | SEO Technical Agent | `technical-audit` | `live_optional` |
    
    ## Stable exit codes
    
  - | Code | Meaning |
  ?  -
  + |Code | Meaning |
    |---:|---|
  - | 0 | Completed successfully or truthfully partial without a hard failure |
  ?                                                                         -
  + | 0 | Completed successfully or truthfully partial without a hard failur |
    | 2 | Invalid or missing operator input |
    | 3 | Optional capability or provider unavailable |
    | 4 | Blocked by evidence, authorization, privacy or governance gate |
    | 5 | Execution or validation failure |
    
    Every command writes one JSON envelope with `command`, `status`, `data`, `warnings`, and `error`.
    
    ## Examples
    
    ```bash
    python -m seoctl --registry-check
    python -m seoctl audit technical --url https://example.com --output audit-runs/example-com
    python -m seoctl knowledge validate
    python -m seoctl knowledge product-claims --status BLOCKED
    python -m seoctl intelligence ai-timeouts --log access.log --server-stack nginx
    python -m seoctl system route "Run a full SEO audit" --domain https://example.com --business-type saas
    python -m seoctl system run "Build an SEO content brief" --domain https://example.com --business-type saas
    python -m seoctl profile resolve --signal cart --signal checkout --signal visible_price
    python -m seoctl cluster serp --serps examples/serps.json
    python -m seoctl privacy consent --config consent-fixture.json
    python -m seoctl benchmark compare
    ```
    
    Commands that require live providers remain optional and must preserve runtime budgets, credential redaction, and approval gates.
6 failed, 338 passed, 2 warnings in 4.31s

EXIT_CODE=1
```

## Command
```text
python -m mypy runtime seoctl integrations adapters
```
## Output
```text
adapters/gbp_local.py:18: error: Need type annotation for "duplicate_names" (hint: "duplicate_names: dict[<type>, <type>] = ...")  [var-annotated]
integrations/technical/browser.py:159: error: Unused "type: ignore" comment  [unused-ignore]
integrations/product_proof/intelligence.py:56: error: Need type annotation for "ai_requests"  [var-annotated]
integrations/product_proof/intelligence.py:56: error: Need type annotation for "statuses"  [var-annotated]
integrations/product_proof/intelligence.py:56: error: Need type annotation for "path_counts"  [var-annotated]
integrations/extensions/providers.py:98: error: Cannot call function of unknown type  [operator]
adapters/evidence_store.py:431: error: Argument 1 to "int" has incompatible type "int | None"; expected "str | Buffer | SupportsInt | SupportsIndex | SupportsTrunc"  [arg-type]
integrations/content_intelligence/adapters.py:36: error: Cannot call function of unknown type  [operator]
adapters/page_drift.py:40: error: Name "_sha256" already defined (possibly by an import)  [no-redef]
adapters/page_drift.py:52: error: Argument 1 to "_sha256" has incompatible type "Any | None"; expected "str"  [arg-type]
adapters/page_drift.py:53: error: Argument 1 to "_sha256" has incompatible type "Any | None"; expected "str"  [arg-type]
adapters/rendered_page.py:163: error: Need type annotation for "headers" (hint: "headers: dict[<type>, <type>] = ...")  [var-annotated]
integrations/technical/http.py:23: error: Unused "type: ignore" comment  [unused-ignore]
integrations/google/client.py:75: error: Unused "type: ignore" comment  [unused-ignore]
integrations/extensions/indexnow.py:24: error: Unused "type: ignore" comment  [unused-ignore]
integrations/authority_media/transport.py:32: error: Unused "type: ignore" comment  [unused-ignore]
integrations/product_proof/crawler.py:70: error: Incompatible types in assignment (expression has type "str | None", variable has type "str")  [assignment]
adapters/google_pagespeed_live.py:235: error: Argument "query" to "request" of "GoogleJsonClient" has incompatible type "dict[str, str | None]"; expected "dict[str, str | int | None] | None"  [arg-type]
adapters/google_pagespeed_live.py:235: note: "dict" is invariant -- see https://mypy.readthedocs.io/en/stable/common_issues.html#variance
adapters/google_pagespeed_live.py:235: note: Consider using "Mapping" instead, which is covariant in the value type
integrations/authority_media/services.py:413: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:419: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:420: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:421: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:422: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:423: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:424: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:425: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:439: error: Item "None" of "Any | dict[Any, Any] | None" has no attribute "get"  [union-attr]
integrations/authority_media/services.py:608: error: Dict entry 2 has incompatible type "str": "list[str]"; expected "str": "str"  [dict-item]
integrations/product_proof/rules.py:23: error: Need type annotation for "counts"  [var-annotated]
integrations/technical/inspection.py:62: error: Unused "type: ignore" comment  [unused-ignore]
integrations/google/sitemaps.py:78: error: Argument "query" to "request" of "GoogleJsonClient" has incompatible type "dict[str, str]"; expected "dict[str, str | int | None] | None"  [arg-type]
integrations/google/sitemaps.py:78: note: "dict" is invariant -- see https://mypy.readthedocs.io/en/stable/common_issues.html#variance
integrations/google/sitemaps.py:78: note: Consider using "Mapping" instead, which is covariant in the value type
integrations/authority_media/adapters.py:42: error: Cannot call function of unknown type  [operator]
integrations/authority_media/adapters.py:61: error: Cannot call function of unknown type  [operator]
integrations/technical/adapters.py:74: error: Cannot call function of unknown type  [operator]
integrations/product_proof/adapters.py:45: error: Cannot call function of unknown type  [operator]
runtime/llm.py:123: error: Argument 1 to "_approved_base_url" has incompatible type "str | None"; expected "str"  [arg-type]
runtime/llm.py:150: error: Argument "model" to "LLMResponse" has incompatible type "str | None"; expected "str"  [arg-type]
runtime/llm.py:223: error: Argument "model" to "LLMResponse" has incompatible type "str | None"; expected "str"  [arg-type]
runtime/llm.py:266: error: Incompatible return value type (got "EchoLLMClient", expected "LLMClient")  [return-value]
runtime/llm.py:266: note: Following member(s) of "EchoLLMClient" have conflicts:
runtime/llm.py:266: note:     Expected:
runtime/llm.py:266: note:         def stream(self, messages: list[LLMMessage]) -> Coroutine[Any, Any, AsyncIterator[str]]
runtime/llm.py:266: note:     Got:
runtime/llm.py:266: note:         def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]
runtime/llm.py:268: error: Incompatible return value type (got "OpenAICompatibleClient", expected "LLMClient")  [return-value]
runtime/llm.py:268: note: Following member(s) of "OpenAICompatibleClient" have conflicts:
runtime/llm.py:268: note:     model: expected "str", got "str | None"
runtime/llm.py:268: note:     Expected:
runtime/llm.py:268: note:         def stream(self, messages: list[LLMMessage]) -> Coroutine[Any, Any, AsyncIterator[str]]
runtime/llm.py:268: note:     Got:
runtime/llm.py:268: note:         def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]
runtime/llm.py:270: error: Incompatible return value type (got "AnthropicClient", expected "LLMClient")  [return-value]
runtime/llm.py:270: note: Following member(s) of "AnthropicClient" have conflicts:
runtime/llm.py:270: note:     model: expected "str", got "str | None"
runtime/llm.py:270: note:     Expected:
runtime/llm.py:270: note:         def stream(self, messages: list[LLMMessage]) -> Coroutine[Any, Any, AsyncIterator[str]]
runtime/llm.py:270: note:     Got:
runtime/llm.py:270: note:         def stream(self, messages: list[LLMMessage]) -> AsyncIterator[str]
runtime/structured_output.py:173: error: Name "errors" already defined on line 148  [no-redef]
runtime/structured_output.py:192: error: Incompatible types in assignment (expression has type "None", variable has type "dict[str, Any]")  [assignment]
runtime/tools.py:80: error: Item "object" of "Any | object" has no attribute "fetch"  [union-attr]
runtime/executor.py:195: error: "Coroutine[Any, Any, AsyncIterator[str]]" has no attribute "__aiter__" (not async iterable)  [attr-defined]
runtime/executor.py:195: note: Maybe you forgot to use "await"?
seoctl/cli.py:41: error: Argument 1 to "asdict" has incompatible type "DataclassInstance | type[DataclassInstance]"; expected "DataclassInstance"  [arg-type]
seoctl/technical_cli.py:25: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/intelligence_cli.py:17: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/extensions_cli.py:31: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/authority_cli.py:21: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/audit_cli.py:23: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/content_cli.py:36: error: Unused "type: ignore" comment  [unused-ignore]
Found 52 errors in 32 files (checked 89 source files)

EXIT_CODE=1
```

