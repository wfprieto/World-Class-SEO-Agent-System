# Adapter Guide

Adapters connect SEO tools and exports to the runtime without tying the system to one vendor or one LLM.

## Contract

Every adapter follows the `SEOAdapter` protocol in `base.py`:

```python
class SEOAdapter(Protocol):
    name: str

    def fetch(self, **kwargs: Any) -> AdapterResult:
        ...
```

Every adapter returns `AdapterResult`:

```python
AdapterResult(
    source="durable source label",
    status="ok | needs-review | invalid | unavailable",
    data={},
    warnings=[]
)
```

## Implementation Rules

1. Keep credentials out of the repository.
2. Accept local exports whenever possible so tests can run without paid tools.
3. Normalize vendor-specific field names into stable data keys.
4. Treat missing data as `unavailable` or `needs-review`, never as clean.
5. Return warnings for stale, sampled, incomplete or ambiguous data.
6. Keep destructive actions out of adapters. Adapters fetch, parse and validate.
7. Add tests for every adapter path that the runtime can call.

## Live Adapter Pattern

Live adapters should:

1. Read credentials from environment variables or a secret manager.
2. Refresh or obtain tokens outside committed code.
3. Request the narrowest required scope.
4. Normalize the response into `AdapterResult`.
5. Handle pagination, rate limits and partial failures.
6. Include a local-export fallback for CI and development.

See `gsc_live_example.py` for a Google Search Console OAuth2 pattern. Google documents that Search Console API user-data requests use OAuth 2.0: https://developers.google.com/webmaster-tools/v1/how-tos/authorizing

## Runtime Usage

```powershell
python main.py "Run a technical crawl audit" --execute --tool crawler_csv=exports/crawl.csv
```

JSON arguments are supported:

```powershell
python main.py "Validate robots rules" --execute --tool robots_txt="{\"path\":\"exports/robots.txt\",\"user_agent\":\"Googlebot\"}"
```

## Adding a New Adapter

1. Create `adapters/my_tool.py`.
2. Implement `name` and `fetch`.
3. Return `AdapterResult`.
4. Add the adapter to `adapters/registry.py`.
5. Add at least one test in `tests/test_adapters.py`.
6. Document the tool in `TOOLS.md` when it is a recommended connection.
