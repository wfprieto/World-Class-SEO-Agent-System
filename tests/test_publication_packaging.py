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
