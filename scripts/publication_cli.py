"""Trusted publication entry point; local labels can never grant authority."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts import publication_policy as policy
from scripts.publication_authorize import authorize_candidate, execution_authorities
from scripts.publication_context import workflow_context
from scripts.publication_subject import JsonObject, integer_value
from scripts.publication_transport import GitHubCLI

ROOT = Path(__file__).resolve().parents[1]


def _positive(value: str) -> int:
    try:
        return integer_value(int(value), "selection")
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Local deny-all/configuration status; never grants authority")
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--ci-run-id", type=_positive, required=True)
    prepare.add_argument("--out", type=Path, required=True)
    handoff = commands.add_parser("verify-build")
    handoff.add_argument("--artifact-id", type=_positive, required=True)
    handoff.add_argument("--archive-sha256", required=True)
    handoff.add_argument("--out", type=Path, required=True)
    for name in ("authorize", "publish", "observe"):
        command = commands.add_parser(name)
        for flag in ("prepare-run-id", "artifact-id", "evidence-pr", "owner-comment-id"):
            command.add_argument("--" + flag, type=_positive, required=True)
        if name == "observe":
            command.add_argument("--out", type=Path, required=True)
    completion = commands.add_parser("verify-completion")
    completion.add_argument("--publication-run-id", type=_positive, required=True)
    completion.add_argument("--artifact-id", type=_positive, required=True)
    return parser


def _selection(args: argparse.Namespace) -> dict[str, int]:
    return {key: integer_value(getattr(args, key), key)
            for key in ("prepare_run_id", "artifact_id", "evidence_pr", "owner_comment_id")}


def _status() -> JsonObject:
    authorities = execution_authorities(ROOT)
    return {"state": "BLOCKED", "publication_allowed": False, "evidence_state": "Not yet verified",
            "missing_execution_authorities": sorted(gate for gate, entries in authorities.items() if not entries),
            "required_final_gates": sorted(policy.REQUIRED_GATES),
            "reason": "Configuration alone cannot certify publication; authenticate detached completion evidence."}


def _run(args: argparse.Namespace) -> JsonObject:
    if args.command == "status":
        return _status()
    api = GitHubCLI(ROOT)
    now = datetime.now(UTC)
    if args.command in {"prepare", "verify-build"}:
        from scripts.publication_prepare import prepare_candidate, verify_build

        if args.command == "prepare":
            return prepare_candidate(ROOT, api, ci_run_id=args.ci_run_id, output=args.out, now=now)
        return verify_build(ROOT, api, artifact_id=args.artifact_id, archive_sha256=args.archive_sha256,
                            output=args.out, now=now)
    if args.command == "verify-completion":
        from scripts.publication_completion import verify_completion

        return verify_completion(ROOT, api, publication_run_id=args.publication_run_id,
                                 artifact_id=args.artifact_id, now=now)
    selection = _selection(args)
    if args.command == "authorize":
        workflow_context(ROOT, api, policy.PUBLICATION_WORKFLOW, "authorize")
        candidate = authorize_candidate(ROOT, api, **selection, now=now)
        return {"state": "AUTHORIZED_NOT_FINAL", "binding": candidate.binding(), "publication_allowed": False}
    if args.command == "publish":
        from scripts.publication_publish import publish_candidate

        return publish_candidate(ROOT, api, selection=selection)
    from scripts.publication_completion import observe_completion

    return observe_completion(ROOT, api, selection=selection, output=args.out, now=now)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = _run(args)
    except (ValueError, OSError, KeyError, TypeError, UnicodeError) as exc:
        result = {"state": "BLOCKED", "publication_allowed": False, "reason": str(exc)}
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 1 if result["state"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
