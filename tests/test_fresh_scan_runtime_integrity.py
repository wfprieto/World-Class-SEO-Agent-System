"""Regression coverage for the fresh scan's runtime authority boundaries."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import main as legacy_cli
from runtime.capability_resolver import CapabilityResolutionError, CapabilityResolver
from runtime.execution_limits import ExecutionLimits, InvalidExecutionLimits
from runtime.executor import AgentExecutor
from runtime.llm import EchoLLMClient, LLMResponse
from runtime.run_budget import BudgetExceeded, RunBudget
from runtime.safe_paths import UnsafeRepositoryPath
from runtime.state import SessionState
from runtime.structured_output import StructuredOutputService
from scripts import seo_pdf_report
from seoctl.composition import build_orchestrator as SEOOrchestrator

ROOT = Path(__file__).resolve().parents[1]


def _asset_fixture(
    tmp_path: Path, knowledge: str = "knowledge/safe.md", *, omit: str = ""
) -> Path:
    root = tmp_path / "assets"
    files = {
        "SYSTEM_SPEC.md": "Fixture system specification.",
        "knowledge/seo-quality-gates.md": "Fixture quality rules.",
        "knowledge/safe.md": "Allowed fixture knowledge.",
        "agents/fixture.md": "Fixture agent specification.",
        "skills/package-registry.json": json.dumps({"packages": {}}),
        "orchestration/capability-registry.json": json.dumps({
            "agents": {"Fixture Agent": {
                "agent_file": "agents/fixture.md", "skills": [], "skill_files": [],
                "knowledge_files": [knowledge], "templates": [], "required_evidence": [],
            }},
            "shared": {},
        }),
    }
    for relative, content in files.items():
        if relative == omit:
            continue
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def test_capability_metadata_cannot_read_outside_asset_root(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLD_CLASS_SEO_ROOT", raising=False)
    outside = tmp_path / "private.md"
    outside.write_text("PRIVATE_FIXTURE_ONLY", encoding="utf-8")
    root = _asset_fixture(tmp_path, "../private.md")
    resolver = CapabilityResolver(root)
    assert resolver.repo_root == root.resolve()

    with pytest.raises((CapabilityResolutionError, UnsafeRepositoryPath)):
        resolver.load_context("Fixture Agent")


@pytest.mark.parametrize("field", ["agent_file", "skill_files", "knowledge_files", "templates"])
def test_bundle_never_certifies_external_capability_paths(tmp_path, monkeypatch, field):
    monkeypatch.delenv("WORLD_CLASS_SEO_ROOT", raising=False)
    outside = tmp_path / "outside.md"
    outside.write_text("PRIVATE_FIXTURE_ONLY", encoding="utf-8")
    root = _asset_fixture(tmp_path)
    resolver = CapabilityResolver(root)
    resolver.registry["Fixture Agent"][field] = (
        str(outside) if field == "agent_file" else [str(outside)]
    )
    with pytest.raises((CapabilityResolutionError, UnsafeRepositoryPath)):
        resolver.bundle("Fixture Agent")


@pytest.mark.parametrize("reader", ["workflow", "quality_gates", "evidence_rules"])
def test_executor_prompt_assets_stay_in_effective_root(tmp_path, monkeypatch, reader):
    monkeypatch.delenv("WORLD_CLASS_SEO_ROOT", raising=False)
    (tmp_path / "outside.md").write_text("PRIVATE_FIXTURE_ONLY", encoding="utf-8")
    root = _asset_fixture(tmp_path)
    executor = AgentExecutor(root, EchoLLMClient())
    workflow = "SYSTEM_SPEC.md"
    if reader == "workflow":
        workflow = "../outside.md"
    else:
        executor.capabilities.shared[reader] = "../outside.md"
    session = SessionState.create("Fixture audit", "Audit", "https://example.com", "service")
    context = executor.capabilities.load_context("Fixture Agent")
    with pytest.raises(UnsafeRepositoryPath):
        executor._messages_for_agent(
            session=session, agent_name="Fixture Agent", workflow_path=workflow,
            tool_results=[], prior_outputs=[], required_handoffs=[], role="lead",
            capability_context=context,
        )


def _directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
            check=True, capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def test_fixed_package_metadata_rejects_resolved_directory_escape(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLD_CLASS_SEO_ROOT", raising=False)
    root = _asset_fixture(tmp_path, omit="skills/package-registry.json")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "package-registry.json").write_text('{"packages": {}}', encoding="utf-8")
    _directory_link(root / "skills", outside)
    with pytest.raises(UnsafeRepositoryPath):
        CapabilityResolver(root)


def test_executor_uses_selected_installed_asset_root(tmp_path, monkeypatch):
    root = _asset_fixture(tmp_path)
    monkeypatch.setenv("WORLD_CLASS_SEO_ROOT", str(root))
    executor = AgentExecutor(tmp_path / "not-an-asset-root", EchoLLMClient())
    assert executor.repo_root == root.resolve()
    assert executor._read("SYSTEM_SPEC.md") == "Fixture system specification."


def test_safe_asset_context_and_optional_missing_file_remain_supported(tmp_path, monkeypatch):
    monkeypatch.delenv("WORLD_CLASS_SEO_ROOT", raising=False)
    root = _asset_fixture(tmp_path)
    context = CapabilityResolver(root).load_context("Fixture Agent")
    assert context["knowledge_context"] == [
        {"path": "knowledge/safe.md", "content": "Allowed fixture knowledge."}
    ]
    executor = AgentExecutor(root, EchoLLMClient())
    assert executor._read("missing-optional.md") == ""


@pytest.mark.parametrize("surface", ["supplemental", "procedure"])
def test_supplemental_readers_recheck_retargeted_asset_directory(tmp_path, monkeypatch, surface):
    monkeypatch.delenv("WORLD_CLASS_SEO_ROOT", raising=False)
    root = _asset_fixture(tmp_path)
    resolver = CapabilityResolver(root)
    resolver.registry["Fixture Agent"]["skills"] = ["fixture-skill"]
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "extra.md").write_text(
        "## Skill: `fixture-skill`\nPRIVATE_FIXTURE_ONLY", encoding="utf-8"
    )
    (outside / "deep-skill-procedures.md").write_text(
        "## fixture-skill\nPRIVATE_FIXTURE_ONLY", encoding="utf-8"
    )
    if surface == "procedure":
        defined = root / "knowledge" / "defined.md"
        defined.write_text("## Skill: `fixture-skill`\nAllowed fixture.", encoding="utf-8")
        resolver.registry["Fixture Agent"]["skill_files"] = ["knowledge/defined.md"]
    old_skills = root / "skills"
    saved_skills = root / "saved-skills"
    assert old_skills.resolve().is_relative_to(tmp_path.resolve())
    assert saved_skills.resolve().is_relative_to(tmp_path.resolve())
    old_skills.rename(saved_skills)
    _directory_link(old_skills, outside)
    with pytest.raises(UnsafeRepositoryPath):
        resolver.load_context("Fixture Agent")


def test_brand_rejects_active_markup_before_renderer_side_effects(tmp_path):
    destination = tmp_path / "new-directory" / "report.pdf"
    calls = []

    def renderer(markup, target):
        calls.append(markup)
        target.write_bytes(b"fixture output")

    with pytest.raises(ValueError, match="brand|color"):
        seo_pdf_report.write_report(
            {"agent": "Fixture", "summary": "Fixture report", "findings": []},
            str(destination), brand="red;</style><script>fixture()</script>",
            pdf_renderer=renderer,
        )
    assert calls == []
    assert not destination.parent.exists()


@pytest.mark.asyncio
async def test_unknown_paid_cost_blocks_before_any_provider_call():
    class PaidClient:
        provider = "fixture-paid"
        model = "fixture-only"
        calls = 0

        async def complete(self, messages):
            self.calls += 1
            return LLMResponse(self.provider, self.model, "{}", {})

    client = PaidClient()
    budget = RunBudget(ExecutionLimits(max_estimated_cost=0, max_correction_attempts=0))
    result = await StructuredOutputService(ROOT).complete_agent_output(
        client, [], agent_name="SEO Technical Agent", request="Fixture audit",
        domain="https://example.com", skills=[], knowledge=[], prior_outputs=[],
        required_handoffs=[], budget=budget,
    )
    assert client.calls == 0
    assert result.status == "blocked"


def test_unknown_cost_without_ceiling_is_not_reported_as_free():
    budget = RunBudget(ExecutionLimits())
    budget.reserve_llm_call()
    assert budget.snapshot()["usage"]["estimated_cost"] is None


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), True])
def test_nonfinite_or_boolean_cost_ceiling_is_rejected(amount):
    with pytest.raises(InvalidExecutionLimits):
        ExecutionLimits(max_estimated_cost=amount)


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), -1, True])
def test_invalid_request_cost_cannot_bypass_reservation(amount):
    with pytest.raises(BudgetExceeded):
        RunBudget(ExecutionLimits()).reserve_llm_call(estimated_cost=amount)


@pytest.mark.asyncio
async def test_verified_request_quote_is_reserved_before_dispatch():
    class QuotedClient:
        provider = "fixture-priced"
        model = "fixture-only"
        calls = 0
        quotes = 0

        def estimate_request_cost(self, messages):
            self.quotes += 1
            return 0.5  # Synthetic whole-call quote, including transport retries.

        async def complete(self, messages):
            self.calls += 1
            return LLMResponse(self.provider, self.model, "{}", {})

    client = QuotedClient()
    result = await StructuredOutputService(ROOT).complete_agent_output(
        client, [], agent_name="SEO Technical Agent", request="Fixture audit",
        domain="https://example.com", skills=[], knowledge=[], prior_outputs=[],
        required_handoffs=[],
        budget=RunBudget(ExecutionLimits(max_estimated_cost=0.2, max_correction_attempts=0)),
    )
    assert client.quotes == 1
    assert client.calls == 0
    assert result.status == "blocked"


class _UnpricedClient:
    provider = "fixture-paid"
    model = "fixture-only"

    def __init__(self):
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        return LLMResponse(self.provider, self.model, "{}", {})

    async def stream(self, messages):
        self.calls += 1
        yield "Synthetic response."


@pytest.mark.asyncio
async def test_single_agent_preserves_supplied_monetary_ceiling():
    client = _UnpricedClient()
    orchestrator = SEOOrchestrator(ROOT, llm_client=client)
    session = orchestrator.start_session("Audit fixture", "Audit", "https://example.com", "unknown")
    result = await orchestrator.execute_async(
        session, execution_mode="single-agent",
        limits=ExecutionLimits(max_estimated_cost=0, max_correction_attempts=0),
    )
    assert client.calls == 0
    assert result["agent_output"]["execution_state"] == "BLOCKED"


def test_stream_cli_preserves_monetary_ceiling(monkeypatch, capsys):
    from seoctl.composition import build_orchestrator

    client = _UnpricedClient()

    def fixture_orchestrator(*args, **kwargs):
        return build_orchestrator(*args, llm_client=client, **kwargs)

    monkeypatch.setattr(legacy_cli, "build_orchestrator", fixture_orchestrator)
    monkeypatch.setattr("sys.argv", [
        "main.py", "Audit fixture", "--execute", "--stream", "--execution-mode",
        "single-agent", "--max-estimated-cost", "0",
    ])
    status = legacy_cli.main()
    assert client.calls == 0
    assert status != 0
    assert "BLOCKED" in capsys.readouterr().out


def test_legacy_export_excludes_request_secret_and_retains_shape(monkeypatch, capsys):
    marker = "SYNTHETIC_PRIVATE_FIXTURE"
    monkeypatch.setattr("sys.argv", [
        "main.py", "Audit fixture password=" + marker, "--execute",
        "--execution-mode", "single-agent", "--llm-provider", "echo",
    ])
    assert legacy_cli.main() == 0
    output = capsys.readouterr().out
    assert marker not in output
    assert json.loads(output)["agent_output"]["execution_state"] == "SYNTHETIC"


def test_raw_stream_refuses_known_sensitive_request(monkeypatch, capsys):
    marker = "SYNTHETIC_PRIVATE_FIXTURE"
    monkeypatch.setattr("sys.argv", [
        "main.py", "Audit fixture password=" + marker, "--execute", "--stream",
        "--execution-mode", "single-agent", "--llm-provider", "echo",
    ])
    assert legacy_cli.main() != 0
    assert marker not in capsys.readouterr().out


@pytest.mark.asyncio
async def test_corrections_require_new_cumulative_cost_reservations():
    class QuotedClient(_UnpricedClient):
        def __init__(self):
            super().__init__()
            self.quotes = []

        def estimate_request_cost(self, messages):
            self.quotes.append(list(messages))
            return 0.5  # Synthetic whole-request upper bound, not a real model price.

    client = QuotedClient()
    budget = RunBudget(ExecutionLimits(max_estimated_cost=0.5, max_correction_attempts=1))
    result = await StructuredOutputService(ROOT).complete_agent_output(
        client, [], agent_name="SEO Technical Agent", request="Fixture audit",
        domain="https://example.com", skills=[], knowledge=[], prior_outputs=[],
        required_handoffs=[], budget=budget,
    )
    assert client.calls == 1
    assert len(client.quotes) == 2
    assert len(client.quotes[1]) > len(client.quotes[0])
    assert result.status == "blocked"
    assert budget.snapshot()["usage"]["estimated_cost"] == 0.5


@pytest.mark.asyncio
async def test_direct_single_agent_projection_does_not_mutate_request():
    marker = "SYNTHETIC_PRIVATE_FIXTURE"
    orchestrator = SEOOrchestrator(ROOT, llm_client=EchoLLMClient())
    session = orchestrator.start_session("Audit password=" + marker, "Audit")
    result = await orchestrator.executor.execute(session, orchestrator.route(session))
    assert marker not in json.dumps(result)
    assert session.request.endswith(marker)
    assert result["agent_output"]["execution_state"] == "SYNTHETIC"


def test_non_sensitive_echo_stream_and_planning_remain_available(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["main.py", "Audit fixture", "--max-estimated-cost", "nan"])
    assert legacy_cli.main() == 0  # Execution-only settings do not change planning mode.
    assert json.loads(capsys.readouterr().out)["lead_agent"]
    monkeypatch.setattr("sys.argv", [
        "main.py", "Audit fixture", "--execute", "--stream", "--execution-mode",
        "single-agent", "--llm-provider", "echo", "--max-estimated-cost", "0",
    ])
    assert legacy_cli.main() == 0
    assert "Echo execution complete" in capsys.readouterr().out
