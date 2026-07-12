"""Governed optional integration registry and executable preflight helpers.

This remains the single machine-readable authority for optional providers. Discovery,
preflight, configuration rendering, and cost estimation perform no provider calls and
never return secret values.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Extension:
    id: str
    provider: str
    cost_tier: str
    unlocks: str
    kit_targets: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    env_vars: tuple[str, ...] = ()
    mcp_hint: str = ""
    fetches_urls: bool = False
    official_docs: str = ""
    remote_endpoint: str = ""
    transport: str = "manual"
    auth_mode: str = "unknown"
    verified_at: str = "2026-07-12"
    live_state: str = "CONFIGURABLE"
    removal_note: str = "Remove the provider configuration and related environment variables."


_READ_ONLY_FORBIDDEN = (
    "write", "delete", "send", "deploy", "transfer", "export_personal_data",
)

REGISTRY: dict[str, Extension] = {
    e.id: e for e in [
        Extension(
            "dataforseo", "DataForSEO", "metered",
            "SERP, keyword, rank, local, marketplace and review data",
            ("marketplace-intelligence", "geo-grid-rank-scan", "serp-overlap-cluster",
             "marketplace-keyword-gap"),
            ("serp_read", "keyword_read", "rank_read", "business_data_read"),
            _READ_ONLY_FORBIDDEN,
            ("DATAFORSEO_USERNAME", "DATAFORSEO_PASSWORD"), "dataforseo", False,
            "https://dataforseo.com/model-context-protocol",
            "https://mcp.dataforseo.com/mcp", "streamable_http",
            "oauth_or_basic_auth", "2026-07-12", "CONFIGURABLE",
        ),
        Extension(
            "ahrefs", "Ahrefs", "metered",
            "Backlink and keyword data under provider-specific API-unit limits",
            ("backlink-profile", "backlink-gap", "competitive-gap"),
            ("backlink_read", "keyword_read"), _READ_ONLY_FORBIDDEN,
            ("AHREFS_API_KEY",), "ahrefs", False,
            "https://docs.ahrefs.com/en/mcp/docs/introduction",
            "https://api.ahrefs.com/mcp/mcp", "streamable_http",
            "oauth_or_mcp_scoped_key", "2026-07-12", "HOST_CLIENT_ONLY",
            "Disconnect the Ahrefs MCP connection and revoke its MCP-scoped key.",
        ),
        Extension(
            "firecrawl", "Firecrawl", "metered",
            "Rendered fetch and structured extraction at scale",
            ("rendered-visual-audit", "single-page-audit", "content-audit"),
            ("page_fetch", "structured_extract"),
            _READ_ONLY_FORBIDDEN + ("crawl_private_hosts",),
            ("FIRECRAWL_API_KEY",), "firecrawl", True,
            "https://docs.firecrawl.dev/use-cases/developers-mcp",
            "", "host_configured_mcp", "api_key", "2026-07-12", "CONFIGURABLE",
        ),
        Extension(
            "seranking", "SE Ranking", "metered",
            "Rank, backlink, audit, domain and AI-search visibility data",
            ("geo-aio-citation-audit", "competitor-change-monitor", "backlink-gap"),
            ("rank_read", "visibility_read", "backlink_read", "audit_read"),
            _READ_ONLY_FORBIDDEN,
            ("SERANKING_API_KEY",), "se-ranking", False,
            "https://seranking.com/api/integrations/mcp/",
            "https://api.seranking.com/mcp", "streamable_http",
            "oauth_2_1_or_api_key", "2026-07-12", "CONFIGURABLE",
        ),
        Extension(
            "profound", "Profound", "metered",
            "AI-answer visibility, citation, prompt, referral and crawler reports",
            ("geo-aio-citation-audit", "brand-serp-audit"),
            ("citation_read", "visibility_read", "prompt_read", "traffic_read"),
            _READ_ONLY_FORBIDDEN,
            ("PROFOUND_API_KEY",), "profound", False,
            "https://docs.tryprofound.com/mcp/capabilities/analytics-capabilities",
            "", "host_configured_mcp", "oauth_or_api_key", "2026-07-12", "CONFIGURABLE",
        ),
        Extension(
            "unlighthouse", "Unlighthouse", "free",
            "Site-wide local Lighthouse scanning",
            ("core-web-vitals-triage", "technical-audit"),
            ("local_scan_read",), _READ_ONLY_FORBIDDEN + ("scan_third_party_targets",),
            (), "unlighthouse", True,
            "https://unlighthouse.dev/", "", "local_tool", "none",
            "2026-07-12", "LOCAL_OPTIONAL",
        ),
        Extension(
            "bing-webmaster", "Bing Webmaster Tools", "free",
            "Verified-site indexing, crawl and backlink evidence",
            ("backlink-profile", "indexation-reality-check"),
            ("index_read", "backlink_read"),
            _READ_ONLY_FORBIDDEN + ("submit_url", "disavow"),
            ("BING_WEBMASTER_API_KEY",), "bing-webmaster", False,
            "https://www.bing.com/webmasters/", "", "direct_api",
            "unverified_current_contract", "2026-07-12", "BLOCKED_BY_CONTRACT",
            "Remove the Bing Webmaster key and connector configuration.",
        ),
        Extension(
            "image-gen", "Image generation", "metered",
            "On-brand media generation with provenance and labeling gates",
            ("image-seo-audit",),
            ("generate_image",), _READ_ONLY_FORBIDDEN + ("publish_asset",),
            ("IMAGE_GEN_API_KEY",), "image-gen", False,
            "", "", "provider_specific", "provider_specific",
            "2026-07-12", "CONFIGURABLE",
        ),
    ]
}


def is_available(ext: Extension, connected_mcp: set[str] | None = None) -> bool:
    """Presence check only. Multi-variable credentials require every value."""
    connected = connected_mcp or set()
    if ext.mcp_hint and ext.mcp_hint in connected:
        return True
    if not ext.env_vars:
        return False
    return all(os.environ.get(var) not in (None, "") for var in ext.env_vars)


def _credentials(ext: Extension) -> dict[str, str]:
    return {var: ("set" if os.environ.get(var) else "missing") for var in ext.env_vars}


def capability_report(connected_mcp: set[str] | None = None) -> dict[str, Any]:
    rows = []
    for ext in REGISTRY.values():
        row = asdict(ext)
        row["requires_cost_approval"] = ext.cost_tier == "metered"
        row["available"] = is_available(ext, connected_mcp)
        row["credentials"] = _credentials(ext)
        row.pop("env_vars", None)
        rows.append(row)
    available = [row["id"] for row in rows if row["available"]]
    return {
        "available_count": len(available),
        "available": available,
        "extensions": rows,
        "note": (
            "Discovery performs no provider call and returns no secret values. "
            "Metered calls require a current cost estimate, an approved ceiling, "
            "and explicit authorization. Write operations remain separately gated."
        ),
    }


def preflight(provider_id: str, connected_mcp: set[str] | None = None) -> dict[str, Any]:
    if provider_id not in REGISTRY:
        raise ValueError(f"unknown provider: {provider_id}")
    ext = REGISTRY[provider_id]
    available = is_available(ext, connected_mcp)
    state = ext.live_state
    if state not in {"BLOCKED_BY_CONTRACT", "HOST_CLIENT_ONLY"}:
        state = "AVAILABLE" if available else "NOT_CONFIGURED"
    return {
        "provider": ext.id,
        "name": ext.provider,
        "state": state,
        "available": available,
        "credentials": _credentials(ext),
        "transport": ext.transport,
        "auth_mode": ext.auth_mode,
        "remote_endpoint": ext.remote_endpoint,
        "official_docs": ext.official_docs,
        "verified_at": ext.verified_at,
        "requires_cost_approval": ext.cost_tier == "metered",
        "allowed_operations": list(ext.allowed_operations),
        "forbidden_operations": list(ext.forbidden_operations),
        "removal_note": ext.removal_note,
        "warnings": (
            ["Current safe direct-API authentication contract is not verified; live use is blocked."]
            if ext.live_state == "BLOCKED_BY_CONTRACT"
            else []
        ),
    }


def render_config(provider_id: str, client: str = "generic") -> dict[str, Any]:
    """Return a credential-free setup template. Never writes host configuration."""
    ext = REGISTRY.get(provider_id)
    if ext is None:
        raise ValueError(f"unknown provider: {provider_id}")
    if client not in {"generic", "codex", "claude"}:
        raise ValueError("client must be generic, codex, or claude")
    if ext.live_state == "BLOCKED_BY_CONTRACT":
        return {
            "provider": provider_id,
            "client": client,
            "state": "BLOCKED_BY_CONTRACT",
            "configuration": None,
            "reason": "Current official direct-API authentication behavior is not safely verified.",
        }
    placeholders = {var: f"${{{var}}}" for var in ext.env_vars}
    config: dict[str, Any] = {
        "name": ext.mcp_hint or ext.id,
        "transport": ext.transport,
        "url": ext.remote_endpoint or None,
        "environment": placeholders,
    }
    if client == "codex" and ext.remote_endpoint:
        config["command_preview"] = (
            f"codex mcp add {ext.mcp_hint or ext.id} --url {ext.remote_endpoint}"
        )
    elif client == "claude" and ext.remote_endpoint:
        config["command_preview"] = (
            f"claude mcp add --transport http {ext.mcp_hint or ext.id} {ext.remote_endpoint}"
        )
    return {
        "provider": provider_id,
        "client": client,
        "state": "TEMPLATE_ONLY",
        "configuration": config,
        "warning": "Template contains placeholders only and was not installed or connected.",
        "removal_note": ext.removal_note,
    }


def estimate_cost(
    provider_id: str,
    *,
    units: int,
    unit_cost: float | None = None,
    approved_ceiling: float | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    ext = REGISTRY.get(provider_id)
    if ext is None:
        raise ValueError(f"unknown provider: {provider_id}")
    if not isinstance(units, int) or isinstance(units, bool) or not 1 <= units <= 1_000_000:
        raise ValueError("units must be an integer from 1 to 1000000")
    if ext.cost_tier == "free":
        return {
            "provider": provider_id, "state": "AVAILABLE", "units": units,
            "estimated_cost": 0.0, "currency": "USD", "approved": True,
            "note": "Provider is classified as free/self-hosted; infrastructure cost may still apply.",
        }
    if unit_cost is None:
        return {
            "provider": provider_id, "state": "BLOCKED", "units": units,
            "estimated_cost": None, "currency": "USD", "approved": False,
            "reason": "A current operator-verified unit cost is required; pricing is not hard-coded.",
        }
    cost = float(unit_cost) * units
    if unit_cost < 0 or not (cost >= 0 and cost < float("inf")):
        raise ValueError("unit_cost must be a finite non-negative number")
    ceiling_ok = approved_ceiling is not None and approved_ceiling >= cost
    return {
        "provider": provider_id,
        "state": "APPROVED" if approved and ceiling_ok else "BLOCKED",
        "units": units,
        "unit_cost": float(unit_cost),
        "estimated_cost": round(cost, 6),
        "currency": "USD",
        "approved_ceiling": approved_ceiling,
        "approved": bool(approved and ceiling_ok),
        "reason": None if approved and ceiling_ok else (
            "Explicit approval and a ceiling at or above the estimate are required."
        ),
    }


DESTRUCTIVE = frozenset({"write", "delete", "send", "deploy", "transfer", "publish", "disavow"})
_INJECTION_MARKERS = (
    "ignore previous", "ignore the above", "disregard", "system prompt",
    "exfiltrate", "send the", "reveal", "api key", "curl ", "http://",
)


class RegistryGovernanceError(RuntimeError):
    pass


def validate_registry(registry: dict[str, Extension] | None = None) -> dict[str, object]:
    reg = registry if registry is not None else REGISTRY
    problems: list[str] = []
    seen: set[str] = set()
    for key, ext in reg.items():
        if key != ext.id:
            problems.append(f"{key}: registry key does not match extension id {ext.id!r}")
        if ext.id in seen:
            problems.append(f"{ext.id}: duplicate id (tool-name shadowing)")
        seen.add(ext.id)
        for op in ext.allowed_operations:
            if any(verb in op.lower() for verb in DESTRUCTIVE):
                problems.append(f"{ext.id}: destructive operation {op!r} in allowed_operations")
        if not ext.forbidden_operations:
            problems.append(f"{ext.id}: must declare forbidden operations")
        if ext.cost_tier not in {"free", "metered"}:
            problems.append(f"{ext.id}: invalid cost_tier {ext.cost_tier!r}")
        for var in ext.env_vars:
            if not var or var != var.upper() or " " in var:
                problems.append(f"{ext.id}: malformed credential variable {var!r}")
        blob = f"{ext.provider} {ext.unlocks}".lower()
        for marker in _INJECTION_MARKERS:
            if marker in blob:
                problems.append(f"{ext.id}: description contains suspicious text {marker!r}")
        if ext.fetches_urls and not (
            {"crawl_private_hosts", "scan_third_party_targets"} & set(ext.forbidden_operations)
        ):
            problems.append(
                f"{ext.id}: URL-fetching provider must forbid private-host or third-party targets"
            )
        if ext.remote_endpoint and not ext.remote_endpoint.startswith("https://"):
            problems.append(f"{ext.id}: remote endpoint must use HTTPS")
    if problems:
        raise RegistryGovernanceError("; ".join(problems))
    return {
        "status": "ok",
        "checked": len(reg),
        "ssrf_capable": sorted(e.id for e in reg.values() if e.fetches_urls),
        "note": "Static validation only. No provider was contacted and no secret value was read.",
    }
