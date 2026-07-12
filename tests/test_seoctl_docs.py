from pathlib import Path

from scripts.generate_command_docs import render

ROOT = Path(__file__).resolve().parents[1]


def test_command_documentation_matches_registry_exactly():
    documented = (ROOT / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
    assert documented == render()


def test_every_command_has_owner_skill_network_and_resolved_handler():
    from seoctl.cli import HANDLERS
    from seoctl.registry import command_specs

    for spec in command_specs():
        assert spec.owner
        assert spec.skills
        assert spec.handler in HANDLERS
        assert callable(HANDLERS[spec.handler])
        assert spec.network
