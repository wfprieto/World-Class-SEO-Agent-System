"""Fail-closed validation of package dependencies and direct network boundaries."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "governance" / "architecture-contract.json"
SCHEMA_PATH = ROOT / "schemas" / "architecture-contract.schema.json"
NETWORK_IMPORTS = {"socket", "urllib.request", "http.client", "requests", "httpx", "aiohttp"}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        return ".".join(parts)
    return ".".join(parts)


def _imports(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module)
    return imported


def _has_network_import(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name in NETWORK_IMPORTS
                or any(alias.name.startswith(f"{item}.") for item in NETWORK_IMPORTS)
                for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module:
            full_names = {node.module, *(f"{node.module}.{alias.name}" for alias in node.names)}
            if any(
                name in NETWORK_IMPORTS
                or any(name.startswith(f"{item}.") for item in NETWORK_IMPORTS)
                for name in full_names
            ):
                return True
    return False


def _cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    found: set[tuple[str, ...]] = set()
    active: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            cycle = active[active.index(node) :] + [node]
            rotations = [tuple(cycle[index:-1] + cycle[:index] + [cycle[index]]) for index in range(len(cycle) - 1)]
            found.add(min(rotations))
            return
        if node in visited:
            return
        active.append(node)
        for target in sorted(graph.get(node, set())):
            visit(target)
        active.pop()
        visited.add(node)

    for module in sorted(graph):
        visit(module)
    return [list(item) for item in sorted(found)]


def validate(
    root: Path = ROOT,
    contract_path: Path | None = None,
    schema_path: Path | None = None,
) -> list[str]:
    contract_path = contract_path or root / CONTRACT_PATH.relative_to(ROOT)
    schema_path = schema_path or root / SCHEMA_PATH.relative_to(ROOT)
    contract = _load(contract_path)
    schema = _load(schema_path)
    errors = [
        f"schema {'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(contract)
    ]
    if errors:
        return sorted(errors)

    layers = {str(name): str(package) for name, package in contract["layers"].items()}
    package_layers = {package: name for name, package in layers.items()}
    allowed = {(item["source"], item["target"]) for item in contract["allowed_layer_edges"]}
    exceptions = {(item["source"], item["target"]) for item in contract["exceptions"]}
    if len(exceptions) != len(contract["exceptions"]):
        errors.append("dependency exceptions must have unique source-target pairs")

    module_paths: dict[str, Path] = {}
    module_imports: dict[str, set[str]] = {}
    network_paths: set[str] = set()
    for package in sorted(package_layers):
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
            source = _module_name(path, root)
            module_paths[source] = path
            module_imports[source] = _imports(tree)
            if _has_network_import(tree):
                network_paths.add(path.relative_to(root).as_posix())

    observed_cross_edges: set[tuple[str, str]] = set()
    graph: dict[str, set[str]] = {name: set() for name in module_paths}
    for source, imports in module_imports.items():
        source_package = source.split(".", 1)[0]
        source_layer = package_layers[source_package]
        for imported in sorted(imports):
            target_package = imported.split(".", 1)[0]
            if target_package not in package_layers:
                continue
            target = imported if "." in imported else f"{imported}.__init__"
            if target in module_paths:
                graph[source].add(target)
            target_layer = package_layers[target_package]
            if source_layer == target_layer:
                continue
            edge = (source, target)
            observed_cross_edges.add(edge)
            if (source_layer, target_layer) not in allowed and edge not in exceptions:
                errors.append(f"forbidden dependency edge: {source} -> {target}")

    for edge in sorted(exceptions - observed_cross_edges):
        errors.append(f"stale or unknown dependency exception: {edge[0]} -> {edge[1]}")
    for cycle in _cycles(graph):
        errors.append(f"internal import cycle: {' -> '.join(cycle)}")

    expected_network = set(contract["network_modules"])
    for relative_path in sorted(network_paths - expected_network):
        errors.append(f"unapproved network-capable module: {relative_path}")
    for relative_path in sorted(expected_network - network_paths):
        errors.append(f"stale or missing network-module entry: {relative_path}")
    return sorted(errors)


def main() -> int:
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
