# Installation

## Supported environment

- Python 3.11 or 3.13
- Windows or Ubuntu
- Git

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

## Optional browser pack

```bash
python -m pip install -e '.[render]'
playwright install chromium
seoctl render health
```

Optional providers remain disabled until their credential and cost preflight passes. Never commit credentials, `.seo-cache`, database files, exports, or generated evidence.