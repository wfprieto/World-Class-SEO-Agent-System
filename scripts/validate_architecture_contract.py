"""Fail-closed validation of package dependencies and direct network boundaries."""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import shlex
import sys
from itertools import dropwhile
from operator import attrgetter
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "governance" / "architecture-contract.json"
SCHEMA_PATH = ROOT / "schemas" / "architecture-contract.schema.json"
NETWORK_IMPORTS = {"aiohttp", "http.client", "httpx", "playwright", "requests", "selenium", "socket", "urllib.request", "urllib3", "websockets"}
NETWORK_IMPORT_PREFIXES = tuple(f"{item}." for item in NETWORK_IMPORTS)
NETWORK_PROCESS_COMMANDS = {"curl", "ftp", "invoke-restmethod", "invoke-webrequest", "powershell", "pwsh", "wget"}
SHELL_LONG_OPTIONS = {"--login", "--noprofile", "--norc", "--posix", "--restricted", "--verbose"}
SHELL_SHORT_OPTIONS = frozenset("abefhklmnptuvxBCEHPTc")
ENV_FLAG_OPTIONS = {"-0", "-i", "--debug", "--ignore-environment", "--null"}
ENV_VALUE_OPTIONS = {"-C", "-u", "--chdir", "--unset"}
SHELL_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*").fullmatch
SUBPROCESS_CALLS = {"subprocess.call", "subprocess.check_call", "subprocess.check_output", "subprocess.Popen", "subprocess.run"}
REFLECTIVE_ALIAS_TARGETS = {"__import__", "builtins", "builtins.__import__", "importlib", "importlib.import_module"}
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
def _imports(tree: ast.AST, *, source: str, is_package: bool, known_modules: set[str]) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    imported.add(node.module)
                    imported.update(candidate for alias in node.names
                                    if (candidate := f"{node.module}.{alias.name}") in known_modules)
                continue
            base = _relative_import_base(source, is_package=is_package, level=node.level)
            if base is None:
                continue
            if node.module:
                target = f"{base}.{node.module}"
                imported.add(target)
                imported.update(candidate for alias in node.names
                                if (candidate := f"{target}.{alias.name}") in known_modules)
            else:
                imported.update(candidate for alias in node.names
                                if (candidate := f"{base}.{alias.name}") in known_modules)
    imported.update(_literal_dynamic_imports(tree))
    return imported
def _resolved_imports(module_paths: dict[str, Path], module_trees: dict[str, ast.AST]) -> dict[str, set[str]]:
    known_modules = set(module_paths)
    return {source: _imports(tree, source=source,
                             is_package=module_paths[source].name == "__init__.py",
                             known_modules=known_modules)
            for source, tree in module_trees.items()}
def _call_name(node: ast.AST | None) -> str | None:
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
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value_name = _resolved_call_name(node.value, aliases)
            if value_name in REFLECTIVE_ALIAS_TARGETS:
                for target in targets:
                    aliases[cast(str, _call_name(target))] = value_name
    return aliases
def _resolved_call_name(node: ast.AST | None, aliases: dict[str, str]) -> str | None:
    call_name = _call_name(node)
    if call_name is None:
        return None
    call_name = aliases.get(call_name, call_name)
    head, separator, tail = call_name.partition(".")
    resolved_head = aliases.get(head, head)
    return f"{resolved_head}{separator}{tail}"
def _literal_text(node: ast.AST | None) -> str | None:
    value = getattr(node, "value", None)
    if isinstance(value, str):
        return value
    try:
        return value.decode("utf-8") if isinstance(value, bytes) else None
    except UnicodeDecodeError:
        return None
def _literal_process_tokens(node: ast.AST | None) -> list[str] | None:
    text = _literal_text(node)
    if text is not None:
        try:
            return shlex.split(text, posix=False)
        except ValueError:
            return None
    elements = getattr(node, "elts", None)
    if elements is None:
        return None
    values = list(map(_literal_text, elements))
    return None if None in values else cast(list[str], values)
