"""Resolve exact agent, skill, package, knowledge, and template context."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime.assets import resolve_asset_root


class CapabilityResolutionError(RuntimeError):
    """Raised when capability metadata is missing or invalid."""


@dataclass(frozen=True)
class CapabilityBundle:
    agent: str
    agent_file: str
    skills: tuple[str, ...]
    skill_files: tuple[str, ...]
    knowledge_files: tuple[str, ...]
    templates: tuple[str, ...]
    required_evidence: tuple[str, ...]


class CapabilityResolver:
    """Assemble canonical runtime context with a non-destructive product-proof overlay."""

    _SPECIALIST_AGENTS = {
        "Competitive Intelligence Agent",
        "International & Multilingual SEO Agent",
        "Local SEO Agent",
        "Negative SEO & Security Agent",
        "Predictive SEO Trend Agent",
        "SEO Accessibility Agent",
        "SEO Compliance & Legal Agent",
        "Visual & Video Search Agent",
    }
    _SKILL_DEFINITION_EXCLUDES = {
        "SKILL_INDEX.md",
        "deep-skill-procedures.md",
        "product-proof-procedures.md",
        "specialist-decision-standard.md",
        "specialist-depth-playbooks.md",
    }

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = resolve_asset_root(repo_root)
        path = self.repo_root / "orchestration" / "capability-registry.json"
        if not path.exists():
            raise CapabilityResolutionError(f"capability registry missing: {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.registry: dict[str, dict[str, Any]] = raw.get("agents", {})
        self.shared: dict[str, Any] = raw.get("shared", {})
        package_raw = json.loads(
            (self.repo_root / "skills" / "package-registry.json").read_text(encoding="utf-8")
        )
        self.packages: dict[str, dict[str, Any]] = package_raw.get("packages", {})
        self.package_document = str(package_raw.get("package_document", ""))
        overlay_path = self.repo_root / "orchestration" / "product-proof-capability-overlay.json"
        overlay: dict[str, Any] = {}
        if overlay_path.exists():
            overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
        self.shared_knowledge_files = tuple(
            str(value) for value in overlay.get("shared_knowledge_files", [])
        )
        self.agent_overrides: dict[str, dict[str, Any]] = overlay.get(
            "agent_overrides", {}
        )

    @staticmethod
    def _merge(*values: list[Any] | tuple[Any, ...]) -> tuple[str, ...]:
        output: list[str] = []
        for group in values:
            for value in group:
                text = str(value)
                if text not in output:
                    output.append(text)
        return tuple(output)

    def bundle(self, agent_name: str) -> CapabilityBundle:
        row = self.registry.get(agent_name)
        if row is None:
            raise CapabilityResolutionError(f"agent not registered: {agent_name}")
        override = self.agent_overrides.get(agent_name, {})
        skills = self._merge(row.get("skills", []), override.get("skills", []))
        grouped_files = self._merge(
            row.get("skill_files", []), override.get("skill_files", [])
        )
        package_files = (
            (self.package_document,)
            if self.package_document and any(skill in self.packages for skill in skills)
            else ()
        )
        skill_files = self._merge(grouped_files, package_files)
        bundle = CapabilityBundle(
            agent=agent_name,
            agent_file=str(row["agent_file"]),
            skills=skills,
            skill_files=skill_files,
            knowledge_files=self._merge(
                row.get("knowledge_files", []),
                self.shared_knowledge_files,
                override.get("knowledge_files", []),
            ),
            templates=self._merge(row.get("templates", []), override.get("templates", [])),
            required_evidence=self._merge(
                row.get("required_evidence", []), override.get("required_evidence", [])
            ),
        )
        for relative in (
            bundle.agent_file,
            *bundle.skill_files,
            *bundle.knowledge_files,
            *bundle.templates,
        ):
            if not (self.repo_root / relative).exists():
                raise CapabilityResolutionError(
                    f"{agent_name} capability path does not exist: {relative}"
                )
        return bundle

    def load_context(self, agent_name: str) -> dict[str, Any]:
        bundle = self.bundle(agent_name)
        skill_context = [
            {"path": path, "content": self._read(path)}
            for path in bundle.skill_files
        ]
        skill_context.extend(self._supplemental_skill_definitions(bundle))
        skill_context.extend(self._specialist_decision_context(agent_name))
        return {
            "bundle": bundle,
            "agent_spec": self._read(bundle.agent_file),
            "skill_context": skill_context,
            "deep_procedures": self._procedure_sections(bundle.skills),
            "knowledge_context": [
                {"path": path, "content": self._read(path)}
                for path in bundle.knowledge_files
            ],
            "template_context": [
                {"path": path, "content": self._read(path)}
                for path in bundle.templates
            ],
        }

    def validate(self) -> dict[str, Any]:
        agents = []
        product_proof_agents = []
        for agent_name in sorted(self.registry):
            bundle = self.bundle(agent_name)
            if "product-proof-technical-audit" in bundle.skills:
                product_proof_agents.append(agent_name)
            agents.append(
                {
                    "agent": agent_name,
                    "skills": list(bundle.skills),
                    "paths": [
                        bundle.agent_file,
                        *bundle.skill_files,
                        *bundle.knowledge_files,
                        *bundle.templates,
                    ],
                }
            )
        return {
            "status": "ok",
            "agent_count": len(agents),
            "package_count": len(self.packages),
            "product_proof_agent_count": len(product_proof_agents),
            "product_proof_agents": product_proof_agents,
            "shared_product_proof_knowledge": list(self.shared_knowledge_files),
            "agents": agents,
        }

    def _read(self, relative: str) -> str:
        return (self.repo_root / relative).read_text(encoding="utf-8")

    @staticmethod
    def _definition_pattern(skill: str) -> re.Pattern[str]:
        return re.compile(
            rf"^## (?:Skill: )?`{re.escape(skill)}`\s*$",
            re.MULTILINE,
        )

    @staticmethod
    def _section(text: str, start: int) -> str:
        next_heading = re.search(r"^## ", text[start + 1 :], re.MULTILINE)
        end = start + 1 + next_heading.start() if next_heading else len(text)
        return text[start:end].strip()

    def _definition_candidates(self, skill: str) -> list[tuple[str, str]]:
        candidates: list[tuple[str, str]] = []
        for path in sorted((self.repo_root / "skills").glob("*.md")):
            if path.name in self._SKILL_DEFINITION_EXCLUDES:
                continue
            text = path.read_text(encoding="utf-8")
            for match in self._definition_pattern(skill).finditer(text):
                candidates.append(
                    (
                        path.relative_to(self.repo_root).as_posix(),
                        self._section(text, match.start()),
                    )
                )
        return candidates

    def _supplemental_skill_definitions(
        self, bundle: CapabilityBundle
    ) -> list[dict[str, str]]:
        """Load exact canonical sections omitted by an agent's grouped skill files."""
        loaded = "\n".join(self._read(path) for path in bundle.skill_files)
        supplemental: list[dict[str, str]] = []
        for skill in bundle.skills:
            if self._definition_pattern(skill).search(loaded):
                continue
            candidates = self._definition_candidates(skill)
            if len(candidates) > 1:
                paths = ", ".join(path for path, _content in candidates)
                raise CapabilityResolutionError(
                    f"ambiguous canonical skill definition for {skill}: {paths}"
                )
            if candidates:
                path, content = candidates[0]
                supplemental.append({"path": f"{path}#{skill}", "content": content})
        return supplemental

    def _specialist_decision_context(self, agent_name: str) -> list[dict[str, str]]:
        if agent_name not in self._SPECIALIST_AGENTS:
            return []
        standard_path = "skills/specialist-decision-standard.md"
        playbook_path = "skills/specialist-depth-playbooks.md"
        integrity_path = "governance/specialist-playbook-integrity.json"
        standard = self._read(standard_path)
        playbooks = self._read(playbook_path)
        integrity = self._read(integrity_path)
        if not standard or not playbooks or not integrity:
            raise CapabilityResolutionError(
                f"specialist decision context missing for {agent_name}"
            )
        heading = re.compile(
            rf"^## Agent: `{re.escape(agent_name)}`\s*$", re.MULTILINE
        )
        matches = list(heading.finditer(playbooks))
        if len(matches) != 1:
            raise CapabilityResolutionError(
                f"specialist playbook must resolve exactly once: {agent_name}"
            )
        return [
            {"path": integrity_path, "content": integrity},
            {"path": standard_path, "content": standard},
            {
                "path": f"{playbook_path}#{agent_name}",
                "content": self._section(playbooks, matches[0].start()),
            },
        ]

    def _procedure_sections(self, skills: tuple[str, ...]) -> list[dict[str, str]]:
        if not skills:
            return []
        paths = [self.repo_root / "skills" / "deep-skill-procedures.md"]
        product_proof = self.repo_root / "skills" / "product-proof-procedures.md"
        if product_proof.exists():
            paths.append(product_proof)
        sections: dict[str, str] = {}
        for path in paths:
            text = path.read_text(encoding="utf-8")
            matches = list(re.finditer(r"^## ([a-z0-9-]+)\s*$", text, re.MULTILINE))
            for index, match in enumerate(matches):
                end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
                skill = match.group(1)
                if skill in sections:
                    raise CapabilityResolutionError(
                        f"duplicate deep procedure heading across canonical files: {skill}"
                    )
                sections[skill] = text[match.start():end].strip()
        return [{"skill": skill, "content": sections.get(skill, "")} for skill in skills]
