from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from adapters.base import AdapterResult
from seoctl import google_cli
from seoctl.cli import EXIT_OK, EXIT_UNAVAILABLE
from seoctl.entrypoint import HANDLERS
from seoctl.registry import command_specs

ROOT = Path(__file__).resolve().parents[1]


class FakeGSC:
    def query(self, **kwargs):
        return AdapterResult(
            source="google_search_console",
            status="ok",
            data={"totals_source": "dimensionless_aggregate_query", "kwargs": kwargs},
            warnings=[],
        )

    def inspect(self, **kwargs):
        return AdapterResult(
            source="google_search_console",
            status="ok",
            data={"inspection_scope": "google_index_version_only", "kwargs": kwargs},
            warnings=[],
        )


class FakeGA4:
    def fetch(self, **kwargs):
        return AdapterResult(
            source="google_analytics_data",
            status="ok",
            data={"totals_source": "ga4_metric_aggregation_total", "kwargs": kwargs},
            warnings=[],
        )


class FakePageSpeed:
    def fetch(self, **kwargs):
        return AdapterResult(
            source="google_pagespeed_live",
            status="ok",
            data={"performance_score": 95, "credential_transport": "X-Goog-Api-Key header"},
            warnings=[],
        )


class FakeCrUX:
    def fetch(self, **kwargs):
        return AdapterResult(
            source="google_crux_history",
            status="ok",
            data={
                "target": kwargs["target"],
                "target_type": kwargs["target_type"],
                "form_factor": "PHONE",
                "collection_period_count_returned": 25,
                "lcp_subparts": {"parts_complete": True},
                "limitations": [],
                "kwargs": kwargs,
            },
            warnings=[],
        )


def test_google_commands_route_to_real_connector_boundaries(monkeypatch):
    monkeypatch.setattr(google_cli, "GoogleSearchConsoleAdapter", FakeGSC)
    monkeypatch.setattr(google_cli, "GoogleAnalyticsDataAdapter", FakeGA4)
    monkeypatch.setattr(google_cli, "GooglePageSpeedLiveAdapter", FakePageSpeed)
    monkeypatch.setattr(google_cli, "CrUXHistoryAdapter", FakeCrUX)

    payload, code = google_cli.run([
        "gsc-query", "--site-url", "sc-domain:example.com",
        "--start-date", "2026-06-01", "--end-date", "2026-06-30",
        "--dimension", "query",
    ])
    assert code == EXIT_OK
    assert payload["data"]["totals_source"] == "dimensionless_aggregate_query"

    payload, code = google_cli.run([
        "gsc-inspect", "--url", "https://example.com/page",
        "--site-url", "sc-domain:example.com",
    ])
    assert code == EXIT_OK
    assert payload["data"]["inspection_scope"] == "google_index_version_only"

    payload, code = google_cli.run([
        "ga4-report", "--property-id", "123", "--metric", "sessions",
    ])
    assert code == EXIT_OK
    assert payload["data"]["totals_source"] == "ga4_metric_aggregation_total"

    payload, code = google_cli.run(["pagespeed", "--url", "https://example.com"])
    assert code == EXIT_OK
    assert payload["data"]["credential_transport"] == "X-Goog-Api-Key header"

    payload, code = google_cli.run(["crux-history", "--target", "https://example.com"])
    assert code == EXIT_OK
    assert payload["data"]["collection_period_count_returned"] == 25

    payload, code = google_cli.run(["lcp-subparts", "--target", "https://example.com"])
    assert code == EXIT_OK
    assert payload["data"]["lcp_subparts"]["parts_complete"] is True


def test_missing_live_credentials_return_unavailable_not_false_clean(monkeypatch):
    for key in ("GOOGLE_PAGESPEED_API_KEY", "GOOGLE_CRUX_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    payload, code = google_cli.run(["pagespeed", "--url", "https://example.com"])
    assert code == EXIT_UNAVAILABLE
    assert payload["status"] == "unavailable"
    assert payload["error"]["type"] == "AdapterNotConfigured"


def test_installed_module_exposes_google_help():
    completed = subprocess.run(
        [sys.executable, "-m", "seoctl", "google", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "gsc-query" in completed.stdout
    assert "ga4-report" in completed.stdout
    assert "crux-history" in completed.stdout


def test_every_registry_handler_resolves_across_command_families():
    for spec in command_specs():
        assert spec.handler in HANDLERS
        assert callable(HANDLERS[spec.handler])
