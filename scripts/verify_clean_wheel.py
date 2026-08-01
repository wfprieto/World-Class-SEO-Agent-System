"""Cross-platform smoke test for a wheel in a newly created virtual environment."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def verify(wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="seo-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        _run([str(python), "-m", "pip", "install", str(wheel.resolve())])
        _run([str(python), "-m", "seoctl", "--registry-check"])
        _run([str(python), "-m", "seoctl", "integrations", "list"])
        _run([str(python), "-m", "seoctl", "knowledge", "validate"])
        input_path = root / "input.txt"
        output_path = root / "output.txt"
        input_path.write_text("Formulaic filler text.\n", encoding="utf-8")
        _run([
            str(python), "-m", "seoctl", "content", "humanize",
            "--input", str(input_path), "--output", str(output_path),
        ])
        prefix = subprocess.check_output(
            [str(python), "-c", "import sys; print(sys.prefix)"], text=True
        ).strip()
        fixture = Path(prefix) / "share/world-class-seo/examples/product-proof/site-fixture.json"
        audit_output = root / "audit"
        _run([
            str(python), "-m", "seoctl", "audit", "technical",
            "--url", "https://example.com/", "--fixture", str(fixture),
            "--output", str(audit_output), "--max-urls", "20",
        ])
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
