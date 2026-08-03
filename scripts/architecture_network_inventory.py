"""Exact transport-policy inventory checks for direct network sinks."""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Any

EXPECTED_NETWORK_TRANSPORTS: dict[str, dict[str, str]] = {
    "adapters/rendered_page.py": {
        "policy": "PUBLIC_RENDERED_PAGE",
        "delegates_to": (
            "integrations.technical.http.BoundedHttpClient + "
            "security.url_safety.validate_public_url"
        ),
    },
    "security/url_safety.py": {
        "policy": "PUBLIC_URL_SAFETY",
        "delegates_to": "security.url_safety.validate_public_url",
    },
    "integrations/authority_media/transport.py": {
        "policy": "APPROVED_HOST_BOUNDED_HTTP",
        "delegates_to": "integrations.authority_media.transport.BoundedTransport",
    },
    "integrations/extensions/indexnow.py": {
        "policy": "NO_REDIRECT_PUBLIC_MUTATION",
        "delegates_to": "integrations.extensions.indexnow.NoRedirect",
    },
    "integrations/google/client.py": {
        "policy": "GOOGLE_API_BOUNDED_HTTP",
        "delegates_to": "integrations.google.client",
    },
    "integrations/technical/browser.py": {
        "policy": "PUBLIC_BROWSER_REQUEST_GUARD",
        "delegates_to": "integrations.technical.browser",
    },
    "integrations/technical/http.py": {
        "policy": "PUBLIC_WEB_EVERY_HOP",
        "delegates_to": "integrations.technical.http.BoundedHttpClient",
    },
    "runtime/llm.py": {
        "policy": "CONFIGURED_LLM_ENDPOINT_BOUNDED_HTTP",
        "delegates_to": "runtime.llm",
    },
}


def scan_modules(
    root: Path,
    packages: list[str],
    *,
    module_name: Callable[[Path, Path], str],
    has_network_import: Callable[[ast.AST], bool],
) -> tuple[dict[str, Path], dict[str, ast.AST], set[str], list[str]]:
    """Parse declared packages and return the exact observed network-sink set."""
    module_paths: dict[str, Path] = {}
    module_trees: dict[str, ast.AST] = {}
    network_paths: set[str] = set()
    errors: list[str] = []
    for package in packages:
        package_root = root / package
        if not package_root.is_dir():
            errors.append(f"declared package directory is missing: {package}")
            continue
        for path in sorted(package_root.rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, SyntaxError, UnicodeError) as exc:
                errors.append(f"cannot parse {path.relative_to(root).as_posix()}: {exc}")
                continue
            source = module_name(path, root)
            module_paths[source] = path
            module_trees[source] = tree
            if has_network_import(tree):
                network_paths.add(path.relative_to(root).as_posix())
    return module_paths, module_trees, network_paths, errors


def validate_network_inventory(contract: dict[str, Any], network_paths: set[str]) -> list[str]:
    registered = set(contract["network_modules"])
    mapped = set(contract["network_transports"])
    errors = [
        f"unapproved network-capable module: {path}" for path in sorted(network_paths - registered)
    ]
    errors.extend(
        f"stale or missing network-module entry: {path}"
        for path in sorted(registered - network_paths)
    )
    errors.extend(
        f"network sink missing canonical transport mapping: {path}"
        for path in sorted(registered - mapped)
    )
    errors.extend(
        f"transport mapping has no registered network sink: {path}"
        for path in sorted(mapped - registered)
    )
    for path in sorted(network_paths & registered & mapped):
        expected = EXPECTED_NETWORK_TRANSPORTS.get(path)
        if expected is None:
            errors.append(f"network sink has no mechanically verified transport contract: {path}")
        elif contract["network_transports"][path] != expected:
            errors.append(f"network transport contract mismatch: {path}")
    return errors
