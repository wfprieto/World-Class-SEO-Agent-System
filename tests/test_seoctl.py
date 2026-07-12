from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from seoctl.cli import EXIT_BLOCKED, EXIT_INPUT, EXIT_OK, run
from seoctl.registry import command_specs, load_registry, validate_registry

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, payload) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_command_registry_is_complete_unique_and_covers_all_agents():
    registry = load_registry()
    assert validate_registry(registry) == []
    assert len(command_specs(registry)) == 11
    assert len(registry["agents"]) == 25
    assert {row["execution_class"] for row in registry["agents"].values()} == {
        "executable",
        "advisory",
        "governance",
    }


def test_registry_check_is_machine_readable_and_successful():
    payload, code = run(["--registry-check"])
    assert code == EXIT_OK
    assert payload["status"] == "ok"
    assert payload["data"]["commands"] == 11
    assert payload["data"]["agents"] == 25


def test_direct_module_execution_works_from_clean_process():
    completed = subprocess.run(
        [sys.executable, "-m", "seoctl", "--registry-check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "ok"


def test_profile_resolution_command_uses_canonical_resolver():
    payload, code = run([
        "profile", "resolve",
        "--signal", "cart",
        "--signal", "checkout",
        "--signal", "visible_price",
        "--signal", "local_business_schema",
        "--signal", "verified_nap",
    ])
    assert code == EXIT_OK
    assert payload["data"]["route"] == "HYBRID"
    assert set(payload["data"]["profiles"]) == {"ecommerce", "local-service"}


def test_content_relevance_and_cluster_commands_reuse_existing_logic(tmp_path: Path):
    site = _write(tmp_path / "site.json", {
        "purpose": "SEO software and consulting",
        "audience": "SEO teams",
        "offerings": ["technical SEO audits"],
        "markets": ["US"],
        "expertise": ["technical SEO"],
    })
    relevance, code = run([
        "content", "relevance", "--site", site,
        "--topic", "technical SEO audit software", "--market", "US",
    ])
    assert code == EXIT_OK
    assert relevance["data"]["verdict"] == "RELEVANT"

    serps = _write(tmp_path / "serps.json", {
        "technical seo audit": ["https://a.test/1", "https://b.test/2", "https://c.test/3"],
        "seo audit software": ["https://a.test/1", "https://b.test/2", "https://c.test/3"],
    })
    clustered, code = run(["cluster", "serp", "--serps", serps])
    assert code == EXIT_OK
    assert clustered["data"]["cluster_count"] == 1


def test_consent_command_preserves_blocked_state(tmp_path: Path):
    config = _write(tmp_path / "consent.json", {
        "live_test_requested": True,
        "live_test_authorized": False,
    })
    payload, code = run(["privacy", "consent", "--config", config])
    assert code == EXIT_BLOCKED
    assert payload["status"] == "blocked"
    assert payload["data"]["status"] == "BLOCKED"


def test_benchmark_commands_execute_real_validators():
    compared, code = run(["benchmark", "compare"])
    assert code == EXIT_OK
    assert compared["data"]["status"] == "PASS"
    traced, code = run(["benchmark", "tracer"])
    assert code == EXIT_OK
    assert traced["data"]["verdict"] == "GO"


def test_system_route_and_echo_run_are_real_runtime_entrypoints():
    routed, code = run([
        "system", "route", "Build an SEO content brief",
        "--domain", "https://example.com",
        "--business-type", "saas",
    ])
    assert code == EXIT_OK
    assert routed["data"]["route"]["lead_agent"] == "SEO Copywriter/Content Agent"

    executed, code = run([
        "system", "run", "Build an SEO content brief",
        "--domain", "https://example.com",
        "--business-type", "saas",
        "--max-llm-calls", "12",
    ])
    assert code == EXIT_OK
    assert executed["status"] == "partial"
    assert executed["data"]["execution_mode"] == "multi-agent"


def test_report_render_writes_truthful_artifact(tmp_path: Path):
    source = _write(tmp_path / "output.json", {
        "agent": "SEO Technical Agent",
        "summary": "Fixture report.",
        "findings": [],
        "recommended_actions": [],
        "evidence": [],
        "confidence": "Low",
        "impact": "Fixture only.",
        "effort": "Low",
        "risks": [],
        "owner": "SEO Technical Agent",
        "dependencies": [],
        "acceptance_criteria": [],
        "verification": [],
        "follow_up": "None",
    })
    payload, code = run([
        "report", "render", "--input", source,
        "--out", str(tmp_path / "report.pdf"),
    ])
    assert code == EXIT_OK
    assert Path(payload["data"]["path"]).is_file()
    assert payload["data"]["format"] in {"pdf", "html"}


def test_invalid_input_returns_stable_json_exit_code(tmp_path: Path):
    payload, code = run([
        "content", "relevance", "--site", str(tmp_path / "missing.json"),
        "--topic", "seo",
    ])
    assert code == EXIT_INPUT
    assert payload["status"] == "input_error"
    assert payload["error"]["type"] == "FileNotFoundError"


def test_pyproject_exposes_console_script():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'seoctl = "seoctl.cli:main"' in text
