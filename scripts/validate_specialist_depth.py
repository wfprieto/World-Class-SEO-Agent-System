"""Validate bounded specialist decision depth and exact runtime context."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.capability_resolver import CapabilityResolutionError, CapabilityResolver  # noqa: E402
from runtime.specialist_decision import (  # noqa: E402
    INTEGRITY_PATH,
    SEMANTIC_RULE_MARKERS,
    runtime_integrity_errors,
)
from runtime.specialist_decision import (  # noqa: E402
    PLAYBOOK_PATH as RUNTIME_PLAYBOOK_PATH,
)
from runtime.specialist_decision import (  # noqa: E402
    STANDARD_PATH as RUNTIME_STANDARD_PATH,
)

STANDARD_PATH = Path("skills/specialist-decision-standard.md")
PLAYBOOK_PATH = Path("skills/specialist-depth-playbooks.md")
PRIORITY_AGENTS = {
    "Negative SEO & Security Agent": "agents/negative-seo-security-agent.md",
    "SEO Accessibility Agent": "agents/seo-accessibility-agent.md",
    "International & Multilingual SEO Agent": "agents/international-multilingual-seo-agent.md",
    "Local SEO Agent": "agents/local-seo-agent.md",
    "Competitive Intelligence Agent": "agents/competitive-intelligence-agent.md",
    "Predictive SEO Trend Agent": "agents/predictive-seo-trend-agent.md",
    "Visual & Video Search Agent": "agents/visual-video-search-agent.md",
    "SEO Compliance & Legal Agent": "agents/seo-compliance-legal-agent.md",
}
STANDARD_HEADINGS = {
    "Decision states",
    "Evidence sufficiency",
    "Decision procedure",
    "Failure, abstention, and escalation",
    "Edge-case discipline",
    "Example contract",
}
PLAYBOOK_HEADINGS = {
    "Decision branches",
    "Evidence sufficiency",
    "Failure, abstention, and escalation",
    "Edge cases and examples",
}
DECISION_STATES = {"READY", "PARTIAL", "BLOCKED", "ABSTAIN", "ESCALATE"}
Mutation = tuple[str, dict[str, str], str, str, str]


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^## ", text[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.start() : end].strip()


def _playbook_sections(text: str) -> dict[str, list[str]]:
    matches = list(re.finditer(r"^## Agent: `([^`]+)`\s*$", text, re.MULTILINE))
    sections: dict[str, list[str]] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.setdefault(match.group(1), []).append(text[match.start() : end].strip())
    return sections


def _standard_errors(text: str) -> list[str]:
    errors = [
        f"specialist standard missing section: {heading}"
        for heading in sorted(STANDARD_HEADINGS)
        if not _section(text, heading)
    ]
    errors.extend(
        f"specialist standard missing decision state: {state}"
        for state in sorted(DECISION_STATES)
        if f"`{state}`" not in text
    )
    return errors


def _agent_playbook_errors(
    docs: dict[str, str], playbook_text: str
) -> list[str]:
    errors: list[str] = []
    sections = _playbook_sections(playbook_text)
    canonical_paths = (STANDARD_PATH.as_posix(), PLAYBOOK_PATH.as_posix())
    for agent in PRIORITY_AGENTS:
        protocol = _section(docs.get(agent, ""), "Decision Protocol")
        if not protocol:
            errors.append(f"specialist agent missing Decision Protocol: {agent}")
        else:
            errors.extend(
                f"specialist agent protocol missing canonical path: {agent} -> {path}"
                for path in canonical_paths
                if path not in protocol
            )
        agent_sections = sections.get(agent, [])
        if len(agent_sections) != 1:
            errors.append(
                f"specialist playbook must occur exactly once: {agent} -> {len(agent_sections)}"
            )
            continue
        playbook = agent_sections[0]
        errors.extend(
            f"specialist playbook missing {heading}: {agent}"
            for heading in sorted(PLAYBOOK_HEADINGS)
            if not re.search(rf"^### {re.escape(heading)}\s*$", playbook, re.MULTILINE)
        )
        if "Good:" not in playbook or "Bad:" not in playbook:
            errors.append(f"specialist playbook missing good/bad examples: {agent}")
        if "`BLOCKED`" not in playbook or "`ABSTAIN`" not in playbook:
            errors.append(f"specialist playbook missing stop states: {agent}")
        errors.extend(
            f"specialist playbook missing semantic rule: {agent} -> {marker}"
            for marker in SEMANTIC_RULE_MARKERS[agent]
            if marker not in playbook
        )
    extras = sorted(set(sections) - set(PRIORITY_AGENTS))
    if extras:
        errors.append(f"specialist playbook has undeclared agents: {extras}")
    return errors


def _runtime_errors(root: Path) -> list[str]:
    errors: list[str] = []
    resolver = CapabilityResolver(root)
    for agent in PRIORITY_AGENTS:
        try:
            context = resolver.load_context(agent)
        except CapabilityResolutionError as exc:
            errors.append(f"specialist runtime context failed: {agent} -> {exc}")
            continue
        paths = [row["path"] for row in context["skill_context"]]
        if STANDARD_PATH.as_posix() not in paths:
            errors.append(f"specialist runtime missing decision standard: {agent}")
        own_prefix = f"{PLAYBOOK_PATH.as_posix()}#{agent}"
        if paths.count(own_prefix) != 1:
            errors.append(f"specialist runtime missing exact playbook: {agent}")
        payload = "\n".join(row["content"] for row in context["skill_context"])
        errors.extend(
            f"specialist runtime missing exact skill definition: {agent} -> {skill}"
            for skill in context["bundle"].skills
            if not resolver._definition_pattern(skill).search(payload)
        )
    return errors


def _integrity_errors(
    standard: str, playbooks: str, integrity: str
) -> list[str]:
    errors: list[str] = []
    sections = _playbook_sections(playbooks)
    for agent in PRIORITY_AGENTS:
        agent_sections = sections.get(agent, [])
        if len(agent_sections) != 1:
            continue
        context = [
            {"path": INTEGRITY_PATH, "content": integrity},
            {"path": RUNTIME_STANDARD_PATH, "content": standard},
            {
                "path": f"{RUNTIME_PLAYBOOK_PATH}#{agent}",
                "content": agent_sections[0],
            },
        ]
        errors.extend(runtime_integrity_errors(agent, context))
    return errors


def validate_documents(
    root: Path,
    *,
    agent_docs: dict[str, str] | None = None,
    standard: str | None = None,
    playbooks: str | None = None,
    integrity: str | None = None,
    check_runtime: bool = True,
) -> list[str]:
    docs = agent_docs or {
        agent: (root / path).read_text(encoding="utf-8")
        for agent, path in PRIORITY_AGENTS.items()
    }
    standard_text = (
        standard
        if standard is not None
        else (root / STANDARD_PATH).read_text(encoding="utf-8")
    )
    playbook_text = (
        playbooks
        if playbooks is not None
        else (root / PLAYBOOK_PATH).read_text(encoding="utf-8")
    )
    integrity_text = (
        integrity
        if integrity is not None
        else (root / INTEGRITY_PATH).read_text(encoding="utf-8")
    )
    errors = [
        *_standard_errors(standard_text),
        *_agent_playbook_errors(docs, playbook_text),
        *_integrity_errors(standard_text, playbook_text, integrity_text),
    ]
    if check_runtime and not errors:
        errors.extend(_runtime_errors(root))
    return errors


def validate_repository(root: Path = ROOT) -> list[str]:
    return validate_documents(root)


def _replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise ValueError(f"mutation source absent: {old}")
    return text.replace(old, new, 1)


def _structural_mutations(
    docs: dict[str, str], standard: str, playbooks: str
) -> list[Mutation]:
    mutations: list[Mutation] = []
    for agent in (
        "Negative SEO & Security Agent",
        "SEO Accessibility Agent",
        "International & Multilingual SEO Agent",
    ):
        candidate = copy.deepcopy(docs)
        candidate[agent] = candidate[agent].replace("## Decision Protocol", "## Protocol Removed", 1)
        mutations.append((f"remove-protocol-{agent}", candidate, standard, playbooks, "missing Decision Protocol"))

    for heading in ("Decision states", "Evidence sufficiency", "Failure, abstention, and escalation"):
        candidate_standard = _replace_once(standard, f"## {heading}", f"## Removed {heading}")
        mutations.append((f"remove-standard-{heading}", docs, candidate_standard, playbooks, "standard missing section"))

    candidate_standard = standard.replace("`ABSTAIN`", "ABSTAIN")
    mutations.append(("remove-abstain-state", docs, candidate_standard, playbooks, "missing decision state"))

    for agent, heading in (
        ("Negative SEO & Security Agent", "Decision branches"),
        ("SEO Accessibility Agent", "Evidence sufficiency"),
        ("Local SEO Agent", "Failure, abstention, and escalation"),
        ("Predictive SEO Trend Agent", "Edge cases and examples"),
    ):
        section = _playbook_sections(playbooks)[agent][0]
        weakened = section.replace(f"### {heading}", f"### Removed {heading}", 1)
        candidate_playbooks = playbooks.replace(section, weakened, 1)
        mutations.append((f"remove-playbook-{agent}-{heading}", docs, standard, candidate_playbooks, "playbook missing"))

    duplicate = _playbook_sections(playbooks)["Visual & Video Search Agent"][0]
    mutations.append(("duplicate-playbook", docs, standard, f"{playbooks}\n\n{duplicate}\n", "must occur exactly once"))
    return mutations


def _semantic_mutations(
    docs: dict[str, str], standard: str, playbooks: str
) -> list[Mutation]:
    mutations: list[Mutation] = []

    for agent, markers in SEMANTIC_RULE_MARKERS.items():
        marker = markers[0]
        candidate_playbooks = _replace_once(playbooks, marker, "SEMANTIC RULE REMOVED")
        mutations.append(
            (
                f"remove-semantic-rule-{agent}",
                docs,
                standard,
                candidate_playbooks,
                "missing semantic rule",
            )
        )

    agent = "Negative SEO & Security Agent"
    section = _playbook_sections(playbooks)[agent][0]
    preserved_tokens = "\n".join(
        (
            f"## Agent: `{agent}`",
            "### Decision branches",
            "NONSENSE",
            "### Evidence sufficiency",
            "NONSENSE",
            "### Failure, abstention, and escalation",
            "`BLOCKED` `ABSTAIN`",
            "### Edge cases and examples",
            *SEMANTIC_RULE_MARKERS[agent],
            "Good: nonsense. Bad: nonsense.",
        )
    )
    mutations.append(
        (
            "replace-domain-procedures-preserve-contract-tokens",
            docs,
            standard,
            playbooks.replace(section, preserved_tokens, 1),
            "digest mismatch",
        )
    )
    return mutations


def run_mutation_suite(root: Path = ROOT) -> dict[str, Any]:
    docs = {
        agent: (root / path).read_text(encoding="utf-8")
        for agent, path in PRIORITY_AGENTS.items()
    }
    standard = (root / STANDARD_PATH).read_text(encoding="utf-8")
    playbooks = (root / PLAYBOOK_PATH).read_text(encoding="utf-8")
    integrity = (root / INTEGRITY_PATH).read_text(encoding="utf-8")
    mutations = [
        *_structural_mutations(docs, standard, playbooks),
        *_semantic_mutations(docs, standard, playbooks),
    ]

    results = []
    for name, candidate_docs, candidate_standard, candidate_playbooks, expected in mutations:
        errors = validate_documents(
            root,
            agent_docs=candidate_docs,
            standard=candidate_standard,
            playbooks=candidate_playbooks,
            integrity=integrity,
            check_runtime=False,
        )
        results.append(
            {
                "name": name,
                "killed": any(expected in error for error in errors),
                "expected": expected,
                "errors": errors,
            }
        )
    return {
        "status": "PASS" if all(item["killed"] for item in results) else "FAIL",
        "mutants": len(results),
        "killed": sum(bool(item["killed"]) for item in results),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutations", action="store_true")
    args = parser.parse_args()
    errors = validate_repository()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.mutations:
        result = run_mutation_suite()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    print(f"Specialist depth: PASS ({len(PRIORITY_AGENTS)} priority agents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
