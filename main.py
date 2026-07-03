"""CLI entrypoint for the World-Class SEO Agent System runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from runtime.orchestrator import SEOOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the SEO agent system orchestrator.")
    parser.add_argument("request", help="SEO request to route and prepare.")
    parser.add_argument("--domain", default="", help="Target domain or property.")
    parser.add_argument("--business-type", default="unknown", help="Business type.")
    parser.add_argument("--market", action="append", default=[], help="Target market. Repeat for multiple.")
    parser.add_argument("--goal", action="append", default=[], help="SEO/business goal. Repeat for multiple.")
    parser.add_argument("--mode", default="Audit", choices=["Audit", "Implementation", "Strategy", "Monitoring", "Research", "Debate"])
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    orchestrator = SEOOrchestrator(repo_root=Path(__file__).parent)
    session = orchestrator.start_session(
        request=args.request,
        mode=args.mode,
        domain=args.domain,
        business_type=args.business_type,
        markets=args.market,
        goals=args.goal,
    )
    result = orchestrator.route(session)
    payload = result.to_dict()

    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