def _call_argument(node: ast.Call, position: int | None, keyword: str) -> ast.AST | None:
    positional = node.args[position : position + 1] if position is not None else []
    keywords = {item.arg: item.value for item in node.keywords}
    return next(iter(positional), keywords.get(keyword))
def _literal_dynamic_imports(tree: ast.AST) -> set[str]:
    aliases = _import_aliases(tree)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and (target := _literal_dynamic_target(node, aliases)):
            imported.add(target)
    return imported
def _literal_dynamic_target(node: ast.Call, aliases: dict[str, str]) -> str | None:
    call_name = _resolved_call_name(node.func, aliases)
    if call_name not in {"__import__", "builtins.__import__", "importlib.import_module"}:
        return None
    argument = _call_argument(node, 0, "name")
    name = _literal_text(argument) if argument is not None else None
    if not name or not name.startswith("."):
        return name
    package_node = _call_argument(node, 1, "package")
    package = _literal_text(package_node) if package_node is not None else None
    if call_name != "importlib.import_module" or not package:
        return None
    try:
        return importlib.util.resolve_name(name, package)
    except ImportError:
        return None
def _unresolved_dynamic_errors(module_trees: dict[str, ast.AST]) -> list[str]:
    errors: list[str] = []
    for source, tree in module_trees.items():
        aliases = _import_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = _resolved_call_name(node.func, aliases)
            argument = _call_argument(node, 0, "name")
            name = _literal_text(argument) if argument is not None else None
            if (
                call_name == "importlib.import_module"
                and name is not None
                and name.startswith(".")
                and _literal_dynamic_target(node, aliases) is None
            ):
                errors.append(f"unresolved literal relative import: {source} -> {name}")
    return errors
def _normalized_process_command(command: str) -> str:
    name = command.strip().strip('"\'').replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return name.removesuffix(".exe")
def _shell_literal_tokens(text: str) -> tuple[list[str], bool]:
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split, lexer.commenters = True, ""
    try:
        tokens = list(lexer)
    except ValueError:
        return [], True
    operators = re.sub(r"'[^']*'|\"[^\"]*\"", "", text)
    return tokens, bool(re.search(r"[\r\n]|[;&|<>]", operators) or re.search(r"(?<!\\)(?:\$\(|`)", re.sub(r"'[^']*'", "", text)))
def _shell_wrapper_result(tokens: list[str], depth: int) -> tuple[str | None, bool]:
    index = 1
    while index < len(tokens):
        option = tokens[index]
        if option in SHELL_LONG_OPTIONS:
            index += 1
            continue
        flags = option[1:] if option.startswith("-") and not option.startswith("--") else ""
        if not flags or not set(flags) <= SHELL_SHORT_OPTIONS:
            return None, True
        index += 1
        if "c" not in flags:
            continue
        if index >= len(tokens):
            return None, True
        nested, unsafe = _shell_literal_tokens(tokens[index])
        if unsafe:
            return None, True
        return _effective_process_command(nested, depth + 1, shell_words=True)
    return _normalized_process_command(tokens[0]), False
def _env_wrapper_result(tokens: list[str], depth: int) -> tuple[str | None, bool]:
    index = 1
    while index < len(tokens):
        option = tokens[index]
        if option == "--":
            index += 1
            break
        if option in ENV_FLAG_OPTIONS or option.startswith(("--unset=", "--chdir=")):
            index += 1
        elif option in ENV_VALUE_OPTIONS:
            index += 2
            if index > len(tokens):
                return None, True
        elif option.startswith("-"):
            return None, True
        elif SHELL_ASSIGNMENT(option):
            index += 1
        else:
            break
    if index >= len(tokens):
        return "env", False
    return _effective_process_command(tokens[index:], depth + 1)
def _command_wrapper_result(tokens: list[str], depth: int) -> tuple[str | None, bool]:
    remaining = tokens[1:]
    index = len(remaining) - len(list(dropwhile(lambda token: token.startswith("-"), remaining)))
    options = tuple(remaining[:index])
    if options in {("-v",), ("-V",), ("-v", "--"), ("-V", "--")}:
        return "command", False
    if options not in {(), ("-p",), ("--",), ("-p", "--")}:
        return None, True
    return _effective_process_command(remaining[index:], depth + 1)
