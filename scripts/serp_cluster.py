"""SERP-overlap topic clustering (stdlib only, deterministic).

Groups keywords by how search engines actually rank them (shared top-10 URLs), not by
text similarity. Two keywords sharing many top-10 results serve the same intent and
usually belong in one cluster. Emits hub-and-spoke architecture and an internal-link
matrix for the `serp-overlap-cluster` skill.

Uses only observed SERP results supplied by the caller. It never fabricates rankings,
volumes, intent, CPC or competitor data, and never calls a provider.

Thresholds (shared top-10 URLs): >= strong (default 4) or exactly 3 => same cluster; <= 2 => separate.
Similarity groups intent. It is not proof that a page will rank.

Usage: python serp_cluster.py serps.json [--volumes vols.json] [--strong 4] [--out clusters.json]
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any


def load_json(path: str) -> Any:
    """Read JSON tolerating a UTF-8 BOM (common in Windows exports)."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


class _DisjointSet:
    def __init__(self, items) -> None:
        self.parent = {item: item for item in items}

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a, b) -> None:
        self.parent[self.find(a)] = self.find(b)


def cluster(serps: dict[str, list[str]], volumes: dict[str, float] | None = None,
            strong: int = 4) -> dict:
    """Cluster keywords by shared top-10 URLs. Deterministic for identical input."""
    if not isinstance(serps, dict):
        raise TypeError("serps must be a mapping of keyword -> list of result URLs")
    keywords = sorted(serps)  # sorted => deterministic ordering
    sets = {k: {u for u in (serps.get(k) or []) if u} for k in keywords}

    disjoint = _DisjointSet(keywords)
    edges: list[dict[str, Any]] = []
    for a, b in combinations(keywords, 2):
        shared = len(sets[a] & sets[b])
        if shared >= strong or shared == 3:
            disjoint.union(a, b)
            edges.append({"a": a, "b": b, "shared": shared})

    groups: dict[str, list[str]] = {}
    for keyword in keywords:
        groups.setdefault(disjoint.find(keyword), []).append(keyword)

    volumes = volumes or {}
    connectivity = {
        k: sum(1 for e in edges if k in (e["a"], e["b"])) for k in keywords
    }
    clusters = []
    for members in groups.values():
        members = sorted(members)
        # Hub: highest supplied volume, then connectivity, then name (stable ties).
        hub = max(members, key=lambda m: (volumes.get(m, 0), connectivity[m], m))
        spokes = [m for m in members if m != hub]
        spokes.sort(key=lambda m: (-volumes.get(m, 0), m))
        clusters.append(
            {
                "hub": hub,
                "hub_volume": volumes.get(hub),
                "spokes": spokes,
                "size": len(members),
                "internal_links": _link_matrix(hub, spokes),
            }
        )
    clusters.sort(key=lambda c: (-c["size"], -(c["hub_volume"] or 0), c["hub"]))
    return {
        "cluster_count": len(clusters),
        "keyword_count": len(keywords),
        "strong_threshold": strong,
        "clusters": clusters,
        "edges": sorted(edges, key=lambda e: (e["a"], e["b"])),
        "note": "SERP overlap groups intent. It does not prove ranking success.",
    }


def _link_matrix(hub: str, spokes: list[str]) -> list[dict[str, str]]:
    links = [{"from": s, "to": hub, "type": "spoke->hub"} for s in spokes]
    links += [{"from": hub, "to": s, "type": "hub->spoke"} for s in spokes]
    return links


def to_markdown(result: dict) -> str:
    lines = [
        f"# Topic Clusters ({result['cluster_count']} clusters, {result['keyword_count']} keywords)",
        "",
    ]
    for index, item in enumerate(result["clusters"], 1):
        volume = f" (volume {item['hub_volume']})" if item.get("hub_volume") is not None else ""
        lines.append(f"## Cluster {index}: {item['hub']}{volume} — hub/pillar page")
        if item["spokes"]:
            lines.append("Supporting pages (each links up to the hub):")
            lines += [f"- {s}" for s in item["spokes"]]
        else:
            lines.append("Single-keyword cluster: one focused page.")
        lines.append("")
    lines.append(result["note"])
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Cluster keywords by SERP overlap")
    parser.add_argument("serps", help="JSON: {keyword: [top-10 result URLs]}")
    parser.add_argument("--volumes", help="Optional JSON: {keyword: volume}")
    parser.add_argument("--strong", type=int, default=4)
    parser.add_argument("--out", default="outputs/clusters.json")
    args = parser.parse_args()

    result = cluster(load_json(args.serps),
                     load_json(args.volumes) if args.volumes else None,
                     strong=args.strong)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    out.with_suffix(".md").write_text(to_markdown(result), encoding="utf-8")
    print(f"{result['cluster_count']} clusters from {result['keyword_count']} keywords -> {args.out}")
