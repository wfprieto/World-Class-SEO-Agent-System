from __future__ import annotations

from pathlib import Path

from adapters.crawler_csv import CrawlerCSVAdapter
from adapters.schema_validation import SchemaValidationAdapter


def test_schema_validation_adapter_flags_missing_type():
    result = SchemaValidationAdapter().fetch({"@context": "https://schema.org"})
    assert result.status == "needs-review"
    assert "Missing @type." in result.warnings


def test_crawler_csv_adapter_parses_status_counts(tmp_path: Path):
    path = tmp_path / "crawl.csv"
    path.write_text("Address,Status Code\nhttps://example.com,200\nhttps://example.com/missing,404\n", encoding="utf-8")
    result = CrawlerCSVAdapter().fetch(str(path))
    assert result.status == "ok"
    assert result.data["row_count"] == 2
    assert result.data["status_counts"]["200"] == 1
    assert result.data["status_counts"]["404"] == 1

