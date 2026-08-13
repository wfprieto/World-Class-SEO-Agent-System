from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_SKILL = ROOT / "skills" / "seo-flow-skill.md"
FLOW_DIR = ROOT / "skills" / "flow-prompts"
STAGES = ("find", "leverage", "optimize", "win", "local")


def test_flow_prompt_skill_registers_every_stage_file():
    body = FLOW_SKILL.read_text(encoding="utf-8")
    for stage in STAGES:
        stage_path = FLOW_DIR / f"{stage}.md"
        assert stage_path.exists()
        assert f"`flow-prompts/{stage}.md`" in body


def test_flow_prompt_files_are_stage_references_not_skill_duplicates():
    skill_index = (ROOT / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
    for stage in STAGES:
        stage_body = (FLOW_DIR / f"{stage}.md").read_text(encoding="utf-8")
        assert f'"stage": "{stage}"' in stage_body
        assert "## Output Contract" in stage_body
        assert f"`flow-{stage}`" not in skill_index
