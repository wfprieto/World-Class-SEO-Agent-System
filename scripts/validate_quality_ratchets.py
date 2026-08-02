from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import re
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
FILE_DEFAULTS = {"max_lines": 400, "max_complexity_total": 180, "max_missing_annotations": 0}
FUNCTION_DEFAULTS = {"max_span": 75, "max_complexity": 15, "max_missing_annotations": 0}
FILE_METRICS = (("lines", "max_lines"), ("complexity_total", "max_complexity_total"), ("missing_annotations_total", "max_missing_annotations"))
FUNCTION_METRICS = (("span", "max_span"), ("complexity", "max_complexity"), ("missing_annotations", "max_missing_annotations"))
MINIMUM_REPOSITORY_COVERAGE = 78.0
MINIMUM_CRITICAL_COVERAGE = {
    "adapters/evidence_store.py": 67.0, "adapters/google_pagespeed_live.py": 83.0,
    "adapters/url_safety.py": 87.0, "integrations/authority_media/transport.py": 67.0,
    "integrations/google/client.py": 68.0, "integrations/google/gsc.py": 62.0,
    "integrations/technical/browser.py": 45.0, "integrations/technical/http.py": 72.0,
    "runtime/executor.py": 96.0, "runtime/llm.py": 64.0,
    "runtime/structured_output.py": 89.0, "runtime/tools.py": 83.0,
    "runtime/workflow_runner.py": 93.0,
}
COVERAGE_TARGETS = ("runtime", "seoctl", "integrations", "adapters")
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
def _load_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("quality ratchet must contain a JSON object")
    return payload
