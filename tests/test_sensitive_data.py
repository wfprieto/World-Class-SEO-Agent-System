"""Fixed mutation catalog for canonical runtime redaction."""

from __future__ import annotations

import pytest

from adapters.evidence_store import EvidenceStore
from sensitive_data import redact


@pytest.mark.parametrize(
    "value,secret",
    [
        ("credential=tenant-specific-value", "tenant-specific-value"),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
        ("Set-Cookie: sid=private-cookie", "sid=private-cookie"),
        ("https://example.com/path?token=custom-token&safe=1", "custom-token"),
        ("failure for api key: custom-provider-key", "custom-provider-key"),
        ("Bearer opaque.provider.token", "opaque.provider.token"),
    ],
)
def test_embedded_labeled_credentials_are_redacted(value: str, secret: str) -> None:
    sanitized = redact(value)
    assert secret not in sanitized
    assert "[REDACTED]" in sanitized


def test_nested_sensitive_keys_and_safe_context_are_preserved() -> None:
    sanitized = redact(
        {
            "safe": "retain context",
            "nested": {"client-secret": "custom", "count": 2},
            "items": ["password=hunter2", "ordinary"],
        }
    )
    assert sanitized["safe"] == "retain context"
    assert sanitized["nested"] == {"client-secret": "[REDACTED]", "count": 2}
    assert sanitized["items"] == ["password=[REDACTED]", "ordinary"]


def test_evidence_store_never_persists_nested_or_embedded_credentials(tmp_path) -> None:
    db_path = tmp_path / "evidence.db"
    with EvidenceStore(db_path) as store:
        store.record(
            "https://example.com/",
            "security",
            {
                "safe": "keep",
                "nested": {"api_key": "custom-key"},
                "error": "credential=tenant-secret",
                "link": "https://example.com/?token=payload-secret",
            },
            scope={"authorization": "Bearer scope-secret"},
            source="credential=source-secret",
            run_id="token=run-secret",
        )
        record = store.latest("https://example.com/", "security")[0]
    raw = db_path.read_bytes()
    for secret in (
        b"custom-key",
        b"tenant-secret",
        b"payload-secret",
        b"scope-secret",
        b"source-secret",
        b"run-secret",
    ):
        assert secret not in raw
    assert record["payload"]["safe"] == "keep"
    assert record["payload"]["nested"]["api_key"] == "[REDACTED]"
