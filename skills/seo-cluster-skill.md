# SERP-Overlap Topic Clustering Skill

Skill for the SEO Information Architecture Agent and SEO Copywriter/Content Agent. Follows `skill-definition-standard.md`.
SKILL_INDEX category: Content and IA Skills.

Groups keywords by shared top-10 Google results, not text similarity, then designs hub-and-spoke content architecture. Script: `scripts/serp_cluster.py`.

---

## `serp-overlap-cluster`

Purpose: Turn a keyword set into a defensible content architecture by clustering on real SERP overlap and assigning hub (pillar) and spoke (supporting) pages.

System prompt: Act as a content architect. Cluster by how Google actually ranks keywords, not by how similar the words look. Two keywords sharing many top-10 URLs are the same intent and usually belong on one page or one tight cluster.

Required inputs:

- A seed keyword or an existing keyword set
- Top-10 organic results per keyword (from a connected SERP source or supplied export). Ads, snippets, and PAA excluded.
- Optional: monthly volume per keyword to pick hubs by demand

Execution steps:

1. Expand the seed into 30-50 variants (related searches, PAA, long-tail and intent modifiers, question forms). Deduplicate.
2. Capture the top-10 organic URLs per keyword from the connected source. If none is connected, request the export and stop rather than guessing.
3. Run `serp_cluster.py`: overlap of >= 4 shared URLs is a strong same-cluster signal; 3 is moderate; <= 2 is separate. Keywords that share many results collapse into one cluster.
4. Assign the hub (highest demand, tie-broken by connectivity) and spokes; build the internal-link matrix (spokes link up to the hub, hub links down to spokes).
5. Output the cluster map, per-cluster page plan, and link matrix. Flag single-keyword clusters as focused one-page targets.

Output format:

- `clusters.json` (machine-readable) and a markdown cluster map: each cluster's hub/pillar page, its supporting pages, and the internal links. Recommend one page type per cluster.

Quality gate:

- Clusters are grounded in observed SERP overlap, not asserted similarity. Do not merge two distinct-intent clusters just because a few results overlap. Do not fabricate SERP results or volumes.

Failure conditions:

- No SERP source connected. Fewer than ~10 keywords after expansion.

Fallback:

- If SERP data is unavailable, produce an intent-grouped draft labeled ANALYSIS and mark that SERP-overlap validation is pending.
