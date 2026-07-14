from __future__ import annotations
import json
from datetime import date
from pathlib import Path
import pytest
from runtime.capability_resolver import CapabilityResolver
from scripts.generate_release_manifest import build_manifest
from scripts.generate_skill_index import render as render_skill_index
from scripts.render_content_prompt import compose,list_workflows
from scripts.validate_reference_freshness import validate as validate_references
ROOT=Path(__file__).resolve().parents[1]
def _json(path):return json.loads((ROOT/path).read_text(encoding="utf-8-sig"))
def _catalog_skills():
 catalog=_json("skills/skill-catalog.json");return [s for c in catalog["categories"] for s in c["skills"]]
def test_skill_catalog_and_generated_index_are_canonical():
 skills=_catalog_skills();assert len(skills)>0;assert len(set(skills))==len(skills);assert (ROOT/"skills/SKILL_INDEX.md").read_text(encoding="utf-8")==render_skill_index()
def test_release_manifest_skill_count_uses_canonical_catalog():
 expected=len(_catalog_skills());assert build_manifest(ROOT)["skill_count"]==expected;assert f"- Indexed skills: {expected}" in render_skill_index()
def test_twenty_priority_packages_are_synchronized_and_anchored():
 p=_json("skills/package-registry.json");r=p["packages"];d=(ROOT/p["package_document"]).read_text(encoding="utf-8");assert len(r)==20
 for skill,row in r.items():assert f'id="{row["anchor"]}"' in d;assert row["references"];assert p["defaults"]["quality_gate"];assert p["defaults"]["failure_states"]
def test_runtime_loads_package_document_without_replacing_grouped_context():
 resolver=CapabilityResolver(ROOT);technical=resolver.bundle("SEO Technical Agent");assert "skills/core-skills.md" in technical.skill_files;assert "skills/packages/PRIORITY_SKILL_PACKAGES.md" in technical.skill_files;assert "product-proof-technical-audit" in technical.skills;assert "knowledge/seo-claim-registry.json" in technical.knowledge_files;content=resolver.bundle("SEO Copywriter/Content Agent");assert "skills/packages/PRIORITY_SKILL_PACKAGES.md" in content.skill_files;assert "knowledge/source-assets/content-information-gain.md" in content.knowledge_files;report=resolver.validate();assert report["package_count"]==20;assert report["product_proof_agent_count"]>=8
def test_reference_registry_is_current_and_complete():
 r=_json("knowledge/reference-registry.json");assert len(r["entries"])==29;assert validate_references(as_of=date(2026,7,12))==[]
def test_prompt_manifest_has_no_orphans_and_composes_deterministically():
 m=_json("prompts/prompt-manifest.json");assert len(list_workflows())==8;v={"audience":"SEO leaders","business_goal":"qualified demand","primary_question":"What should we publish?","intent":"informational","relevance_evidence":"RELEVANT","serp_evidence":"Observed mixed result types","source_register":"s1: official source"};first=compose("content-brief",v);assert first==compose("content-brief",v);assert "Evidence contract" in first["prompt"];assert "What should we publish?" in first["prompt"];assert "{{" not in first["prompt"];components={c for row in m["workflows"].values() for c in row["components"]};assert components==set(m["components"])
def test_prompt_composition_rejects_missing_and_unknown_inputs():
 with pytest.raises(ValueError,match="missing prompt inputs"):compose("content-brief",{})
 with pytest.raises(ValueError,match="unknown prompt inputs"):compose("executive-summary",{"audience":"CEO","accepted_findings":"A","business_impact":"B","priorities":"C","open_risks":"D","secret":"not allowed"})
