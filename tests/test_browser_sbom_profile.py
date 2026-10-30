"""Resolve declared optional SBOM components from the dedicated browser lock."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import pytest

from scripts.generate_sbom import build_sbom

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_render_components_use_the_optional_browser_lock():
    payload = build_sbom(ROOT)
    render = {
        component["name"].lower(): component
        for component in payload["components"]
        if {"name": "wcseo:optional_group", "value": "render"} in component["properties"]
    }
    assert set(render) == {"playwright", "pyee"}
    for name, version in {"playwright": "1.64.1", "pyee": "13.0.1"}.items():
        assert render[name].get("version") == version
        assert render[name]["purl"] == f"pkg:pypi/{name}@{version}"
        assert {"name": "wcseo:resolution", "value": "LOCKED"} in render[name]["properties"]


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "2.0.0"\n'
        'dependencies = ["tenacity>=8"]\n'
        '[project.optional-dependencies]\n'
        'render = ["playwright>=1.64.1,<2", "pyee>=13,<14"]\n',
        encoding="utf-8",
    )
    (tmp_path / "requirements-dev.txt").write_text(
        "tenacity==9.1.4\ntyping-extensions==4.16.0\n", encoding="utf-8"
    )
    return tmp_path


def _browser_lock(project, *, shared_name="typing-extensions", shared_version="4.16.0"):
    (project / "requirements-browser.txt").write_text(
        "playwright==1.64.1\npyee==13.0.1\ngreenlet==3.5.6\n"
        f"{shared_name}=={shared_version}\n",
        encoding="utf-8",
    )


def test_absent_optional_lock_remains_truthfully_unresolved(project):
    payload = build_sbom(project)
    optional = [item for item in payload["components"] if item["scope"] == "optional"]
    assert {item["name"] for item in optional} == {"playwright", "pyee"}
    assert all("version" not in item and "@" not in item["purl"] for item in optional)
    assert all({"name": "wcseo:resolution", "value": "DECLARED_OPTIONAL_UNRESOLVED"}
               in item["properties"] for item in optional)


def test_optional_profile_resolves_only_declared_inventory(project):
    _browser_lock(project)
    components = build_sbom(project)["components"]
    assert {item["name"] for item in components} == {"tenacity", "playwright", "pyee"}
    assert len(components) == 3  # Neither profile's undeclared transitives are inventoried.
    assert all({"name": "wcseo:resolution", "value": "LOCKED"} in item["properties"]
               for item in components)
    assert next(item for item in components if item["name"] == "tenacity")["scope"] == "required"


@pytest.mark.parametrize("alias", ["typing-extensions", "typing_extensions", "Typing.Extensions"])
def test_shared_pin_conflicts_fail_closed_even_for_undeclared_transitives(project, alias):
    _browser_lock(project, shared_name=alias, shared_version="4.17.0")
    with pytest.raises(ValueError, match=r"conflicting.*typing-extensions==4.16.0.*4.17.0"):
        build_sbom(project)


def test_optional_lock_cannot_hide_a_missing_required_runtime_pin(project):
    (project / "requirements-dev.txt").write_text("typing-extensions==4.16.0\n")
    _browser_lock(project)
    browser = project / "requirements-browser.txt"
    browser.write_text(browser.read_text() + "tenacity==9.1.4\n")
    with pytest.raises(ValueError, match="required dependency is not resolved in requirements-dev.txt: tenacity"):
        build_sbom(project)


def test_missing_required_lock_keeps_existing_failure_semantics(project):
    (project / "requirements-dev.txt").unlink()
    _browser_lock(project)
    with pytest.raises(ValueError, match="dependency lock is missing"):
        build_sbom(project)


def test_sbom_uuid_metadata_and_output_remain_deterministic(project):
    _browser_lock(project)
    first, second = build_sbom(project), build_sbom(project)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    digest = hashlib.sha256((project / "pyproject.toml").read_bytes()).hexdigest()
    serial = uuid.uuid5(uuid.NAMESPACE_URL, f"wcseo:{digest}")
    assert first["serialNumber"] == f"urn:uuid:{serial}"
    assert first["metadata"] == {
        "component": {"type": "application", "name": "world-class-seo-agent-system", "version": "2.0.0"},
        "properties": [{"name": "wcseo:pyproject_sha256", "value": digest}],
    }
    assert (first["bomFormat"], first["specVersion"], first["version"]) == ("CycloneDX", "1.5", 1)
