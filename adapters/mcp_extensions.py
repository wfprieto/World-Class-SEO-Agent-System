"""Declarative MCP extension registry (capability and permission boundaries).

One source of truth for the optional data providers the kit can use. `docs/mcp-server-mapping.md`
documents the mapping for humans and points here; this module is what code reads.

Governance (per the kit's MCP tool-governance rules):
- Tools are capability boundaries. Each entry declares allowed and forbidden operations.
- Availability is detected from a connected MCP server name or the presence of an env var.
  Presence only. Secret VALUES are never read into the report, logged, or returned.
- Nothing here performs any network call. Detection is free and side-effect-free, so no
  paid or destructive provider call can happen during capability discovery.
- Metered providers require explicit cost approval before any call is made by a skill.
- Write/delete/send/deploy operations are forbidden by default and are not enabled here.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Extension:
    id: str
    provider: str
    cost_tier: str                      # "free" | "metered"
    unlocks: str
    kit_targets: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    forbidden_operations: tuple[str, ...]
    env_vars: tuple[str, ...] = ()
    mcp_hint: str = ""
    fetches_urls: bool = False

    @property
    def requires_cost_approval(self) -> bool:
        return self.cost_tier == "metered"


_READ_ONLY_FORBIDDEN = (
    "write",
    "delete",
    "send",
    "deploy",
    "transfer",
    "export_personal_data",
)

REGISTRY: dict[str, Extension] = {
    e.id: e
    for e in [
        Extension(
            "dataforseo", "DataForSEO", "metered",
            "SERP, keyword, rank, local, marketplace and review data",
            ("marketplace-intelligence", "geo-grid-rank-scan", "serp-overlap-cluster",
             "marketplace-keyword-gap"),
            ("serp_read", "keyword_read", "rank_read", "business_data_read"),
            _READ_ONLY_FORBIDDEN, ("DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD"), "dataforseo",
        ),
        Extension(
            "ahrefs", "Ahrefs", "metered",
            "Authoritative backlink and keyword data",
            ("backlink-profile", "backlink-gap", "competitive-gap"),
            ("backlink_read", "keyword_read"), _READ_ONLY_FORBIDDEN,
            ("AHREFS_API_KEY",), "ahrefs",
        ),
        Extension(
            "firecrawl", "Firecrawl", "metered",
            "Rendered fetch and structured extraction at scale",
            ("rendered-visual-audit", "single-page-audit", "content-audit"),
            ("page_fetch", "structured_extract"),
            _READ_ONLY_FORBIDDEN + ("crawl_private_hosts",),
            ("FIRECRAWL_API_KEY",), "firecrawl", fetches_urls=True,
        ),
        Extension(
            "seranking", "SE Ranking", "metered",
            "Rank tracking and AI share-of-voice",
            ("geo-aio-citation-audit", "competitor-change-monitor"),
            ("rank_read", "visibility_read"), _READ_ONLY_FORBIDDEN,
            ("SERANKING_API_KEY",), "seranking",
        ),
        Extension(
            "profound", "Profound", "metered",
            "LLM-citation tracking across AI answer engines",
            ("geo-aio-citation-audit", "brand-serp-audit"),
            ("citation_read",), _READ_ONLY_FORBIDDEN,
            ("PROFOUND_API_KEY",), "profound",
        ),
        Extension(
            "unlighthouse", "Unlighthouse", "free",
            "Site-wide Lighthouse and Core Web Vitals scanning (self-hosted)",
            ("core-web-vitals-triage", "technical-audit"),
            ("local_scan_read",), _READ_ONLY_FORBIDDEN + ("scan_third_party_targets",),
            (), "unlighthouse", fetches_urls=True,
        ),
        Extension(
            "bing-webmaster", "Bing Webmaster Tools", "free",
            "Bing indexing, crawl and competitor backlink comparison for verified sites",
            ("backlink-profile", "indexation-reality-check"),
            ("index_read", "backlink_read"),
            _READ_ONLY_FORBIDDEN + ("submit_url", "disavow"),
            ("BING_WEBMASTER_API_KEY",), "bing-webmaster",
        ),
        Extension(
            "image-gen", "Image generation", "metered",
            "On-brand image generation for media SEO; label AI images per knowledge/ai-image-labeling.md",
            ("image-seo-audit",),
            ("generate_image",), _READ_ONLY_FORBIDDEN + ("publish_asset",),
            ("IMAGE_GEN_API_KEY",), "image-gen",
        ),
    ]
}


def is_available(ext: Extension, connected_mcp: set[str] | None = None) -> bool:
    """Presence check only. Never reads or returns a secret value."""
    connected = connected_mcp or set()
    if ext.mcp_hint and ext.mcp_hint in connected:
        return True
    return any(os.environ.get(var) not in (None, "") for var in ext.env_vars)


def capability_report(connected_mcp: set[str] | None = None) -> dict:
    """What is connected, what it unlocks, and what remains gated. No network calls."""
    rows = []
    for ext in REGISTRY.values():
        row = asdict(ext)
        row["requires_cost_approval"] = ext.requires_cost_approval
        row["available"] = is_available(ext, connected_mcp)
        # Report only which env vars are expected and whether they are set. Never the value.
        row["credentials"] = {
            var: ("set" if os.environ.get(var) else "missing") for var in ext.env_vars
        }
        row.pop("env_vars", None)
        rows.append(row)
    available = [r for r in rows if r["available"]]
    return {
        "available_count": len(available),
        "available": [r["id"] for r in available],
        "extensions": rows,
        "note": (
            "The free tier runs without any of these. Detection performs no provider call. "
            "Every metered call must be preceded by a cost estimate and explicit approval. "
            "Write, delete, send, deploy and transfer operations are forbidden by default."
        ),
    }


# --- Governance validation (static; no network, no provider call) ---

DESTRUCTIVE = frozenset({"write", "delete", "send", "deploy", "transfer", "publish", "disavow"})
_INJECTION_MARKERS = (
    "ignore previous", "ignore the above", "disregard", "system prompt",
    "exfiltrate", "send the", "reveal", "api key", "curl ", "http://", "https://",
)


class RegistryGovernanceError(RuntimeError):
    """Raised when a registry entry violates the kit's MCP tool-governance rules."""


