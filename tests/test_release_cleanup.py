from __future__ import annotations

from pathlib import Path

from runtime.orchestrator import SEOOrchestrator
from runtime.schema_registry import SchemaRegistry


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_output_feature_flag_is_absent_before_release():
    forbidden = "SEO_RUNTIME_" + "LEGACY_OUTPUT"
    roots = [ROOT / "runtime", ROOT / "scripts", ROOT / "docs", ROOT / ".github"]
    occurrences = []
    for directory in roots:
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".yml", ".yaml", ".json"}:
                if forbidden in path.read_text(encoding="utf-8", errors="ignore"):
                    occurrences.append(path.relative_to(ROOT).as_posix())
    assert occurrences == []


def test_single_agent_debug_path_uses_canonical_structured_output_contract():
    orchestrator = SEOOrchestrator(ROOT)
    session = orchestrator.start_session(
        request="Run a technical audit",
        mode="Audit",
        domain="https://example.com",
        business_type="saas",
    )
    payload = orchestrator.execute(
        session,
        orchestrator.route(session),
        execution_mode="single-agent",
    )
    assert payload["execution_mode"] == "single-agent-debug"
    SchemaRegistry(ROOT).validate("agent-output", payload["agent_output"])
    assert payload["agent_output"]["execution_state"] == "SYNTHETIC"
