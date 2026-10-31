"""CLI boundary for bounded image-generation request plans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from integrations.extensions.providers import image_generation_service
from seoctl.cli import envelope, exit_code_for_status
from seoctl.composition import build_provider_service


def image_plan(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    request_path = Path(args.request)
    if request_path.stat().st_size > 1_000_000:
        raise ValueError("image request exceeds 1000000 bytes")
    request = json.loads(request_path.read_text(encoding="utf-8-sig"))
    result = image_generation_service(build_provider_service()).plan(
        request=request,
        units=args.units,
        unit_cost=args.unit_cost,
        approved_ceiling=args.ceiling,
        approved=args.approve,
    )
    return envelope(
        "media.image-plan", result.status, result.data, warnings=result.warnings
    ), exit_code_for_status(result.status)


def add_image_plan_parser(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "image-plan",
        help="Authorize a bounded optional-provider image request without generating or publishing",
    )
    parser.add_argument("--request", required=True)
    parser.add_argument("--units", type=int, default=1)
    parser.add_argument("--unit-cost", type=float)
    parser.add_argument("--ceiling", type=float)
    parser.add_argument("--approve", action="store_true")
    parser.set_defaults(handler="media_image_plan")
