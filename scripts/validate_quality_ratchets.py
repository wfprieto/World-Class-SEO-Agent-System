"""Measure and enforce fail-closed maintainability ratchets for first-party Python."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "governance" / "code-quality-ratchet.json"
PACKAGES = ("runtime", "adapters", "integrations", "seoctl", "scripts")
RUFF_RULES = ("E4", "E7", "E9", "F", "I", "B", "UP", "C4", "SIM", "C90")


def _complexity(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if child is node:
            continue
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp)):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(0, len(child.values) - 1)
        elif isinstance(child, ast.Try):
            score += len(child.handlers) + bool(child.orelse) + bool(child.finalbody)
        elif isinstance(child, ast.Match):
            score += len(child.cases)
        elif isinstance(child, ast.comprehension):
            score += 1 + len(child.ifs)
    return score


def _missing_annotations(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg:
        arguments.append(node.args.vararg)
    if node.args.kwarg:
        arguments.append(node.args.kwarg)
    if arguments and arguments[0].arg in {"self", "cls"}:
        arguments = arguments[1:]
    return sum(item.annotation is None for item in arguments) + (node.returns is None)


class _FunctionVisitor(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.stack: list[str] = []
        self.metrics: dict[str, dict[str, int]] = {}

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.stack.append(node.name)
        key = f"{self.module}::{'.'.join(self.stack)}"
        self.metrics[key] = {
            "span": int((node.end_lineno or node.lineno) - node.lineno + 1),
            "complexity": _complexity(node),
            "missing_annotations": _missing_annotations(node),
        }
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def measure(root: Path = ROOT) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    files: dict[str, dict[str, int]] = {}
    functions: dict[str, dict[str, int]] = {}
    for package in PACKAGES:
        for path in sorted((root / package).rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
            module = relative[:-3].replace("/", ".")
            visitor = _FunctionVisitor(module)
            visitor.visit(tree)
            files[relative] = {
                "lines": len(source.splitlines()),
                "complexity_total": sum(item["complexity"] for item in visitor.metrics.values()),
                "missing_annotations_total": sum(
                    item["missing_annotations"] for item in visitor.metrics.values()
                ),
            }
            functions.update(visitor.metrics)
    return files, functions


def _ruff_counts(root: Path = ROOT) -> Counter[str]:
    command = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        *PACKAGES,
        "--select",
        ",".join(RUFF_RULES),
        "--output-format",
        "json",
    ]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=120)
    if result.returncode not in {0, 1}:
        raise RuntimeError(f"ruff measurement failed: {result.stderr.strip()}")
    findings = json.loads(result.stdout or "[]")
    counts: Counter[str] = Counter()
    for item in findings:
        path = Path(item["filename"])
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            relative = path.as_posix()
        fingerprint = f"{relative}|{item['code']}|{item['message']}"
        counts[fingerprint] += 1
    return counts


def build_contract(root: Path = ROOT) -> dict[str, Any]:
    files, functions = measure(root)
    file_defaults = {"max_lines": 400, "max_complexity_total": 180, "max_missing_annotations": 0}
    function_defaults = {"max_span": 75, "max_complexity": 15, "max_missing_annotations": 0}
    file_exceptions = {
        path: {
            "max_lines": metrics["lines"],
            "max_complexity_total": metrics["complexity_total"],
            "max_missing_annotations": metrics["missing_annotations_total"],
            "owner": "Quality owner",
            "rationale": "Frozen P3 legacy ceiling; increases fail and reductions are encouraged.",
            "removal_phase": "P7",
        }
        for path, metrics in files.items()
        if metrics["lines"] > file_defaults["max_lines"]
        or metrics["complexity_total"] > file_defaults["max_complexity_total"]
        or metrics["missing_annotations_total"] > 0
    }
    function_exceptions = {
        key: {
            "max_span": metrics["span"],
            "max_complexity": metrics["complexity"],
            "max_missing_annotations": metrics["missing_annotations"],
            "owner": "Quality owner",
            "rationale": "Frozen P3 legacy ceiling; increases fail and reductions are encouraged.",
            "removal_phase": "P7",
        }
        for key, metrics in functions.items()
        if metrics["span"] > function_defaults["max_span"]
        or metrics["complexity"] > function_defaults["max_complexity"]
        or metrics["missing_annotations"] > 0
    }
    return {
        "schema_version": "1.0.0",
        "packages": list(PACKAGES),
        "file_defaults": file_defaults,
        "function_defaults": function_defaults,
        "file_exceptions": file_exceptions,
        "function_exceptions": function_exceptions,
        "ruff": {"rules": list(RUFF_RULES), "violation_counts": dict(sorted(_ruff_counts(root).items()))},
        "coverage": {
            "repository_floor": 78.0,
            "critical_file_floors": {
                "adapters/evidence_store.py": 67.0,
                "adapters/google_pagespeed_live.py": 83.0,
                "adapters/url_safety.py": 87.0,
                "integrations/authority_media/transport.py": 67.0,
                "integrations/google/client.py": 68.0,
                "integrations/google/gsc.py": 62.0,
                "integrations/technical/browser.py": 45.0,
                "integrations/technical/http.py": 72.0,
                "runtime/executor.py": 96.0,
                "runtime/llm.py": 64.0,
                "runtime/structured_output.py": 89.0,
                "runtime/tools.py": 83.0,
                "runtime/workflow_runner.py": 93.0,
            },
        },
    }


def _load_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("quality ratchet must contain a JSON object")
    return payload


def _repository_setting_errors(root: Path, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    configured_rules = tuple(pyproject.get("tool", {}).get("ruff", {}).get("lint", {}).get("select", []))
    if configured_rules != RUFF_RULES:
        errors.append("pyproject Ruff profile must equal the canonical P3 rule profile")
    mypy = pyproject.get("tool", {}).get("mypy", {})
    if (
        mypy.get("follow_imports") != "normal"
        or mypy.get("explicit_package_bases") is not True
        or mypy.get("check_untyped_defs") is not True
    ):
        errors.append("mypy must analyze imported bodies and untyped function bodies")
    coverage = contract["coverage"]
    total_floor = float(pyproject["tool"]["coverage"]["report"]["fail_under"])
    if total_floor < float(coverage["repository_floor"]):
        errors.append("repository coverage floor is weaker than the quality contract")
    risk = pyproject["tool"].get("wcseo", {}).get("risk_coverage", {})
    for path, floor in coverage["critical_file_floors"].items():
        if float(risk.get(path, -1)) < float(floor):
            errors.append(f"critical coverage floor is missing or weak: {path}")
    workflow = (root / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    for command in (
        "python scripts/validate_architecture_contract.py",
        "python scripts/validate_quality_ratchets.py",
    ):
        if command not in workflow:
            errors.append(f"CI is missing mandatory quality command: {command}")
    if "ruff check . --select" in workflow:
        errors.append("CI must not override the canonical Ruff profile with --select")
    return errors


def validate(
    root: Path = ROOT,
    contract_path: Path | None = None,
    *,
    enforce_repository_settings: bool = True,
) -> list[str]:
    contract_path = contract_path or root / CONTRACT_PATH.relative_to(ROOT)
    contract = _load_contract(contract_path)
    errors: list[str] = []
    if contract.get("schema_version") != "1.0.0":
        errors.append("unsupported quality-ratchet schema_version")
        return errors
    if tuple(contract.get("packages", [])) != PACKAGES:
        errors.append("quality-ratchet package inventory must match first-party packages exactly")
    file_defaults = contract.get("file_defaults", {})
    function_defaults = contract.get("function_defaults", {})
    files, functions = measure(root)
    file_exceptions = contract.get("file_exceptions", {})
    function_exceptions = contract.get("function_exceptions", {})
    for path, ceiling in file_exceptions.items():
        normalized = Path(path).as_posix()
        if normalized != path or Path(path).is_absolute() or ".." in Path(path).parts:
            errors.append(f"unsafe quality file exception path: {path}")
        if not all(ceiling.get(field) for field in ("owner", "rationale", "removal_phase")):
            errors.append(f"quality file exception lacks accountable metadata: {path}")
    for key, ceiling in function_exceptions.items():
        if "::" not in key or ".." in key or key.startswith(("/", "\\")):
            errors.append(f"unsafe quality function exception key: {key}")
        if not all(ceiling.get(field) for field in ("owner", "rationale", "removal_phase")):
            errors.append(f"quality function exception lacks accountable metadata: {key}")

    for path, metrics in files.items():
        ceiling = file_exceptions.get(path, file_defaults)
        for metric, key in (
            ("lines", "max_lines"),
            ("complexity_total", "max_complexity_total"),
            ("missing_annotations_total", "max_missing_annotations"),
        ):
            if metrics[metric] > int(ceiling[key]):
                errors.append(f"{path} {metric} {metrics[metric]} exceeds ceiling {ceiling[key]}")
    for path in sorted(set(file_exceptions) - set(files)):
        errors.append(f"quality file exception references missing file: {path}")

    for key, metrics in functions.items():
        ceiling = function_exceptions.get(key, function_defaults)
        for metric, limit_key in (
            ("span", "max_span"),
            ("complexity", "max_complexity"),
            ("missing_annotations", "max_missing_annotations"),
        ):
            if metrics[metric] > int(ceiling[limit_key]):
                errors.append(f"{key} {metric} {metrics[metric]} exceeds ceiling {ceiling[limit_key]}")
    for key in sorted(set(function_exceptions) - set(functions)):
        errors.append(f"quality function exception references missing symbol: {key}")

    expected_ruff = Counter({key: int(value) for key, value in contract["ruff"]["violation_counts"].items()})
    if tuple(contract["ruff"]["rules"]) != RUFF_RULES:
        errors.append("Ruff rule profile is weaker or different from the canonical P3 profile")
    actual_ruff = _ruff_counts(root)
    for fingerprint, count in sorted(actual_ruff.items()):
        if count > expected_ruff.get(fingerprint, 0):
            errors.append(
                f"new Ruff debt: {fingerprint} count {count} exceeds {expected_ruff.get(fingerprint, 0)}"
            )
    for fingerprint in sorted(set(expected_ruff) - set(actual_ruff)):
        errors.append(f"stale Ruff baseline must be tightened after remediation: {fingerprint}")
    if enforce_repository_settings:
        errors.extend(_repository_setting_errors(root, contract))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()
    if args.write_baseline:
        CONTRACT_PATH.write_text(json.dumps(build_contract(), indent=2) + "\n", encoding="utf-8")
        print(CONTRACT_PATH.relative_to(ROOT).as_posix())
        return 0
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
