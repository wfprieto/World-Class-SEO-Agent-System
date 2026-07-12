# Five-Minute Quick Start

```bash
python -m pip install -e .
seoctl --registry-check
seoctl system route "Run a full SEO audit" --domain https://example.com --business-type saas
seoctl integrations list
seoctl benchmark compare
```

## Credential-free checks

```bash
seoctl content quality --input page.txt
seoctl schema validate --file schema.json
seoctl links profile --input backlinks.csv
seoctl drift baseline --url https://example.com --input page-state.json
```

## One live integration

```bash
seoctl integrations preflight --provider dataforseo
```

Do not execute a metered call until the estimate and authorized ceiling are recorded. Remove credentials from the environment to disable an integration. Delete generated sidecars or local evidence only through the documented rollback path.