"""Rule group dispatcher for product-proof technical audits."""
from __future__ import annotations

from integrations.product_proof.head_metadata_rules import apply_head_metadata_rules
from integrations.product_proof.rule_types import CrawlEvidence, RuleContext


def apply_technical_rule_groups(rules: RuleContext, crawl: CrawlEvidence) -> None:
    rules.robots(crawl)
    rules.statuses(crawl)
    rules.canon(crawl)
    rules.ai_cwv_facets(crawl)
    apply_head_metadata_rules(rules, crawl)
