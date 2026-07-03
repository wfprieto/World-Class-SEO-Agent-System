from __future__ import annotations

import re
from pathlib import Path

from runtime.executor import AGENT_FILE_NAMES
from runtime.routing import RequestRouter


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


def test_system_map_points_to_core_repository_sections():
    content = (ROOT / "SYSTEM_MAP.md").read_text(encoding="utf-8")
    required_paths = [
        "SYSTEM_SPEC.md",
        "agents/AGENT_INDEX.md",
        "skills/SKILL_INDEX.md",
        "skills/deep-skill-procedures.md",
        "workflows/request-routing.md",
        "knowledge/seo-quality-gates.md",
        "schemas/agent-output.schema.json",
        "adapters/README.md",
        "runtime/orchestrator.py",
        "examples/README.md",
    ]
    for path in required_paths:
        assert path in content
        assert (ROOT / path).exists(), path


def test_executor_agent_map_covers_all_agent_files():
    agent_files = {path.name for path in (ROOT / "agents").glob("*.md") if path.name != "AGENT_INDEX.md"}
    mapped_files = set(AGENT_FILE_NAMES.values())
    assert agent_files == mapped_files


def test_router_routes_to_existing_agent_files_and_workflows():
    router = RequestRouter()
    mapped_agents = set(AGENT_FILE_NAMES)
    for _keywords, lead_agent, workflow in router.ROUTES:
        assert lead_agent in mapped_agents
        assert (ROOT / workflow).exists(), workflow
