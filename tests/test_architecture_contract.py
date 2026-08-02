from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_architecture_contract import SCHEMA_PATH, validate


def _contract() -> dict:
    return {
        "schema_version": "1.0.0",
        "layers": {
            "runtime": "runtime",
            "adapters": "adapters",
            "integrations": "integrations",
            "composition": "seoctl",
        },
        "allowed_layer_edges": [
            {"source": "composition", "target": "runtime"},
            {"source": "composition", "target": "adapters"},
            {"source": "composition", "target": "integrations"},
        ],
        "exceptions": [],
        "network_modules": [],
    }


def _fixture(tmp_path: Path, contract: dict, sources: dict[str, str]) -> tuple[Path, Path]:
    for package in ("runtime", "adapters", "integrations", "seoctl"):
        package_path = tmp_path / package
        package_path.mkdir(parents=True)
        (package_path / "__init__.py").write_text("", encoding="utf-8")
    for relative, source in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    contract_path = tmp_path / "governance" / "architecture-contract.json"
    schema_path = tmp_path / "schemas" / "architecture-contract.schema.json"
    contract_path.parent.mkdir(parents=True)
    schema_path.parent.mkdir(parents=True)
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    schema_path.write_bytes(SCHEMA_PATH.read_bytes())
    return contract_path, schema_path


def test_canonical_architecture_contract_passes() -> None:
    assert validate() == []


def test_forbidden_runtime_to_integration_import_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/new_boundary.py": "from integrations.provider import Client\n"},
    )
    errors = validate(tmp_path, contract_path, schema_path)
    assert "forbidden dependency edge: runtime.new_boundary -> integrations.provider" in errors


def test_new_internal_cycle_fails_even_with_exact_exceptions(tmp_path: Path) -> None:
    contract = _contract()
    contract["exceptions"] = [
        {
            "source": "runtime.port",
            "target": "integrations.provider",
            "owner": "Architecture owner",
            "rationale": "Adversarial fixture exact edge with accountable ownership.",
            "removal_phase": "P5",
        },
        {
            "source": "integrations.provider",
            "target": "runtime.port",
            "owner": "Architecture owner",
            "rationale": "Adversarial fixture reverse edge with accountable ownership.",
            "removal_phase": "P5",
        },
    ]
    contract_path, schema_path = _fixture(
        tmp_path,
        contract,
        {
            "runtime/port.py": "from integrations.provider import Client\n",
            "integrations/provider.py": "from runtime.port import Port\n",
        },
    )
    errors = validate(tmp_path, contract_path, schema_path)
    assert any(error.startswith("internal import cycle:") for error in errors)


def test_single_dot_relative_cycle_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/a.py": "from .b import B\n",
            "runtime/b.py": "from .a import A\n",
        },
    )

    assert any(
        error.startswith("internal import cycle:")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_multi_dot_relative_cycle_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "integrations/shared.py": "from .nested.worker import Worker\n",
            "integrations/nested/__init__.py": "",
            "integrations/nested/worker.py": "from ..shared import Shared\n",
        },
    )

    assert any(
        error.startswith("internal import cycle:")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_package_init_relative_cycle_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/package/__init__.py": "from .worker import Worker\n",
            "runtime/package/worker.py": "from runtime import package\n",
        },
    )

    assert any(
        error.startswith("internal import cycle:")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_mixed_absolute_relative_cycle_fails(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/package/__init__.py": (
                "from runtime.package import worker as imported_worker\n"
            ),
            "runtime/package/worker.py": "from . import helper\n",
            "runtime/package/helper.py": "from runtime import package as imported_package\n",
        },
    )

    assert any(
        error.startswith("internal import cycle:")
        for error in validate(tmp_path, contract_path, schema_path)
    )


