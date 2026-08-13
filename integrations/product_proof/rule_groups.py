"""Rule group dispatcher for product-proof technical audits."""
from __future__ import annotations

from typing import Any

from integrations.product_proof.head_metadata_rules import apply_head_metadata_rules


def apply_technical_rule_groups(rules: Any, crawl: dict[str, Any]) -> None:
    rules.robots(crawl)
    rules.statuses(crawl)
    rules.canon(crawl)
    rules.ai_cwv_facets(crawl)
    apply_head_metadata_rules(rules, crawl)
