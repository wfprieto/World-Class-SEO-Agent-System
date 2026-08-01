# Installation

Release verification and maintainer publication steps are documented in `docs/RELEASING.md`.

## Supported environment

- CPython 3.11, 3.12, or 3.13 (all three versions are CI-certified)
- Windows or Ubuntu
- Git

Python 3.14 and later are not currently declared compatible. Supporting a new
minor version requires adding it to the CI matrix and passing the full repository
and clean-wheel certification gates before changing `requires-python`.

## Core install

```bash
git clone https://github.com/wfprieto/World-Class-SEO-Agent-System.git
cd World-Class-SEO-Agent-System
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
seoctl --registry-check
```

## Development install

```bash
python -m pip install -r requirements-dev.txt
python -m compileall -q .
pytest -q
```

`requirements-dev.in` is the canonical list of direct development tools.
`requirements-dev.txt` is its exact, transitive pip-compile lock and is the file
used by CI and dependency auditing. To update it on a supported Python version:

```bash
python -m pip install "pip-tools>=7.5,<8"
python -m piptools compile --strip-extras --output-file requirements-dev.txt requirements-dev.in
python scripts/validate_dependency_lock.py
```

Commit the input and generated lock together. Dependabot may update pinned
packages in `requirements-dev.txt`; reviewers must still confirm that the direct
requirement remains allowed by `requirements-dev.in` and that all CI versions
resolve and pass. Do not generate the lock with an unsupported interpreter.

## Optional browser pack

```bash
python -m pip install -e '.[render]'
playwright install chromium
seoctl render health
```

Optional providers remain disabled until their credential and cost preflight passes. Never commit credentials, `.seo-cache`, database files, exports, or generated evidence.

Fixture and mocked transport tests prove local contracts only. A live provider or
browser-network path remains `BLOCKED_BY_EXTERNAL_VERIFICATION` until an authorized
operator verifies credentials, provider response, logs, and resulting user-visible
evidence against the intended environment.
