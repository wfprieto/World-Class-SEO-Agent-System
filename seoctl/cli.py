"""Unified JSON-first command-line interface for SEO system capabilities."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.tracer.run_tracer import evaluate as evaluate_tracer
from runtime.business_profile_resolver import resolve_business_profile
from runtime.execution_limits import ExecutionLimits
from runtime.llm import build_llm_client
from runtime.orchestrator import SEOOrchestrator
from scripts.content_brief_evidence import assess_relevance, assess_serp, brief_decision
from scripts.inventory_comparator import validate_all as validate_comparison
from scripts.serp_cluster import cluster as cluster_serps
from scripts.seo_pdf_report import write_report
from scripts.consent_mode_diagnostic import diagnose as diagnose_consent
from seoctl.registry import load_registry, validate_registry

EXIT_OK = 0
EXIT_INPUT = 2
EXIT_UNAVAILABLE = 3
EXIT_BLOCKED = 4
EXIT_FAILED = 5


def _json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def envelope(command: str, status: str, data: Any = None, *, warnings: list[str] | None = None,
             error: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "command": command,
        "status": status,
        "data": _plain(data),
        "warnings": warnings or [],
        "error": error,
    }


def _system_route(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    orchestrator = SEOOrchestrator(ROOT)
    session = orchestrator.start_session(
        request=args.request,
        mode=args.mode,
        domain=args.domain,
        business_type=args.business_type,
        markets=args.market,
        goals=args.goal,
        profile_signals=args.profile_signal,
    )
    route = orchestrator.route(session)
    return envelope("system.route", "ok", {
        "route": route.to_dict(),
        "business_profile_resolution": session.business_profile_resolution,
        "open_risks": session.open_risks,
    }), EXIT_OK


def _system_run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    client = build_llm_client(args.llm_provider, args.model or None)
    orchestrator = SEOOrchestrator(ROOT, llm_client=client)
    session = orchestrator.start_session(
        request=args.request,
        mode=args.mode,
        domain=args.domain,
        business_type=args.business_type,
        markets=args.market,
        goals=args.goal,
        profile_signals=args.profile_signal,
    )
    route = orchestrator.route(session)
    result = orchestrator.execute(
        session,
        route,
        execution_mode=args.execution_mode,
        limits=ExecutionLimits(
            max_nodes=args.max_nodes,
            max_llm_calls=args.max_llm_calls,
            max_parallel_agents=args.max_parallel_agents,
            max_correction_attempts=args.max_correction_attempts,
            max_workflow_depth=args.max_workflow_depth,
            max_runtime_seconds=args.max_runtime_seconds,
            max_estimated_cost=args.max_estimated_cost,
        ),
    )
    status = str(result.get("workflow_status", "FAILED"))
    if status == "COMPLETE":
        return envelope("system.run", "ok", result), EXIT_OK
    if status == "PARTIAL":
        return envelope("system.run", "partial", result), EXIT_OK
    if status == "BLOCKED":
        return envelope("system.run", "blocked", result), EXIT_BLOCKED
    return envelope("system.run", "failed", result), EXIT_FAILED


def _content_relevance(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = assess_relevance(_json(args.site), args.topic, args.market, args.search_volume)
    return envelope("content.relevance", "ok", result), EXIT_OK


def _content_serp(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = assess_serp(
        _json(args.results),
        _json(args.capture),
        args.own_domain,
        known_domain_competitors=args.known_competitor,
        weights=_json(args.weights) if args.weights else None,
        as_of=args.as_of,
        target_intent=args.target_intent,
    )
    status = "blocked" if result.get("status") in {"INSUFFICIENT_EVIDENCE", "STALE_EVIDENCE"} else "ok"
    return envelope("content.serp", status, result), EXIT_BLOCKED if status == "blocked" else EXIT_OK


def _content_brief_decision(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    gains = _json(args.information_gain)
    if not isinstance(gains, list):
        raise ValueError("information-gain file must contain a JSON array")
    result = brief_decision(
        _json(args.relevance),
        _json(args.serp),
        [str(item) for item in gains],
        conditions_resolved=args.conditions_resolved,
        selected_intent=args.selected_intent,
    )
    return envelope("content.brief-decision", "ok" if result.get("publish") else "blocked", result), (
        EXIT_OK if result.get("publish") else EXIT_BLOCKED
    )


def _cluster_serp(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = cluster_serps(
        _json(args.serps),
        _json(args.volumes) if args.volumes else None,
        strong=args.strong,
    )
    return envelope("cluster.serp", "ok", result), EXIT_OK


def _profile_resolve(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = resolve_business_profile(
        explicit_business_type=args.business_type,
        signals=args.signal,
    )
    status = "partial" if result.route == "UNCONFIRMED" else "ok"
    return envelope("profile.resolve", status, result.to_dict()), EXIT_OK


def _privacy_consent(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = diagnose_consent(_json(args.config))
    state = str(result.get("status", "FAIL"))
    if state == "BLOCKED":
        return envelope("privacy.consent", "blocked", result), EXIT_BLOCKED
    if state == "FAIL":
        return envelope("privacy.consent", "failed", result), EXIT_FAILED
    return envelope("privacy.consent", "partial" if state == "PARTIAL" else "ok", result), EXIT_OK


def _report_render(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = write_report(_json(args.input), args.out, args.brand)
    data = {
        "format": result.format,
        "path": str(result.path),
        "message": result.message,
        "reason": result.reason,
        "pdf_verified": result.pdf_verified,
    }
    warnings = [] if result.pdf_verified else ["PDF output is Not Run; styled HTML fallback was produced."]
    return envelope("report.render", "ok", data, warnings=warnings), EXIT_OK


def _benchmark_compare(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = validate_comparison(ROOT)
    return envelope("benchmark.compare", "ok" if result["status"] == "PASS" else "failed", result), (
        EXIT_OK if result["status"] == "PASS" else EXIT_FAILED
    )


def _benchmark_tracer(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    result = evaluate_tracer(Path(args.fixtures) if args.fixtures else None) if args.fixtures else evaluate_tracer()
    return envelope("benchmark.tracer", "ok" if result["verdict"] == "GO" else "failed", result), (
        EXIT_OK if result["verdict"] == "GO" else EXIT_FAILED
    )


HANDLERS: dict[str, Callable[[argparse.Namespace], tuple[dict[str, Any], int]]] = {
    "system_route": _system_route,
    "system_run": _system_run,
    "content_relevance": _content_relevance,
    "content_serp": _content_serp,
    "content_brief_decision": _content_brief_decision,
    "cluster_serp": _cluster_serp,
    "profile_resolve": _profile_resolve,
    "privacy_consent": _privacy_consent,
    "report_render": _report_render,
    "benchmark_compare": _benchmark_compare,
    "benchmark_tracer": _benchmark_tracer,
}


def _common_session(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("request")
    parser.add_argument("--domain", default="")
    parser.add_argument("--business-type", default="unknown")
    parser.add_argument("--profile-signal", action="append", default=[])
    parser.add_argument("--market", action="append", default=[])
    parser.add_argument("--goal", action="append", default=[])
    parser.add_argument("--mode", default="Audit", choices=["Audit", "Implementation", "Strategy", "Monitoring", "Research", "Debate"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="seoctl", description="World-Class SEO Agent System operator CLI")
    parser.add_argument("--registry-check", action="store_true", help="Validate commands and agent execution ownership, then exit.")
    groups = parser.add_subparsers(dest="group")

    system = groups.add_parser("system", help="Route or execute coordinated SEO workflows")
    system_sub = system.add_subparsers(dest="action")
    route = system_sub.add_parser("route")
    _common_session(route)
    route.set_defaults(command_id="system.route")
    run = system_sub.add_parser("run")
    _common_session(run)
    run.add_argument("--llm-provider", default="echo", choices=["echo", "openai", "openai-compatible", "anthropic"])
    run.add_argument("--model", default="")
    run.add_argument("--execution-mode", default="multi-agent", choices=["multi-agent", "single-agent"])
    run.add_argument("--max-nodes", type=int, default=20)
    run.add_argument("--max-llm-calls", type=int, default=12)
    run.add_argument("--max-parallel-agents", type=int, default=3)
    run.add_argument("--max-correction-attempts", type=int, default=1)
    run.add_argument("--max-workflow-depth", type=int, default=5)
    run.add_argument("--max-runtime-seconds", type=int, default=900)
    run.add_argument("--max-estimated-cost", type=float)
    run.set_defaults(command_id="system.run")

    content = groups.add_parser("content")
    content_sub = content.add_subparsers(dest="action")
    relevance = content_sub.add_parser("relevance")
    relevance.add_argument("--site", required=True)
    relevance.add_argument("--topic", required=True)
    relevance.add_argument("--market")
    relevance.add_argument("--search-volume", type=int)
    relevance.set_defaults(command_id="content.relevance")
    serp = content_sub.add_parser("serp")
    serp.add_argument("--results", required=True)
    serp.add_argument("--capture", required=True)
    serp.add_argument("--own-domain", required=True)
    serp.add_argument("--known-competitor", action="append", default=[])
    serp.add_argument("--weights")
    serp.add_argument("--as-of")
    serp.add_argument("--target-intent")
    serp.set_defaults(command_id="content.serp")
    decision = content_sub.add_parser("brief-decision")
    decision.add_argument("--relevance", required=True)
    decision.add_argument("--serp", required=True)
    decision.add_argument("--information-gain", required=True)
    decision.add_argument("--conditions-resolved", action="store_true")
    decision.add_argument("--selected-intent")
    decision.set_defaults(command_id="content.brief-decision")

    cluster_group = groups.add_parser("cluster")
    cluster_sub = cluster_group.add_subparsers(dest="action")
    cluster = cluster_sub.add_parser("serp")
    cluster.add_argument("--serps", required=True)
    cluster.add_argument("--volumes")
    cluster.add_argument("--strong", type=int, default=4)
    cluster.set_defaults(command_id="cluster.serp")

    profile_group = groups.add_parser("profile")
    profile_sub = profile_group.add_subparsers(dest="action")
    profile = profile_sub.add_parser("resolve")
    profile.add_argument("--business-type", default="unknown")
    profile.add_argument("--signal", action="append", default=[])
    profile.set_defaults(command_id="profile.resolve")

    privacy = groups.add_parser("privacy")
    privacy_sub = privacy.add_subparsers(dest="action")
    consent = privacy_sub.add_parser("consent")
    consent.add_argument("--config", required=True)
    consent.set_defaults(command_id="privacy.consent")

    report_group = groups.add_parser("report")
    report_sub = report_group.add_subparsers(dest="action")
    report = report_sub.add_parser("render")
    report.add_argument("--input", required=True)
    report.add_argument("--out", required=True)
    report.add_argument("--brand", default="#0b5fff")
    report.set_defaults(command_id="report.render")

    benchmark = groups.add_parser("benchmark")
    benchmark_sub = benchmark.add_subparsers(dest="action")
    compare = benchmark_sub.add_parser("compare")
    compare.set_defaults(command_id="benchmark.compare")
    tracer = benchmark_sub.add_parser("tracer")
    tracer.add_argument("--fixtures")
    tracer.set_defaults(command_id="benchmark.tracer")
    return parser


def run(argv: list[str] | None = None) -> tuple[dict[str, Any], int]:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry_errors = validate_registry(load_registry())
    if args.registry_check:
        data = {"commands": len(load_registry()["commands"]), "agents": len(load_registry()["agents"]), "errors": registry_errors}
        return envelope("registry.check", "ok" if not registry_errors else "failed", data), (
            EXIT_OK if not registry_errors else EXIT_FAILED
        )
    if registry_errors:
        return envelope("registry.check", "failed", {"errors": registry_errors}), EXIT_FAILED
    command_id = getattr(args, "command_id", None)
    if not command_id:
        return envelope("unknown", "input_error", error={"type": "MissingCommand", "message": "Choose a command. Run seoctl --help."}), EXIT_INPUT
    spec = next(item for item in load_registry()["commands"] if item["id"] == command_id)
    handler = HANDLERS.get(spec["handler"])
    if handler is None:
        return envelope(command_id, "failed", error={"type": "MissingHandler", "message": spec["handler"]}), EXIT_FAILED
    try:
        return handler(args)
    except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return envelope(command_id, "input_error", error={"type": type(exc).__name__, "message": str(exc)}), EXIT_INPUT
    except Exception as exc:  # noqa: BLE001
        return envelope(command_id, "failed", error={"type": type(exc).__name__, "message": str(exc)}), EXIT_FAILED


def main(argv: list[str] | None = None) -> int:
    payload, code = run(argv)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