def _contract_digest(contract: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
def _previous_contract(root: Path, contract_path: Path) -> dict[str, Any] | None:
    try:
        relative = contract_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    try:
        head_text = subprocess.run(
            ["git", "show", f"HEAD:{relative}"], cwd=root, check=True,
            capture_output=True, text=True, timeout=20,
        ).stdout
        current_text = contract_path.read_text(encoding="utf-8-sig")
        if json.loads(head_text) != json.loads(current_text):
            return json.loads(head_text)
        revisions = subprocess.run(
            ["git", "log", "-2", "--format=%H", "--", relative], cwd=root,
            check=True, capture_output=True, text=True, timeout=20,
        ).stdout.splitlines()
        if len(revisions) < 2:
            return None
        return json.loads(subprocess.run(
            ["git", "show", f"{revisions[1]}:{relative}"], cwd=root, check=True,
            capture_output=True, text=True, timeout=20,
        ).stdout)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
def _checkout_errors(lines: list[str]) -> list[str]:
    indexes = [index for index, line in enumerate(lines) if "uses: actions/checkout@" in line]
    errors = [] if indexes else ["CI requires at least one pinned actions/checkout step"]
    for index in indexes:
        reference = lines[index].split("actions/checkout@", 1)[1].split()[0]
        indent, following = len(lines[index]) - len(lines[index].lstrip()), lines[index + 1:]
        boundary = next((offset for offset, line in enumerate(following) if line.strip().startswith("-") and len(line) - len(line.lstrip()) <= indent), len(following))
        if not re.fullmatch(r"[0-9a-f]{40}", reference):
            errors.append("every actions/checkout step must use an immutable 40-character SHA")
        if not re.search(r"(?m)^\s+fetch-depth:\s*0\s*$", "\n".join(following[:boundary])):
            errors.append("every actions/checkout step must set fetch-depth: 0")
    return errors
def _workflow_errors(workflow: str, coverage_floor: float) -> list[str]:
    lines = workflow.splitlines()
    coverage = "pytest -q " + " ".join(f"--cov={target}" for target in COVERAGE_TARGETS) + " --cov-report=term-missing --cov-report=xml:outputs/coverage.xml --cov-report=json:outputs/coverage.json " + f"--cov-fail-under={coverage_floor:g} --junitxml=outputs/pytest-quality.xml"
    errors = _checkout_errors(lines)
    if [line.strip() for line in lines if "pytest" in line and "--cov" in line] != [coverage]:
        errors.append("CI coverage command must equal the canonical source, report-path, and threshold contract")
    risk_lines = [line.strip() for line in lines if line.strip().startswith("python scripts/validate_risk_coverage.py")]
    if risk_lines != ["python scripts/validate_risk_coverage.py outputs/coverage.json"]:
        errors.append("CI risk coverage command must consume outputs/coverage.json exactly once")
    return errors
def _canonical_policy_errors(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("file_defaults") != FILE_DEFAULTS:
        errors.append("file defaults must equal the immutable canonical new-code policy")
    if contract.get("function_defaults") != FUNCTION_DEFAULTS:
        errors.append("function defaults must equal the immutable canonical new-code policy")
    coverage = contract.get("coverage", {})
    if float(coverage.get("repository_floor", -1)) < MINIMUM_REPOSITORY_COVERAGE:
        errors.append("repository coverage floor is below the immutable canonical minimum")
    critical = coverage.get("critical_file_floors", {})
    for path, minimum in MINIMUM_CRITICAL_COVERAGE.items():
        if float(critical.get(path, -1)) < minimum:
            errors.append(f"critical coverage floor is below the immutable canonical minimum: {path}")
    return errors
def _monotonic_exception_errors(
    previous: dict[str, Any], current: dict[str, Any], section: str, fields: tuple[str, ...]
) -> list[str]:
    before, after = previous.get(section, {}), current.get(section, {})
    errors = [f"quality ratchet cannot add a new legacy exception: {key}" for key in sorted(set(after) - set(before))]
    for key in sorted(set(after) & set(before)):
        errors.extend(
            f"quality ratchet cannot raise {key} {field}"
            for field in fields if int(after[key][field]) > int(before[key][field])
        )
        errors.extend(
            f"quality ratchet cannot rewrite {key} {field}"
            for field in ("owner", "rationale", "removal_phase")
            if after[key].get(field) != before[key].get(field)
        )
    return errors
def _monotonic_contract_errors(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Reject contract edits that add or raise debt allowances."""
    errors = _monotonic_exception_errors(previous, current, "file_exceptions", tuple(key for _, key in FILE_METRICS))
    errors += _monotonic_exception_errors(previous, current, "function_exceptions", tuple(key for _, key in FUNCTION_METRICS))
    for field in ("schema_version", "packages", "file_defaults", "function_defaults"):
        if current.get(field) != previous.get(field):
            errors.append(f"quality ratchet cannot rewrite immutable policy field: {field}")
    old_ruff = previous.get("ruff", {}).get("violation_counts", {})
    new_ruff = current.get("ruff", {}).get("violation_counts", {})
    for key, count in new_ruff.items():
        if int(count) > int(old_ruff.get(key, 0)):
            errors.append(f"quality ratchet cannot add or raise Ruff allowance: {key}")
    old_coverage = previous.get("coverage", {})
    new_coverage = current.get("coverage", {})
    if float(new_coverage.get("repository_floor", -1)) < float(old_coverage.get("repository_floor", -1)):
        errors.append("quality ratchet cannot lower repository coverage floor")
    for path, floor in old_coverage.get("critical_file_floors", {}).items():
        if float(new_coverage.get("critical_file_floors", {}).get(path, -1)) < float(floor):
            errors.append(f"quality ratchet cannot lower critical coverage floor: {path}")
    return errors
def _exception_metadata_errors(exceptions: dict[str, Any], kind: str) -> list[str]:
    errors: list[str] = []
    for key, ceiling in exceptions.items():
        path = Path(key)
        unsafe_file = path.as_posix() != key or path.is_absolute() or ".." in path.parts
        unsafe_function = "::" not in key or ".." in key or key.startswith(("/", "\\"))
        if unsafe_file if kind == "file" else unsafe_function:
            errors.append(f"unsafe quality {kind} exception {'path' if kind == 'file' else 'key'}: {key}")
        if not all(ceiling.get(field) for field in ("owner", "rationale", "removal_phase")):
            errors.append(f"quality {kind} exception lacks accountable metadata: {key}")
    return errors
def _measurement_errors(
    exceptions: dict[str, Any], measurements: dict[str, dict[str, int]],
    defaults: dict[str, int], pairs: tuple[tuple[str, str], ...], kind: str,
) -> list[str]:
    errors: list[str] = []
    for key, metrics in measurements.items():
        ceiling = exceptions.get(key, defaults)
        for metric, limit in pairs:
            if metrics[metric] > int(ceiling[limit]):
                errors.append(f"{key} {metric} {metrics[metric]} exceeds ceiling {ceiling[limit]}")
            elif key in exceptions and metrics[metric] < int(ceiling[limit]):
                errors.append(f"stale quality {kind} ceiling must be tightened: {key} {limit}")
        if key in exceptions and all(metrics[metric] <= defaults[limit] for metric, limit in pairs):
            errors.append(f"quality {kind} exception must be removed after remediation: {key}")
    missing_label = "file" if kind == "file" else "symbol"
    errors.extend(f"quality {kind} exception references missing {missing_label}: {key}" for key in sorted(set(exceptions) - set(measurements)))
    return errors
def _exception_errors(
    exceptions: dict[str, Any], measurements: dict[str, dict[str, int]],
    defaults: dict[str, int], pairs: tuple[tuple[str, str], ...], kind: str,
) -> list[str]:
    return _exception_metadata_errors(exceptions, kind) + _measurement_errors(
        exceptions, measurements, defaults, pairs, kind
    )
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
    errors.extend(_workflow_errors(workflow, float(coverage["repository_floor"])))
    errors += ["CI risk coverage validator script is missing"] * int(not (root / "scripts" / "validate_risk_coverage.py").is_file())
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
    previous_contract: dict[str, Any] | None = None,
) -> list[str]:
    contract_path = contract_path or root / CONTRACT_PATH.relative_to(ROOT)
    contract = _load_contract(contract_path)
    errors: list[str] = []
    if contract.get("schema_version") != "1.0.0":
        errors.append("unsupported quality-ratchet schema_version")
        return errors
    errors.extend(_canonical_policy_errors(contract))
    prior = previous_contract
    canonical_root = root.resolve() == ROOT.resolve()
    if prior is None and canonical_root:
        prior = _previous_contract(root, contract_path)
    errors += ["quality ratchet prior contract Git history is unavailable"] * int(prior is None and canonical_root)
    if prior is not None:
        errors.extend(_monotonic_contract_errors(prior, contract))
    if tuple(contract.get("packages", [])) != PACKAGES:
        errors.append("quality-ratchet package inventory must match first-party packages exactly")
    file_defaults = contract.get("file_defaults", {})
    function_defaults = contract.get("function_defaults", {})
    files, functions = measure(root)
    file_exceptions = contract.get("file_exceptions", {})
    function_exceptions = contract.get("function_exceptions", {})
    errors.extend(_exception_errors(file_exceptions, files, file_defaults, FILE_METRICS, "file"))
    errors.extend(_exception_errors(function_exceptions, functions, function_defaults, FUNCTION_METRICS, "function"))
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
def _tighten_exceptions(
    proposal: dict[str, Any], contract: dict[str, Any], measurements: dict[str, dict[str, int]],
    defaults: dict[str, int], pairs: tuple[tuple[str, str], ...], section: str, kind: str,
) -> None:
    for key, ceiling in contract.get(section, {}).items():
        metrics = measurements.get(key)
        if metrics is None:
            raise ValueError(f"cannot update missing legacy {kind}: {key}")
        if any(metrics[metric] > int(ceiling[limit]) for metric, limit in pairs):
            raise ValueError(f"cannot baseline increased legacy {kind} debt: {key}")
        if all(metrics[metric] <= defaults[limit] for metric, limit in pairs):
            del proposal[section][key]
        else:
            for metric, limit in pairs:
                proposal[section][key][limit] = metrics[metric]
def tightened_contract(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    proposal = copy.deepcopy(contract)
    files, functions = measure(root)
    _tighten_exceptions(proposal, contract, files, FILE_DEFAULTS, FILE_METRICS, "file_exceptions", "file")
    _tighten_exceptions(proposal, contract, functions, FUNCTION_DEFAULTS, FUNCTION_METRICS, "function_exceptions", "function")
    actual_ruff = _ruff_counts(root)
    allowed_ruff = contract.get("ruff", {}).get("violation_counts", {})
    for fingerprint, count in actual_ruff.items():
        if count > int(allowed_ruff.get(fingerprint, 0)):
            raise ValueError(f"cannot baseline new Ruff debt: {fingerprint}")
    proposal["ruff"]["violation_counts"] = dict(sorted(actual_ruff.items()))
    monotonic_errors = _monotonic_contract_errors(contract, proposal)
    if monotonic_errors:
        raise ValueError("; ".join(monotonic_errors))
    return proposal
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--approve-tightening", metavar="CURRENT_SHA256")
    args = parser.parse_args()
    if args.write_baseline:
        contract = _load_contract(CONTRACT_PATH)
        expected = _contract_digest(contract)
        if not args.approve_tightening or args.approve_tightening != expected:
            failure = {"status": "FAIL", "errors": ["--write-baseline requires --approve-tightening with the current canonical contract SHA256"], "current_contract_sha256": expected}
            print(json.dumps(failure, indent=2))
            return 1
        try:
            proposal = tightened_contract(ROOT, contract)
        except ValueError as exc:
            print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, indent=2))
            return 1
        if proposal == contract:
            print(json.dumps({"status": "PASS", "changed": False}, indent=2))
            return 0
        CONTRACT_PATH.write_text(json.dumps(proposal, indent=2) + "\n", encoding="utf-8")
        print(CONTRACT_PATH.relative_to(ROOT).as_posix())
        return 0
    errors = validate()
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 1 if errors else 0
if __name__ == "__main__":
    sys.exit(main())
