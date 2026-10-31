"""Public retention/deletion contracts over synthetic, in-memory evidence only."""

from __future__ import annotations

import math

import pytest

from adapters.evidence_store import EvidenceStore, EvidenceStoreError


def test_purge_retains_newest_per_url_group_and_schema_with_stable_tie_order() -> None:
    series = [
        ("https://example.com/a", "crawl", "1", [1, 5, 5, 10]),
        ("https://example.com/a", "crawl", "2", [1]),
        ("https://example.com/a", "performance", "1", [1, 2]),
        ("https://example.com/b", "crawl", "1", [0, 2, 4]),
    ]
    with EvidenceStore(":memory:") as store:
        originals = {}
        for url, group, schema, timestamps in series:
            for ordinal, timestamp in enumerate(timestamps):
                store.record(
                    url, group, {"ordinal": ordinal}, schema_version=schema,
                    captured_at=timestamp, source="synthetic retention fixture",
                )
            originals[(url, group, schema)] = store.latest(url, group, limit=10, schema_version=schema)

        assert store.purge(before=8, keep_latest=2) == 3
        for url, group, schema, _timestamps in series:
            # Whole verified records include payload/record digests and provenance.
            assert store.latest(url, group, limit=10, schema_version=schema) == originals[(url, group, schema)][:2]
        assert store.integrity_check() == {
            "status": "ok", "sqlite_quick_check": ["ok"],
            "payloads_checked": 7, "errors": [],
        }


def test_purge_combines_filters_and_uses_strict_cutoff_without_rewriting_survivors() -> None:
    url = "https://example.com/a"
    with EvidenceStore(":memory:") as store:
        for timestamp in (4, 5, 6):
            store.record(url, "crawl", {"at": timestamp}, captured_at=timestamp)
        protected = [
            (url, "crawl", "2"),
            (url, "other-group", "1"),
            ("https://example.com/b", "crawl", "1"),
        ]
        for target, group, schema in protected:
            store.record(target, group, {"protected": True}, schema_version=schema, captured_at=1)
        originals = {
            key: store.latest(key[0], key[1], schema_version=key[2]) for key in protected
        }
        retained = store.latest(url, "crawl", limit=3, schema_version="1")[:2]

        assert store.purge(
            before=5, keep_latest=0, url="https://EXAMPLE.com:443/a#fragment",
            metric_group=" crawl ", schema_version=" 1 ",
        ) == 1
        assert store.latest(url, "crawl", limit=10, schema_version="1") == retained
        assert [row["captured_at"] for row in retained] == [6.0, 5.0]
        for target, group, schema in protected:
            assert store.latest(target, group, schema_version=schema) == originals[(target, group, schema)]
        assert store.purge(before=0, keep_latest=0) == 0
        assert store.integrity_check()["payloads_checked"] == 5


def test_delete_scopes_metric_group_across_schemas_and_preserves_other_urls() -> None:
    url = "https://example.com/a"
    with EvidenceStore(":memory:") as store:
        for schema in ("1", "1", "2"):
            store.record(url, "crawl", {"schema": schema}, schema_version=schema, captured_at=1)
        store.record(url, "other-group", {"keep": True}, captured_at=1)
        store.record("https://example.com/b", "crawl", {"keep": True}, captured_at=1)
        other_group = store.latest(url, "other-group")
        other_url = store.latest("https://example.com/b", "crawl")

        assert store.delete(" https://EXAMPLE.com:443/a#fragment ", metric_group=" crawl ") == 3
        assert store.latest(url, "crawl", limit=10) == []
        assert store.latest(url, "other-group") == other_group
        assert store.latest("https://example.com/b", "crawl") == other_url
        assert store.delete(url) == 1
        assert store.delete(url) == 0
        assert store.latest("https://example.com/b", "crawl") == other_url
        assert store.integrity_check()["payloads_checked"] == 1


@pytest.mark.parametrize("operation", ["purge", "delete"])
def test_retention_filters_treat_sql_metacharacters_as_literal_labels(operation: str) -> None:
    label = "fixture' OR 1=1 --"
    url = "https://example.com/a"
    with EvidenceStore(":memory:") as store:
        store.record(url, label, {"remove": True}, schema_version=label, captured_at=1)
        store.record(url, "protected", {"keep": True}, captured_at=1)
        store.record("https://example.com/b", label, {"keep": True}, schema_version=label, captured_at=1)
        protected = store.latest(url, "protected")
        protected_url = store.latest("https://example.com/b", label, schema_version=label)
        if operation == "purge":
            removed = store.purge(before=2, keep_latest=0, url=url, metric_group=label, schema_version=label)
        else:
            removed = store.delete(url, metric_group=label)
        assert removed == 1
        assert store.latest(url, label) == []
        assert store.latest(url, "protected") == protected
        assert store.latest("https://example.com/b", label, schema_version=label) == protected_url
        assert store.integrity_check()["status"] == "ok"


@pytest.mark.parametrize("before", [-1, math.inf, math.nan])
def test_invalid_purge_cutoffs_do_not_delete_evidence(before: float) -> None:
    with EvidenceStore(":memory:") as store:
        store.record("https://example.com/", "crawl", {"keep": True}, captured_at=1)
        original = store.latest("https://example.com/", "crawl")
        with pytest.raises(ValueError, match="before must be a finite non-negative timestamp"):
            store.purge(before=before, keep_latest=0)
        assert store.latest("https://example.com/", "crawl") == original


@pytest.mark.parametrize("keep_latest", [True, -1, 1.5, "1"])
def test_invalid_retention_counts_do_not_delete_evidence(keep_latest: object) -> None:
    with EvidenceStore(":memory:") as store:
        store.record("https://example.com/", "crawl", {"keep": True}, captured_at=1)
        original = store.latest("https://example.com/", "crawl")
        with pytest.raises(ValueError, match="keep_latest must be a non-negative integer"):
            store.purge(before=10, keep_latest=keep_latest)
        assert store.latest("https://example.com/", "crawl") == original


@pytest.mark.parametrize("operation", ["purge", "delete"])
@pytest.mark.parametrize("label", ["", " ", "x" * 2049])
def test_invalid_retention_group_labels_preserve_records(operation: str, label: str) -> None:
    with EvidenceStore(":memory:") as store:
        store.record("https://example.com/", "crawl", {"keep": True}, captured_at=1)
        original = store.latest("https://example.com/", "crawl")
        with pytest.raises(ValueError, match="metric_group"):
            if operation == "purge":
                store.purge(before=10, keep_latest=0, metric_group=label)
            else:
                store.delete("https://example.com/", metric_group=label)
        assert store.latest("https://example.com/", "crawl") == original


def test_close_is_idempotent_and_read_or_context_reentry_fails_closed() -> None:
    store = EvidenceStore(":memory:")
    store.record("https://example.com/", "crawl", {"fixture": True}, captured_at=1)
    store.close()
    store.close()
    with pytest.raises(EvidenceStoreError, match="EvidenceStore is closed"):
        store.latest("https://example.com/", "crawl")
    with pytest.raises(EvidenceStoreError, match="EvidenceStore is closed"), store:
        pytest.fail("closed evidence store must not be re-entered")
