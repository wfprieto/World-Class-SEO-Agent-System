"""Private working evidence and generated Python metadata stay out of source commits."""

import shutil
import subprocess
from pathlib import Path


def test_repo_ignores_generated_and_private_run_artifacts(tmp_path):
    source = Path(__file__).resolve().parents[1]
    shutil.copyfile(source / ".gitignore", tmp_path / ".gitignore")
    empty = tmp_path / "empty-excludes"
    empty.write_text("", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    paths = [
        ".coverage",
        ".coverage.worker.123",
        "world_class_seo_agent_system.egg-info/SOURCES.txt",
        ".venv/Scripts/python.exe",
        ".wcbs/runs/example/findings.json",
    ]
    result = subprocess.run(
        ["git", "-c", f"core.excludesFile={empty}", "check-ignore", "--no-index", "--stdin", "-z"],
        cwd=tmp_path,
        input="\0".join(paths) + "\0",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.split("\0")[:-1] == paths
    canonical = subprocess.run(
        [
            "git",
            "-c",
            f"core.excludesFile={empty}",
            "check-ignore",
            "--no-index",
            ".wcbs/project-contract.json",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert canonical.returncode == 1
