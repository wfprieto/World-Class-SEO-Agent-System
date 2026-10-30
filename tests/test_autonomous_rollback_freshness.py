from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from scripts.validate_historical_rollback_claims import APPROVED_BOUNDARIES

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/validate_historical_rollback_claims.py"
CURRENT = "e0743688fb3bfdfc702348a5debd9aa397939478"
OLD_NAME = "Validate restored baseline repository at historical review boundary"
NEW_NAME = "Validate restored baseline repository with scoped freshness"


def _command() -> str:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/autonomous-seo-certification.yml").read_text()
    )
    steps = workflow["jobs"]["autonomous-seo-p0-rollback-certification"]["steps"]
    return next(step["run"] for step in steps if step.get("name") in {OLD_NAME, NEW_NAME})


def _fixture(tmp_path: Path, review_by: date, *, broken: bool = False) -> tuple[Path, bytes]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    runner = tmp_path / "runner temp"
    runner.mkdir()
    shutil.copyfile(HELPER, runner / HELPER.name)
    content = f'''from datetime import date
import json, os
from pathlib import Path

def validate(root, *, as_of=None):
    effective = as_of or date.today()
    print(json.dumps({{"effective_date": effective.isoformat(),
                      "historical_override": bool(os.environ.get("WCSEO_BASELINE_CLAIM_VALIDATOR"))}}))
    if {broken!r}:
        raise RuntimeError("fixture-validator-failed")
    return ["fixture-review-overdue"] if effective > date.fromisoformat({review_by.isoformat()!r}) else []

if __name__ == "__main__":
    failures = validate(Path.cwd())
    print(json.dumps({{"failures": failures}}))
    raise SystemExit(1 if failures else 0)
'''
    original = content.encode()
    (scripts / "validate_seo_claims.py").write_bytes(original)
    python = sys.executable.replace("'", "''")
    (scripts / "validate-repository.ps1").write_text(
        "Set-Content -LiteralPath invocation.txt -Value 'invoked'\n"
        f"& '{python}' -B scripts/validate_seo_claims.py\nexit $LASTEXITCODE\n"
    )
    return runner, original


