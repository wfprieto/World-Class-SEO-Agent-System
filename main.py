"""CLI entrypoint for the World-Class SEO Agent System runtime."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

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
    return ToolRequest(tool=tool, arguments=arguments)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SEO agent system orchestrator.")
    parser.add_argument("request", help="SEO request to route and prepare.")
    parser.add_argument("--domain", default="", help="Target domain or property.")
    parser.add_argument("--business-type", default="unknown", help="Business type.")
    parser.add_argument("--market", action="append", default=[], help="Target market. Repeat for multiple.")
    parser.add_argument("--goal", action="append", default=[], help="SEO/business goal. Repeat for multiple.")
    parser.add_argument("--mode", default="Audit", choices=["Audit", "Implementation", "Strategy", "Monitoring", "Research", "Debate"])
    parser.add_argument("--execute", action="store_true", help="Execute the routed workflow with an LLM client.")
    parser.add_argument("--llm-provider", default=os.getenv("LLM_PROVIDER", "echo"), choices=["echo", "openai", "openai-compatible", "anthropic"], help="LLM provider for execution.")
    parser.add_argument("--model", default="", help="Optional model override for the selected provider.")
    parser.add_argument("--tool", action="append", type=parse_tool_request, default=[], help="Run an adapter before the LLM, such as crawler_csv=path/to/crawl.csv.")
    parser.add_argument("--stream", action="store_true", help="Stream LLM output chunks when executing.")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
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
    )
    result = orchestrator.route(session)
    if args.execute and args.stream:
        async def run_stream() -> None:
            async for chunk in orchestrator.executor.stream(session, result, args.tool):
                print(chunk, end="", flush=True)

        asyncio.run(run_stream())
        return 0
    if args.execute:
        payload = orchestrator.execute(session, result, args.tool)
    else:
        payload = result.to_dict()

    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
