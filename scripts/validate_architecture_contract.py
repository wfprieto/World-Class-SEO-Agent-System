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
    "invoke-restmethod",
    "invoke-webrequest",
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


def _imports(
    tree: ast.AST, *, source: str, is_package: bool, known_modules: set[str]
) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    imported.add(node.module)
                    imported.update(
                        candidate
                        for alias in node.names
                        if (candidate := f"{node.module}.{alias.name}") in known_modules
                    )
                continue
            base = _relative_import_base(source, is_package=is_package, level=node.level)
            if base is None:
                continue
            if node.module:
                target = f"{base}.{node.module}"
                imported.add(target)
                imported.update(
                    candidate
                    for alias in node.names
                    if (candidate := f"{target}.{alias.name}") in known_modules
                )
            else:
                imported.update(
                    candidate
                    for alias in node.names
                    if (candidate := f"{base}.{alias.name}") in known_modules
                )
    imported.update(_literal_dynamic_imports(tree))
    return imported


def _resolved_imports(
    module_paths: dict[str, Path], module_trees: dict[str, ast.AST]
) -> dict[str, set[str]]:
    known_modules = set(module_paths)
    return {
        source: _imports(
            tree,
            source=source,
            is_package=module_paths[source].name == "__init__.py",
            known_modules=known_modules,
        )
        for source, tree in module_trees.items()
    }


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                aliases[local_name] = alias.name if alias.asname else local_name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _resolved_call_name(node: ast.AST, aliases: dict[str, str]) -> str | None:
    call_name = _call_name(node)
    if call_name is None:
        return None
    head, separator, tail = call_name.partition(".")
    resolved_head = aliases.get(head, head)
    return f"{resolved_head}{separator}{tail}"


def _literal_process_command(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip().split(maxsplit=1)[0] if node.value.strip() else None
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
        first = node.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
    return None


def _call_argument(node: ast.Call, position: int | None, keyword: str) -> ast.AST | None:
    if position is not None and len(node.args) > position:
        return node.args[position]
    return next((item.value for item in node.keywords if item.arg == keyword), None)


def _literal_dynamic_imports(tree: ast.AST) -> set[str]:
    aliases = _import_aliases(tree)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _resolved_call_name(node.func, aliases) not in {
            "__import__",
            "importlib.import_module",
        }:
            continue
        argument = _call_argument(node, 0, "name")
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            imported.add(argument.value)
    return imported


def _normalized_process_command(command: str) -> str:
    name = command.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return name[:-4] if name.endswith(".exe") else name


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


def _call_has_network_egress(node: ast.AST, aliases: dict[str, str]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    call_name = _resolved_call_name(node.func, aliases)
    if call_name in {"__import__", "importlib.import_module"}:
        imported = _call_argument(node, 0, "name")
        return (
            isinstance(imported, ast.Constant)
            and isinstance(imported.value, str)
            and _is_network_import(imported.value)
        )
    if call_name in {*SUBPROCESS_CALLS, "os.system"}:
        argument = _call_argument(node, 0, "args" if call_name != "os.system" else "command")
        command = _literal_process_command(argument) if argument is not None else None
        executable = _call_argument(node, None, "executable")
        executable_name = _literal_process_command(executable) if executable is not None else None
        return any(
            value is not None and _normalized_process_command(value) in NETWORK_PROCESS_COMMANDS
            for value in (command, executable_name)
        )
    return False


def _has_network_import(tree: ast.AST) -> bool:
    aliases = _import_aliases(tree)
    return any(
        _import_has_network_egress(node) or _call_has_network_egress(node, aliases)
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
    module_trees: dict[str, ast.AST] = {}
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
            module_trees[source] = tree
            if _has_network_import(tree):
                network_paths.add(path.relative_to(root).as_posix())
    module_imports = _resolved_imports(module_paths, module_trees)
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
