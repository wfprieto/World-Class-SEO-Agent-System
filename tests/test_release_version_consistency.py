from __future__ import annotations

from pathlib import Path

from scripts.validate_release_version import state_legend, validate


ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path, changelog: str, manifest: str) -> Path:
    (tmp_path / "docs").mkdir()
    (tmp_path / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{changelog}] - 2026-07-11\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "INTEGRATION-MANIFEST.md").write_text(
        f"# Integration Record\n\n**Version:** {manifest}\n",
        encoding="utf-8",
    )
    return tmp_path


def test_manifest_and_changelog_version_mismatch_fails_validation(tmp_path: Path):
    root = _fixture(tmp_path, "1.7.0", "1.6.0")
    failures = validate(root)
    assert failures
    assert "disagree" in failures[0]


def test_current_repository_version_sources_are_consistent_after_fix():
    assert validate(ROOT) == []


def test_version_validator_distinguishes_integration_release_publication_and_deployment():
    legend = state_legend()
    assert set(legend) == {
        "integrated_into_main",
        "released_or_tagged",
        "published_or_distributed",
        "deployed",
    }
    assert len(set(legend.values())) == 4
