"""Distribution input contract for the linked trusted-publication protocol."""

import tomllib
from pathlib import Path


def test_linked_publication_protocol_is_in_the_installed_document_resource_set() -> None:
    root = Path(__file__).resolve().parents[1]
    adr = root / "docs/adr/trusted-publication.md"
    assert adr.is_file()
    for name in ("RELEASING.md", "PUBLICATION-BLOCKERS.md"):
        assert "(adr/trusted-publication.md)" in (root / "docs" / name).read_text(encoding="utf-8")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    data_files = project["tool"]["setuptools"]["data-files"]
    patterns = data_files.get("share/world-class-seo/docs/adr", [])
    included = {path.resolve() for pattern in patterns for path in root.glob(pattern)}
    assert adr.resolve() in included, "Linked protocol ADR must be included as an installed resource"


def test_source_distribution_declares_tracked_test_helpers_and_fixture_inputs() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in ("tests/conftest.py", "tests/publication_evidence_fixtures.py",
                     "tests/publication_full_path_fixtures.py"):
        assert (root / relative).is_file(), "The test helper exists in canonical source"
    manifest = root / "MANIFEST.in"
    assert manifest.is_file(), "Source distribution must explicitly include tracked test support"
    rules = set(manifest.read_text(encoding="utf-8").splitlines())
    assert "recursive-include tests *.py" in rules
    fixtures = (
        "tests/baselines/pre-remediation-runtime.json",
        "tests/fixtures/architecture_c5a47c3/README.md",
        "tests/fixtures/architecture_c5a47c3/architecture-contract.json",
        "tests/fixtures/architecture_c5a47c3/architecture-exception-disposition.json",
        "tests/fixtures/release_readiness_20260801.json",
    )
    for relative in fixtures:
        assert (root / relative).is_file()
        assert f"include {relative}" in rules
