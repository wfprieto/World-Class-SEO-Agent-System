from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def test_readme_surfaces_core_public_proof_paths() -> None:
    readme = _read("README.md")
    required_links = [
        "QUICKSTART.md",
        "examples/golden-demo/",
        "examples/proof-pack/",
        "examples/proof-pack/proof-pack-manifest.json",
        "docs/AGENT-SYNERGY-MAP.md",
        "docs/AUTONOMY-SAFETY-MODEL.md",
        "orchestration/autonomy-safety-policy.json",
        "runtime/autonomy.py",
    ]
    for link in required_links:
        assert link in readme


def test_readme_uses_approved_public_claim_boundaries() -> None:
    readme = _read("README.md")
    lower = readme.lower()
    assert "does not prove live rankings" in lower
    assert "fixture demo proves offline routing" in lower
    assert "public repository defaults to audit-only" in lower
    assert "full autopilot is reserved for private controlled installations" in lower


def test_readme_avoids_blocked_product_claim_wording() -> None:
    readme = _read("README.md")
    inventory = json.loads(_read("knowledge/product-claim-inventory.json"))
    lower = readme.lower()
    for claim in inventory["claims"]:
        if claim["status"] == "BLOCKED":
            assert claim["prohibited_wording"].lower() not in lower


def test_readme_validation_commands_match_current_gates() -> None:
    readme = _read("README.md")
    commands = [
        "powershell -ExecutionPolicy Bypass -File scripts\\validate-repository.ps1",
        "python -m pytest -q --basetemp .pytest_tmp",
        "python -m ruff check . --select E9,F63,F7,F82 --no-cache",
        "python -m mypy runtime seoctl integrations adapters scripts",
        "python scripts\\scan_secrets.py",
    ]
    for command in commands:
        assert command in readme
