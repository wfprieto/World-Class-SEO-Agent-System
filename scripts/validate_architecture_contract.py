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
NETWORK_IMPORTS = {
    "aiohttp",
    "http.client",
    "httpx",
    "playwright",
    "requests",
    "selenium",
    "socket",
    "urllib.request",
    "urllib3",
    "websockets",
}
NETWORK_PROCESS_COMMANDS = {
    "curl",
    "ftp",
    "Invoke-RestMethod",
    "Invoke-WebRequest",
    "powershell",
    "pwsh",
    "wget",
}
SUBPROCESS_CALLS = {
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
    "subprocess.run",
}


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _relative_import_base(source: str, *, is_package: bool, level: int) -> str | None:
    package_parts = source.split(".") if is_package else source.split(".")[:-1]
    keep = len(package_parts) - (level - 1)
    if keep <= 0:
        return None
    return ".".join(package_parts[:keep])


def _imports(tree: ast.AST, *, source: str, is_package: bool) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    imported.add(node.module)
                continue
            base = _relative_import_base(source, is_package=is_package, level=node.level)
            if base is None:
                continue
            if node.module:
                imported.add(f"{base}.{node.module}")
            else:
                imported.update(f"{base}.{alias.name}" for alias in node.names)
    return imported


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _literal_process_command(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip().split(maxsplit=1)[0] if node.value.strip() else None
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        first = node.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _is_network_import(name: str) -> bool:
    return name in NETWORK_IMPORTS or any(
        name.startswith(f"{item}.") for item in NETWORK_IMPORTS
    )


def _import_has_network_egress(node: ast.AST) -> bool:
    if isinstance(node, ast.Import):
        return any(_is_network_import(alias.name) for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        full_names = {node.module, *(f"{node.module}.{alias.name}" for alias in node.names)}
        return any(_is_network_import(name) for name in full_names)
    return False


def _call_has_network_egress(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    call_name = _call_name(node.func)
    if call_name in {"__import__", "importlib.import_module"} and node.args:
        imported = node.args[0]
        return (
            isinstance(imported, ast.Constant)
            and isinstance(imported.value, str)
            and _is_network_import(imported.value)
        )
    if call_name in {*SUBPROCESS_CALLS, "os.system"} and node.args:
        command = _literal_process_command(node.args[0])
        return bool(command and command in NETWORK_PROCESS_COMMANDS)
    return False


def _has_network_import(tree: ast.AST) -> bool:
    return any(
        _import_has_network_egress(node) or _call_has_network_egress(node)
        for node in ast.walk(tree)
    )


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
            module_imports[source] = _imports(tree, source=source, is_package=path.name == "__init__.py")
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
            target = imported
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
