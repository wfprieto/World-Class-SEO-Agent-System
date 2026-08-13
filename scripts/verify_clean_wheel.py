"""Cross-platform smoke test for a wheel in a newly created virtual environment."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _output(command: list[str], *, cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            "command failed in clean wheel environment: "
            f"{command}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed.stdout


def verify(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="seo-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        wheel_copy = root / wheel.name
        shutil.copy2(wheel.resolve(), wheel_copy)
        _run([str(python), "-m", "pip", "install", str(wheel_copy)], cwd=root)
        _run([str(python), "-m", "seoctl", "--help"], cwd=root)
        _run([str(python), "-m", "seoctl", "--registry-check"], cwd=root)
        _run([str(python), "-m", "seoctl", "integrations", "list"], cwd=root)
        _run([str(python), "-m", "seoctl", "knowledge", "validate"], cwd=root)
        doctor = json.loads(
            _output(
                [str(python), "-m", "seoctl", "system", "doctor", "--as-of", "2026-08-02"],
                cwd=root,
            )
        )
        doctor_data = doctor["data"]
        if doctor["status"] != "ok" or doctor_data["status"] != "PASS":
            raise RuntimeError(f"installed system doctor failed: {doctor}")
        if doctor_data["network_performed"] or doctor_data["provider_authentication_performed"]:
            raise RuntimeError("installed system doctor performed forbidden network or provider auth")
        input_path = root / "input.txt"
        output_path = root / "output.txt"
        input_path.write_text("Formulaic filler text.\n", encoding="utf-8")
        _run(
            [
                str(python), "-m", "seoctl", "content", "humanize",
                "--input", str(input_path), "--output", str(output_path),
            ],
            cwd=root,
        )
        prefix = _output(
            [str(python), "-c", "import sys; print(sys.prefix)"], cwd=root
        ).strip()
        support_root = Path(prefix) / "share/world-class-seo"
        for relative in (
            "SYSTEM_SPEC.md",
            "governance/architecture-contract.json",
            "requirements-dev.in",
            "requirements-dev.txt",
            "runtime/assets.py",
            "seoctl/command-registry.json",
        ):
            if not (support_root / relative).is_file():
                raise RuntimeError(f"packaged resource missing: {relative}")
        fixture = Path(prefix) / "share/world-class-seo/examples/product-proof/site-fixture.json"
        audit_output = root / "audit"
        _run(
            [
                str(python), "-m", "seoctl", "audit", "technical",
                "--url", "https://example.com/", "--fixture", str(fixture),
                "--output", str(audit_output), "--max-urls", "20",
            ],
            cwd=root,
        )
        required = [output_path, audit_output / "run-manifest.json", audit_output / "executive-summary.md"]
        missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
        if missing:
            raise RuntimeError(f"clean-wheel smoke outputs missing or empty: {missing}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args(argv)
    verify(args.wheel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
