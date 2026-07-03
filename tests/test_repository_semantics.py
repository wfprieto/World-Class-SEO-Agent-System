from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_every_agent_has_mission_required_evidence_primary_skills_and_output():
    for path in (ROOT / "agents").glob("*.md"):
        if path.name == "AGENT_INDEX.md":
            continue
        content = path.read_text(encoding="utf-8")
        assert "## Mission" in content, path
        assert "## Required Evidence" in content, path
        assert "## Primary Skills" in content, path
        assert "## Output" in content, path


def test_every_template_referenced_by_agents_exists():
    template_refs = set()
    for path in (ROOT / "agents").glob("*.md"):
        content = path.read_text(encoding="utf-8")
        template_refs.update(re.findall(r"templates/([a-z0-9-]+\.md)", content))
    for template in template_refs:
        assert (ROOT / "templates" / template).exists(), template


def test_core_workflows_have_mermaid_diagrams():
    for path in (ROOT / "workflows").glob("*.md"):
        content = path.read_text(encoding="utf-8")
        assert "```mermaid" in content, path


def test_every_indexed_skill_has_deep_procedure():
    index = (ROOT / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
    procedures = (ROOT / "skills" / "deep-skill-procedures.md").read_text(encoding="utf-8")
    indexed_skills = set(re.findall(r"`([a-z0-9-]+)`", index))
    procedure_skills = set(re.findall(r"^## ([a-z0-9-]+)$", procedures, re.MULTILINE))
    assert not indexed_skills - procedure_skills
