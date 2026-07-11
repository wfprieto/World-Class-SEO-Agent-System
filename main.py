"""CLI entrypoint for the World-Class SEO Agent System runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from runtime.execution_limits import ExecutionLimits
from runtime.llm import build_llm_client
from runtime.orchestrator import SEOOrchestrator
from runtime.tools import ToolRequest


def parse_tool_request(value: str) -> ToolRequest:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Tool requests must use adapter=path-or-json.")
    tool, raw = value.split("=", 1)
    try:
        arguments = json.loads(raw)
        if not isinstance(arguments, dict):
            arguments = {"path": raw}
    except json.JSONDecodeError:
        arguments = {"path": raw}
    required = bool(arguments.pop("_required", False))
    return ToolRequest(tool=tool, arguments=arguments, required=required)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SEO agent system orchestrator.")
    parser.add_argument("request", help="SEO request to route and prepare.")
    parser.add_argument("--domain", default="", help="Target domain or property.")
    parser.add_argument("--business-type", default="unknown", help="Explicit business profile or declared hybrid.")
    parser.add_argument("--profile-signal", action="append", default=[], help="Observed business-profile signal. Repeat for multiple signals.")
    parser.add_argument("--market", action="append", default=[], help="Target market. Repeat for multiple.")
    parser.add_argument("--goal", action="append", default=[], help="SEO/business goal. Repeat for multiple.")
    parser.add_argument("--mode", default="Audit", choices=["Audit", "Implementation", "Strategy", "Monitoring", "Research", "Debate"])
    parser.add_argument("--execute", action="store_true", help="Execute the routed workflow with an LLM client.")
    parser.add_argument("--execution-mode", default="multi-agent", choices=["multi-agent", "single-agent"], help="Use coordinated agents or the debug comparison path.")
    parser.add_argument("--llm-provider", default=os.getenv("LLM_PROVIDER", "echo"), choices=["echo", "openai", "openai-compatible", "anthropic"], help="LLM provider for execution.")
    parser.add_argument("--model", default="", help="Optional model override for the selected provider.")
    parser.add_argument("--tool", action="append", type=parse_tool_request, default=[], help="Run an adapter before agents. Add _required=true in JSON to make missing evidence blocking.")
    parser.add_argument("--stream", action="store_true", help="Stream the single-agent debug output.")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    parser.add_argument("--max-nodes", type=int, default=20)
    parser.add_argument("--max-llm-calls", type=int, default=12)
    parser.add_argument("--max-parallel-agents", type=int, default=3)
    parser.add_argument("--max-correction-attempts", type=int, default=1)
    parser.add_argument("--max-workflow-depth", type=int, default=5)
    parser.add_argument("--max-runtime-seconds", type=int, default=900)
    parser.add_argument("--max-estimated-cost", type=float, default=None)
    args = parser.parse_args()

    orchestrator = SEOOrchestrator(
        repo_root=Path(__file__).parent,
        llm_client=build_llm_client(args.llm_provider, args.model or None),
    )
    session = orchestrator.start_session(
        request=args.request,
        mode=args.mode,
        domain=args.domain,
        business_type=args.business_type,
        markets=args.market,
        goals=args.goal,
        profile_signals=args.profile_signal,
    )
    result = orchestrator.route(session)
    if args.execute and args.stream:
        if args.execution_mode != "single-agent":
            parser.error("--stream is available only with --execution-mode single-agent")

        async def run_stream() -> None:
            async for chunk in orchestrator.executor.stream(session, result, args.tool):
                print(chunk, end="", flush=True)

        asyncio.run(run_stream())
        return 0
    if args.execute:
        limits = ExecutionLimits(
            max_nodes=args.max_nodes,
            max_llm_calls=args.max_llm_calls,
            max_parallel_agents=args.max_parallel_agents,
            max_correction_attempts=args.max_correction_attempts,
            max_workflow_depth=args.max_workflow_depth,
            max_runtime_seconds=args.max_runtime_seconds,
            max_estimated_cost=args.max_estimated_cost,
        )
        payload = orchestrator.execute(
            session,
            result,
            args.tool,
            execution_mode=args.execution_mode,
            limits=limits,
        )
    else:
        payload = result.to_dict()

    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
