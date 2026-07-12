"""Flagship technical audit and evidence-governed SEO knowledge commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from integrations.product_proof.service import ProductProofTechnicalAudit
from runtime.assets import resolve_asset_root
from scripts.validate_product_claims import validate as validate_product_claims
from scripts.validate_seo_claims import validate as validate_claims
from seoctl.cli import EXIT_FAILED, EXIT_INPUT, EXIT_OK, EXIT_UNAVAILABLE, envelope

ROOT = resolve_asset_root(Path(__file__).resolve().parents[1])


def _service() -> ProductProofTechnicalAudit:
    return ProductProofTechnicalAudit()


def _result(command: str, result):  # type: ignore[no-untyped-def]
    code = EXIT_OK
    if result.status in {"not_configured", "unavailable"}:
        code = EXIT_UNAVAILABLE
    elif result.status in {"failed", "invalid", "invalid_response"}:
        code = EXIT_FAILED
    return envelope(command, result.status, result.data, warnings=result.warnings), code


def _technical(args: argparse.Namespace):
    return _result(
        "audit.technical",
        _service().run(
            url=args.url,
            output_dir=args.output,
            fixture_path=args.fixture,
            max_urls=args.max_urls,
            max_depth=args.max_depth,
            max_asset_hosts=args.max_asset_hosts,
        ),
    )


def _claims(args: argparse.Namespace):
    registry = json.loads(
        (ROOT / "knowledge" / "seo-claim-registry.json").read_text(encoding="utf-8-sig")
    )
    rows = registry["claims"]
    if args.evidence_class:
        rows = [row for row in rows if row["evidence_class"] == args.evidence_class]
    if args.applies_to:
        rows = [row for row in rows if args.applies_to in row.get("applies_to", [])]
    return envelope(
        "knowledge.claims",
        "ok",
        {
            "count": len(rows),
            "claims": rows,
            "source_of_truth": registry["source_of_truth"],
            "note": "Evidence labels are part of the claim and must not be promoted by downstream agents.",
        },
    ), EXIT_OK


def _product_claims(args: argparse.Namespace):
    inventory = json.loads(
        (ROOT / "knowledge" / "product-claim-inventory.json").read_text(encoding="utf-8-sig")
    )
    rows = inventory["claims"]
    if args.status:
        rows = [row for row in rows if row["status"] == args.status]
    return envelope(
        "knowledge.product-claims",
        "ok",
        {"count": len(rows), "claims": rows, "note": "Blocked claims must not be promoted by README, release notes, agents, or reports."},
    ), EXIT_OK


def _knowledge_validate(args: argparse.Namespace):
    failures = [*validate_claims(ROOT), *validate_product_claims(ROOT)]
    status = "ok" if not failures else "failed"
    code = EXIT_OK if not failures else EXIT_FAILED
    return envelope(
        "knowledge.validate",
        status,
        {
            "state": "AVAILABLE" if not failures else "INVALID",
            "failure_count": len(failures),
            "failures": failures,
        },
    ), code


HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "audit_technical": _technical,
    "knowledge_claims": _claims,
    "knowledge_product_claims": _product_claims,
    "knowledge_validate": _knowledge_validate,
}


def build_parser(family: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"seoctl {family}")
    sub = parser.add_subparsers(dest="action")
    if family == "audit":
        technical = sub.add_parser(
            "technical",
            help="Run the bounded evidence-governed flagship technical audit",
        )
        technical.add_argument("--url", required=True)
        technical.add_argument("--output", required=True)
        technical.add_argument("--fixture")
        technical.add_argument("--max-urls", type=int, default=500)
        technical.add_argument("--max-depth", type=int, default=6)
        technical.add_argument("--max-asset-hosts", type=int, default=10)
        technical.set_defaults(handler="audit_technical")
    elif family == "knowledge":
        claims = sub.add_parser("claims", help="List approved SEO claims and evidence states")
        claims.add_argument(
            "--evidence-class",
            choices=[
                "PRIMARY_SOURCE",
                "CONTROLLED_EXPERIMENT",
                "LARGE_SCALE_OBSERVATIONAL",
                "PRACTITIONER_CONSENSUS",
                "EXPERT_HYPOTHESIS",
                "ANALYSIS",
                "UNVERIFIED",
                "DISPUTED",
                "STALE",
                "FALSE",
            ],
        )
        claims.add_argument("--applies-to")
        claims.set_defaults(handler="knowledge_claims")
        product_claims = sub.add_parser("product-claims", help="List approved and blocked public product claims")
        product_claims.add_argument("--status", choices=["APPROVED", "APPROVED_WITH_QUALIFIER", "BLOCKED"])
        product_claims.set_defaults(handler="knowledge_product_claims")
        check = sub.add_parser("validate", help="Validate claims, precedence and stale-advice controls")
        check.set_defaults(handler="knowledge_validate")
    else:
        raise ValueError("family must be audit or knowledge")
    return parser


def run(argv: list[str] | None = None):
    arguments = list(argv or [])
    if not arguments or arguments[0] not in {"audit", "knowledge"}:
        return envelope(
            "audit.unknown",
            "input_error",
            error={"type": "MissingFamily", "message": "Choose audit or knowledge."},
        ), EXIT_INPUT
    family = arguments.pop(0)
    parser = build_parser(family)
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        if exc.code == 0:
            raise
        return envelope(
            f"{family}.unknown",
            "input_error",
            error={"type": "ArgumentError", "message": "Invalid command arguments."},
        ), EXIT_INPUT
    handler = getattr(args, "handler", None)
    if not handler:
        return envelope(
            f"{family}.unknown",
            "input_error",
            error={"type": "MissingCommand", "message": f"Choose a {family} command."},
        ), EXIT_INPUT
    try:
        return HANDLERS[handler](args)
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return envelope(
            f"{family}.{args.action}",
            "input_error",
            error={"type": type(exc).__name__, "message": str(exc)},
        ), EXIT_INPUT
    except Exception as exc:  # noqa: BLE001
        return envelope(
            f"{family}.{args.action}",
            "failed",
            error={"type": type(exc).__name__, "state": "FAILED", "message": str(exc)[:500]},
        ), EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    payload, code = run(argv)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code
