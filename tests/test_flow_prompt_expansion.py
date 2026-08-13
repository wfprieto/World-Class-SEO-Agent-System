from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FLOW_DIR = ROOT / "skills" / "flow-prompts"
FLOW_SKILL = ROOT / "skills" / "seo-flow-skill.md"

STAGES = {
    "find": "opportunity_map",
    "leverage": "authority_actions",
    "optimize": "recommended_changes",
    "win": "win_plan",
    "local": "local_action_plan",
}

REQUIRED_STAGE_SECTIONS = (
    "## Use When",
    "## Owner Agents",
    "## Required Inputs",
    "## Stop Conditions",
    "## Decision Tree",
    "## Prompt Blocks",
    "## Output Contract",
)

FORBIDDEN_SOURCE_LABELS = (
    "AgriciDaniel",
    "claude-seo",
    "every-app",
    "open-seo",
    "stefankirkegaard",
    "TahaHachana",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_flow_stage_files_have_deep_operating_contracts():
    for stage, required_output_key in STAGES.items():
        body = _read(FLOW_DIR / f"{stage}.md")

        for section in REQUIRED_STAGE_SECTIONS:
            assert section in body, f"{stage}.md is missing {section}"

        assert f'"stage": "{stage}"' in body
        assert f'"{required_output_key}"' in body
        assert "Evidence" in body or "evidence" in body
        assert "Risk" in body or "risk" in body
        assert body.count("## Prompt:") >= 4, f"{stage}.md needs several actionable prompt blocks"


def test_flow_stage_files_remain_clean_room_and_model_agnostic():
    for stage in STAGES:
        body = _read(FLOW_DIR / f"{stage}.md")

        for forbidden in FORBIDDEN_SOURCE_LABELS:
            assert forbidden not in body

        assert "ChatGPT" not in body
        assert "Claude" not in body
        assert "Gemini" not in body


def test_flow_skill_routes_public_copy_and_source_governance():
    body = _read(FLOW_SKILL)

    assert "evaluation/upgrade-source-matrix.json" in body
    assert "anti-AI writing" in body
    assert "SEO Compliance & Legal Agent" in body
    assert "No fabricated statistics" in body

    for stage in STAGES:
        assert f"`flow-prompts/{stage}.md`" in body


def test_flow_files_do_not_contain_common_mojibake():
    paths = [FLOW_SKILL, *FLOW_DIR.glob("*.md")]
    bad_tokens = ("â", "\u2014", "\u2013")

    for path in paths:
        body = _read(path)
        for token in bad_tokens:
            assert token not in body, f"{path.name} contains non-ASCII or mojibake token {token!r}"
