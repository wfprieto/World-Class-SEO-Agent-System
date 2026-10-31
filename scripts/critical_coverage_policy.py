"""Immutable minimum per-file coverage floors, including relocated critical logic."""

from __future__ import annotations

MINIMUM_CRITICAL_COVERAGE: dict[str, float] = {
    "adapters/evidence_store.py": 67.0, "adapters/google_pagespeed_live.py": 83.0,
    "adapters/url_safety.py": 87.0, "integrations/authority_media/transport.py": 67.0,
    "integrations/google/client.py": 68.0, "integrations/google/gsc.py": 62.0,
    "integrations/technical/browser.py": 45.0, "integrations/technical/http.py": 72.0,
    "runtime/executor.py": 96.0, "runtime/llm.py": 64.0,
    "runtime/structured_output.py": 89.0, "runtime/tools.py": 83.0,
    "runtime/workflow_runner.py": 93.0,
    "security/url_safety.py": 84.0, "security/pinned_http.py": 95.0,
    "security/browser_proxy.py": 90.0, "security/browser_capture.py": 100.0,
    "adapters/evidence_identity.py": 67.0,
    "adapters/evidence_migrations.py": 67.0,
    "adapters/llm_transport.py": 64.0,
    "contracts/google.py": 68.0,
    "contracts/llm_transport.py": 64.0,
    "integrations/google/oauth.py": 68.0,
    "integrations/google/transport.py": 68.0,
    "integrations/google/gsc_results.py": 62.0,
    "seoctl/composition.py": 83.0,
}