def test_broad_or_unknown_exception_fails_closed(tmp_path: Path) -> None:
    contract = _contract()
    broad = copy.deepcopy(contract)
    broad["exceptions"] = [
        {
            "source": "runtime",
            "target": "integrations",
            "owner": "Architecture owner",
            "rationale": "This intentionally broad mutation must be rejected by schema.",
            "removal_phase": "P5",
        }
    ]
    contract_path, schema_path = _fixture(tmp_path / "broad", broad, {})
    assert any(error.startswith("schema exceptions") for error in validate(tmp_path / "broad", contract_path, schema_path))

    unknown = copy.deepcopy(contract)
    unknown["exceptions"] = [
        {
            "source": "runtime.missing",
            "target": "integrations.missing",
            "owner": "Architecture owner",
            "rationale": "An exception must bind one currently observed exact import edge.",
            "removal_phase": "P5",
        }
    ]
    contract_path, schema_path = _fixture(tmp_path / "unknown", unknown, {})
    errors = validate(tmp_path / "unknown", contract_path, schema_path)
    assert "stale or unknown dependency exception: runtime.missing -> integrations.missing" in errors


def test_new_direct_network_module_fails_until_explicitly_owned(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"integrations/new_transport.py": "import urllib.request\n"},
    )
    errors = validate(tmp_path, contract_path, schema_path)
    assert "unapproved network-capable module: integrations/new_transport.py" in errors


def test_new_playwright_browser_module_fails_until_explicitly_owned(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"integrations/new_browser.py": "from playwright.sync_api import sync_playwright\n"},
    )

    assert "unapproved network-capable module: integrations/new_browser.py" in validate(
        tmp_path, contract_path, schema_path
    )


def test_literal_dynamic_and_process_egress_fail_until_owned(tmp_path: Path) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {
            "runtime/dynamic_client.py": (
                "import importlib\nclient = importlib.import_module('httpx')\n"
            ),
            "runtime/process_client.py": (
                "import subprocess\nsubprocess.run(['curl', 'https://example.test'])\n"
            ),
        },
    )
    errors = validate(tmp_path, contract_path, schema_path)

    assert "unapproved network-capable module: runtime/dynamic_client.py" in errors
    assert "unapproved network-capable module: runtime/process_client.py" in errors


@pytest.mark.parametrize(
    ("import_line", "call"),
    [
        ("from subprocess import run", "run(['curl', 'https://example.test'])"),
        (
            "from subprocess import run as execute",
            "execute(['curl', 'https://example.test'])",
        ),
        ("from subprocess import Popen", "Popen(['curl', 'https://example.test'])"),
        (
            "from subprocess import Popen as launch",
            "launch(['curl', 'https://example.test'])",
        ),
        (
            "from subprocess import check_output",
            "check_output(['curl', 'https://example.test'])",
        ),
        (
            "from subprocess import check_output as capture",
            "capture(['curl', 'https://example.test'])",
        ),
    ],
)
def test_imported_subprocess_egress_fails_until_owned(
    tmp_path: Path, import_line: str, call: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/process_client.py": f"{import_line}\n{call}\n"},
    )

    assert "unapproved network-capable module: runtime/process_client.py" in validate(
        tmp_path, contract_path, schema_path
    )


@pytest.mark.parametrize(
    ("import_line", "call"),
    [
        ("from importlib import import_module", "import_module('httpx')"),
        ("from importlib import import_module as load", "load('httpx')"),
    ],
)
def test_imported_dynamic_egress_fails_until_owned(
    tmp_path: Path, import_line: str, call: str
) -> None:
    contract_path, schema_path = _fixture(
        tmp_path,
        _contract(),
        {"runtime/dynamic_client.py": f"{import_line}\nclient = {call}\n"},
    )

    assert "unapproved network-capable module: runtime/dynamic_client.py" in validate(
        tmp_path, contract_path, schema_path
    )


def test_network_allowlist_cannot_hide_missing_module(tmp_path: Path) -> None:
    contract = _contract()
    contract["network_modules"] = ["runtime/missing.py"]
    contract_path, schema_path = _fixture(tmp_path, contract, {})
    assert "stale or missing network-module entry: runtime/missing.py" in validate(
        tmp_path, contract_path, schema_path
    )
