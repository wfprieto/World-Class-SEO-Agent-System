# Full Mypy Diagnostic

Commit: b371faaa6b4c651fe1b064adcbd4aa661af715a6
Generated: 2026-07-13T21:15:36Z

## Mypy
```text
integrations/technical/browser.py:159: error: Unused "type: ignore" comment  [unused-ignore]
integrations/product_proof/intelligence.py:56: error: Need type annotation for "ai_requests"  [var-annotated]
integrations/product_proof/intelligence.py:56: error: Need type annotation for "statuses"  [var-annotated]
integrations/product_proof/intelligence.py:56: error: Need type annotation for "path_counts"  [var-annotated]
adapters/evidence_store.py:431: error: Argument 1 to "int" has incompatible type "int | None"; expected "str | Buffer | SupportsInt | SupportsIndex | SupportsTrunc"  [arg-type]
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
integrations/product_proof/adapters.py:45: error: Cannot call function of unknown type  [operator]
seoctl/cli.py:41: error: Argument 1 to "asdict" has incompatible type "DataclassInstance | type[DataclassInstance]"; expected "DataclassInstance"  [arg-type]
seoctl/technical_cli.py:25: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/intelligence_cli.py:17: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/extensions_cli.py:31: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/authority_cli.py:21: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/audit_cli.py:23: error: Unused "type: ignore" comment  [unused-ignore]
seoctl/content_cli.py:36: error: Unused "type: ignore" comment  [unused-ignore]
Found 36 errors in 23 files (checked 89 source files)

EXIT_CODE=1
```

## Pytest
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
344 passed, 2 warnings in 4.21s

EXIT_CODE=0
```