def _effective_process_command(tokens: list[str], depth: int = 0, *, shell_words: bool = False) -> tuple[str | None, bool]:
    if depth > 3:
        return None, True
    if shell_words:
        tokens = list(dropwhile(SHELL_ASSIGNMENT, tokens))
        if tokens[:1] == ["exec"]:
            tokens = tokens[1:]
    if not tokens:
        return None, False
    command = _normalized_process_command(tokens[0])
    wrapper = {"bash": _shell_wrapper_result, "sh": _shell_wrapper_result, "env": _env_wrapper_result, "command": _command_wrapper_result}.get(command, lambda _tokens, _depth: (command, False))
    return wrapper(tokens, depth)
def _process_argument_result(node: ast.AST, *, shell_words: bool = False) -> tuple[str | None, bool]:
    text = _literal_text(node)
    if shell_words:
        tokens, unsafe = _shell_literal_tokens(text) if text is not None else ([], True)
        return (None, True) if unsafe else _effective_process_command(tokens, shell_words=True)
    literal_tokens = _literal_process_tokens(node)
    if literal_tokens is not None:
        return _effective_process_command(literal_tokens, shell_words=shell_words)
    head = _literal_text(next(iter(getattr(node, "elts", ())), None))
    return None, _normalized_process_command(head or "") in {"bash", "sh", "env", "command"}
def _selected_executable_result(argument: ast.AST | None, executable: ast.AST) -> tuple[str | None, bool]:
    executable_name, unsafe = _process_argument_result(executable)
    if executable_name not in {"bash", "sh", "env"}:
        return executable_name, unsafe
    tokens = _literal_process_tokens(argument)
    if tokens is None:
        return None, True
    return _effective_process_command([executable_name, *tokens[1:]])
def _is_network_import(name: str) -> bool:
    return any((name in NETWORK_IMPORTS, name.startswith(NETWORK_IMPORT_PREFIXES)))
def _import_has_network_egress(node: ast.AST) -> bool:
    if not isinstance(node, (ast.Import, ast.ImportFrom)):
        return False
    module = getattr(node, "module", None)
    names = list(map(attrgetter("name"), node.names))
    candidates = names if module is None else [module, *map(f"{module}.{{}}".format, names)]
    return any(map(_is_network_import, candidates))
def _call_has_network_egress(node: ast.AST, aliases: dict[str, str]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    call_name = _resolved_call_name(node.func, aliases)
    if call_name in {"__import__", "builtins.__import__", "importlib.import_module"}:
        imported = _literal_dynamic_target(node, aliases)
        return bool(imported and _is_network_import(imported))
    if call_name in {*SUBPROCESS_CALLS, "os.system"}:
        keyword = {"os.system": "command"}.get(call_name, "args")
        argument = _call_argument(node, 0, keyword)
        shell_node = _call_argument(node, None, "shell")
        shell = call_name == "os.system" or getattr(shell_node, "value", False) is True
        command, unsafe = _process_argument_result(argument, shell_words=shell) if argument else (None, False)
        executable = _call_argument(node, None, "executable")
        executable_name, executable_unsafe = (_selected_executable_result(argument, executable)
                                               if executable is not None and not shell else (None, False))
        return any((unsafe, executable_unsafe, command in NETWORK_PROCESS_COMMANDS,
                    executable_name in NETWORK_PROCESS_COMMANDS))
    return False
def _has_network_import(tree: ast.AST) -> bool:
    aliases = _import_aliases(tree)
    return any(
        _import_has_network_egress(node) or _call_has_network_egress(node, aliases)
        for node in ast.walk(tree))
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
def validate(root: Path = ROOT, contract_path: Path | None = None,
             schema_path: Path | None = None) -> list[str]:
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
    errors.extend(_unresolved_dynamic_errors(module_trees))
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
