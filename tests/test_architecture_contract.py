from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.validate_architecture_contract import ROOT, SCHEMA_PATH, validate


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


def test_network_allowlist_cannot_hide_missing_module(tmp_path: Path) -> None:
    contract = _contract()
    contract["network_modules"] = ["runtime/missing.py"]
    contract_path, schema_path = _fixture(tmp_path, contract, {})
    assert "stale or missing network-module entry: runtime/missing.py" in validate(
        tmp_path, contract_path, schema_path
    )
