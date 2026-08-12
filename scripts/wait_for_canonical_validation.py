"""Wait for and authenticate the exact-head canonical validation workflow."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_ROOT = "https://api.github.com"
CANONICAL_NAME = "Validate repository"
CANONICAL_PATH = ".github/workflows/validate.yml"


def _api_json(path: str, token: str) -> Any:
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "wcseo-canonical-prerequisite",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GitHub canonical validation lookup failed: {exc}") from exc


def select_canonical_run(payload: dict[str, Any], head_sha: str) -> dict[str, Any] | None:
    candidates = [
        run
        for run in payload.get("workflow_runs", [])
        if run.get("name") == CANONICAL_NAME
        and run.get("path") == CANONICAL_PATH
        and run.get("head_sha") == head_sha
        and run.get("event") == "pull_request"
    ]
    return max(candidates, key=lambda run: int(run.get("id", 0)), default=None)


def _receipt(repository: str, head_sha: str, run: dict[str, Any]) -> dict[str, Any]:
    return {
        "repository_full_name": repository,
        "candidate_commit": head_sha,
        "canonical_ci_run_id": int(run["id"]),
        "workflow_name": str(run["name"]),
        "workflow_path": str(run["path"]),
        "event": str(run["event"]),
        "status": str(run["status"]),
        "conclusion": str(run["conclusion"]),
        "result": "PASS",
    }


def wait_for_canonical(
    repository: str,
    head_sha: str,
    token: str,
    timeout_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    query = urllib.parse.urlencode({"head_sha": head_sha, "per_page": 20})
    path = f"/repos/{repository}/actions/runs?{query}"
    while time.monotonic() < deadline:
        payload = _api_json(path, token)
        if not isinstance(payload, dict):
            raise RuntimeError("GitHub canonical validation response is not an object")
        run = select_canonical_run(payload, head_sha)
        if run is None:
            time.sleep(poll_seconds)
            continue
        if run.get("status") != "completed":
            time.sleep(poll_seconds)
            continue
        if run.get("conclusion") != "success":
            raise RuntimeError(
                f"canonical Validate repository run {run.get('id')} completed with {run.get('conclusion')}"
            )
        return _receipt(repository, head_sha, run)
    raise RuntimeError("timed out waiting for exact-head canonical validation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--poll-seconds", type=int, default=10)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print(json.dumps({"status": "FAIL", "errors": ["GITHUB_TOKEN is required"]}))
        return 1
    if len(args.head_sha) != 40:
        print(json.dumps({"status": "FAIL", "errors": ["head SHA must be 40 characters"]}))
        return 1
    try:
        receipt = wait_for_canonical(
            args.repository,
            args.head_sha,
            token,
            args.timeout_seconds,
            args.poll_seconds,
        )
    except RuntimeError as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}))
        return 1
    Path(args.receipt).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "receipt": receipt}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