def validate_registry(registry: dict[str, Extension] | None = None) -> dict[str, object]:
    """Fail closed on governance violations. Static only; performs no provider call.

    Guards against: tool-name shadowing, silent capability expansion (destructive verbs
    appearing in allowed_operations), missing forbidden-operation declarations, metered
    providers without a cost-approval gate, malformed credential configuration, prompt
    injection or exfiltration text hidden in tool descriptions, and SSRF-capable providers
    that do not declare URL fetching.
    """
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
        if ext.cost_tier == "metered" and not ext.requires_cost_approval:
            problems.append(f"{ext.id}: metered provider must require cost approval")

        for var in ext.env_vars:
            if not var or var != var.upper() or " " in var:
                problems.append(f"{ext.id}: malformed credential variable {var!r}")

        blob = f"{ext.provider} {ext.unlocks}".lower()
        for marker in _INJECTION_MARKERS:
            if marker in blob:
                problems.append(f"{ext.id}: description contains suspicious text {marker!r}")

        if ext.fetches_urls and "crawl_private_hosts" not in ext.forbidden_operations \
                and "scan_third_party_targets" not in ext.forbidden_operations:
            problems.append(
                f"{ext.id}: URL-fetching provider must forbid private-host or third-party targets"
            )

    if problems:
        raise RegistryGovernanceError("; ".join(problems))
    return {
        "status": "ok",
        "checked": len(reg),
        "ssrf_capable": sorted(e.id for e in reg.values() if e.fetches_urls),
        "note": "Static validation only. No provider was contacted and no secret value was read.",
    }
