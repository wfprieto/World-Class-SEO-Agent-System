# Remediation CI Diagnostic

Commit: 9239552a54c505bbcf23d9c2f2dab9b68b694fbd
Generated: 2026-07-13T18:55:29Z

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
  "status": "ok",
  "claims": 38
}

EXIT_CODE=0
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
........................................................................ [ 62%]
........................................................................ [ 83%]
........................................................                 [100%]
=============================== warnings summary ===============================
runtime/schema_registry.py:9
runtime/schema_registry.py:9
  /home/runner/work/World-Class-SEO-Agent-System/World-Class-SEO-Agent-System/runtime/schema_registry.py:9: DeprecationWarning: jsonschema.RefResolver is deprecated as of v4.18.0, in favor of the https://github.com/python-jsonschema/referencing library, which provides more compliant referencing behavior as well as more flexible APIs for customization. A future release will remove RefResolver. Please file a feature request (on referencing) if you are missing an API for the kind of customization you need.
    from jsonschema import Draft202012Validator, RefResolver

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
344 passed, 2 warnings in 4.02s

EXIT_CODE=0
```

## Command
```text
python -m mypy runtime seoctl integrations adapters
```
## Output
```text
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
Found 51 errors in 31 files (checked 89 source files)

EXIT_CODE=1
```