def _step(tmp_path: Path, runner: Path, baseline: str) -> subprocess.CompletedProcess[str]:
    shell = shutil.which("pwsh")
    assert shell, "the rollback workflow requires PowerShell for its actual-step regression"
    command = _command().replace("${{ steps.rollback.outputs.baseline }}", baseline)
    command = command.replace("${{ steps.trusted.outputs.python }}", sys.executable)
    assert "${{" not in command
    wrapper = (
        "$ErrorActionPreference='Stop'; $stepFailed=$false\ntry {\n" + command
        + "\n} catch { Write-Output $_; $stepFailed=$true }\n"
        + "Write-Output ('CLEANUP_JSON='+(@{validator=$env:WCSEO_BASELINE_CLAIM_VALIDATOR;"
        + "expected=$env:WCSEO_ROLLBACK_EXPECTED_SHA}|ConvertTo-Json -Compress))\n"
        + "if($stepFailed){exit 1}\nexit 0"
    )
    env = os.environ | {"RUNNER_TEMP": str(runner), "PYTHONDONTWRITEBYTECODE": "1"}
    for name in ("WCSEO_BASELINE_CLAIM_VALIDATOR", "WCSEO_ROLLBACK_EXPECTED_SHA"):
        env.pop(name, None)
    return subprocess.run(
        [shell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", wrapper],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )


def _restored(tmp_path: Path, original: bytes, result: subprocess.CompletedProcess[str]) -> None:
    assert (tmp_path / "scripts/validate_seo_claims.py").read_bytes() == original
    cleanup = next(line.removeprefix("CLEANUP_JSON=") for line in result.stdout.splitlines()
                   if line.startswith("CLEANUP_JSON="))
    assert not any(json.loads(cleanup).values())


@pytest.mark.parametrize("baseline", [CURRENT, "0" * 40, *APPROVED_BOUNDARIES])
def test_selector_is_scoped_and_does_not_run_a_validator(baseline: str) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-E", "-S", str(HELPER), "--review-mode", baseline],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
    expected = "APPROVED_HISTORICAL" if baseline in APPROVED_BOUNDARIES else "CURRENT_FRESHNESS"
    assert result.stdout.strip() == expected


@pytest.mark.parametrize("baseline", ["", "main", CURRENT.upper(), "a" * 39, "a" * 41, "g" * 40])
def test_selector_rejects_malformed_baselines(baseline: str) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-E", "-S", str(HELPER), "--review-mode", baseline],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
    assert result.stdout.strip() not in {"APPROVED_HISTORICAL", "CURRENT_FRESHNESS"}


def test_current_baseline_uses_real_freshness_without_a_historical_override(tmp_path: Path) -> None:
    runner, original = _fixture(tmp_path, date.today() + timedelta(days=1))
    result = _step(tmp_path, runner, CURRENT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'"effective_date": "{date.today().isoformat()}"' in result.stdout
    assert '"historical_override": false' in result.stdout
    assert "historical_rollback_only" not in result.stdout
    _restored(tmp_path, original, result)


def test_current_stale_baseline_cannot_be_backdated(tmp_path: Path) -> None:
    runner, original = _fixture(tmp_path, date.today() - timedelta(days=1))
    result = _step(tmp_path, runner, CURRENT)
    assert result.returncode != 0
    assert "fixture-review-overdue" in result.stdout
    assert '"historical_override": false' in result.stdout
    _restored(tmp_path, original, result)


@pytest.mark.parametrize("baseline,boundary", APPROVED_BOUNDARIES.items())
def test_approved_historical_baselines_keep_their_exact_boundary(
    tmp_path: Path, baseline: str, boundary: date,
) -> None:
    runner, original = _fixture(tmp_path, boundary)
    result = _step(tmp_path, runner, baseline)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f'"effective_date": "{boundary.isoformat()}"' in result.stdout
    assert '"certification_scope": "HISTORICAL_ROLLBACK_ONLY"' in result.stdout
    assert '"current_certification": false' in result.stdout
    _restored(tmp_path, original, result)


@pytest.mark.parametrize("historical", [False, True])
def test_failure_restores_source_and_clears_overrides(tmp_path: Path, historical: bool) -> None:
    runner, original = _fixture(tmp_path, date.today(), broken=True)
    baseline = next(iter(APPROVED_BOUNDARIES)) if historical else CURRENT
    result = _step(tmp_path, runner, baseline)
    assert result.returncode != 0
    assert "fixture-validator-failed" in result.stdout + result.stderr
    _restored(tmp_path, original, result)


def test_invalid_baseline_stops_before_replacing_or_running_source(tmp_path: Path) -> None:
    runner, original = _fixture(tmp_path, date.today())
    result = _step(tmp_path, runner, "not-a-certified-sha")
    assert result.returncode != 0
    assert not (tmp_path / "invocation.txt").exists()
    _restored(tmp_path, original, result)


@pytest.mark.parametrize("output,code", [
    ("", 0), ("UNKNOWN\n", 0),
    ("CURRENT_FRESHNESS\nAPPROVED_HISTORICAL\n", 0),
    ("CURRENT_FRESHNESS\nCURRENT_FRESHNESS\n", 0), ("CURRENT_FRESHNESS\n", 9),
    ("current_freshness\n", 0), ("approved_historical\n", 0),
    ("CURRENT_FRESHNESS \n", 0), (" CURRENT_FRESHNESS\n", 0),
])
def test_selector_failure_or_ambiguous_output_cannot_run_validation(
    tmp_path: Path, output: str, code: int,
) -> None:
    runner, original = _fixture(tmp_path, date.today())
    (runner / HELPER.name).write_text(
        f"import sys\nsys.stdout.write({output!r})\nraise SystemExit({code})\n"
    )
    result = _step(tmp_path, runner, CURRENT)
    assert result.returncode != 0
    assert not (tmp_path / "invocation.txt").exists()
    _restored(tmp_path, original, result)


def test_strict_historical_wrapper_still_rejects_an_unapproved_sha(tmp_path: Path) -> None:
    runner, original = _fixture(tmp_path, date.today())
    env = os.environ | {"WCSEO_ROLLBACK_EXPECTED_SHA": CURRENT,
                        "WCSEO_BASELINE_CLAIM_VALIDATOR": str(tmp_path / "scripts/validate_seo_claims.py")}
    result = subprocess.run(
        [sys.executable, "-B", str(runner / HELPER.name)], env=env,
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
    assert "approved rollback SHA and restored baseline validator are required" in result.stderr
    assert "effective_date" not in result.stdout
    assert (tmp_path / "scripts/validate_seo_claims.py").read_bytes() == original
