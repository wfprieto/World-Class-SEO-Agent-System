"""Batch 3 tactical capability tests (test-first).

Covers: Desktop Commander governance boundaries, content-brief website-relevance
gate and SERP competitor evidence, six vertical profiles, agent-friendly-pages
reference, and the DMA / Consent Mode v2 diagnostic.

Fixtures and static governance only. No network, no paid providers, no live tags,
no production credentials, no consent writes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import consent_mode_diagnostic as cmd  # noqa: E402
import content_brief_evidence as cbe  # noqa: E402
import vertical_profiles as vp  # noqa: E402


# ===================== Scope 1: Desktop Commander governance =====================

def test_desktop_commander_skill_registered_once():
    index = (ROOT / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
    assert index.count("`desktop-commander-execution`") == 1
    procs = (ROOT / "skills" / "deep-skill-procedures.md").read_text(encoding="utf-8")
    assert "## desktop-commander-execution" in procs


def test_desktop_commander_skill_defines_permission_tiers():
    doc = (ROOT / "skills" / "local-execution-skills.md").read_text(encoding="utf-8")
    for tier in ("Allowed without additional approval", "Requires explicit human approval",
                 "Always prohibited"):
        assert tier in doc
    # Approval-gated operations must be named explicitly.
    for gated in ("commit", "push", "pull request", "merge", "deploy", "publish",
                  "paid API", "production credentials"):
        assert gated in doc
    # Must not claim command success equals SEO/business success.
    assert "command completion" in doc.lower()


def test_desktop_commander_does_not_register_individual_functions_as_skills():
    index = (ROOT / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
    for leaked in ("`read-file`", "`write-file`", "`start-process`", "`list-directory`"):
        assert leaked not in index


# ===================== Scope 2: content-brief relevance + SERP =====================

SITE = {
    "purpose": "Buffalo-based commercial HVAC installation and service",
    "audience": "facility managers in Western New York",
    "offerings": ["commercial HVAC install", "preventive maintenance", "emergency repair"],
    "markets": ["US-NY"],
    "expertise": ["licensed HVAC engineers", "20 years field service"],
    "existing_topics": ["hvac maintenance", "rooftop units", "energy efficiency"],
}


def test_relevance_gate_accepts_on_topic_page():
    r = cbe.assess_relevance(SITE, topic="rooftop HVAC preventive maintenance checklist",
                             market="US-NY")
    assert r["verdict"] == "RELEVANT"
    assert r["evidence"]


def test_relevance_gate_rejects_unrelated_high_volume_topic():
    """Search volume must never green-light an unrelated topic."""
    r = cbe.assess_relevance(SITE, topic="best crypto exchanges 2026", market="US-NY",
                             search_volume=250_000)
    assert r["verdict"] == "NOT_RELEVANT"
    assert "volume" not in " ".join(r["reasons"]).lower() or r["verdict"] == "NOT_RELEVANT"


def test_relevance_gate_returns_insufficient_evidence_when_site_unknown():
    r = cbe.assess_relevance({}, topic="anything", market="US")
    assert r["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_relevance_gate_handles_hybrid_business():
    hybrid = dict(SITE, offerings=SITE["offerings"] + ["online HVAC parts store"])
    r = cbe.assess_relevance(hybrid, topic="replacement HVAC air filter sizes", market="US-NY")
    assert r["verdict"] in {"RELEVANT", "CONDITIONALLY_RELEVANT"}


def test_relevance_gate_conditional_when_market_mismatch():
    r = cbe.assess_relevance(SITE, topic="commercial HVAC maintenance", market="DE")
    assert r["verdict"] == "CONDITIONALLY_RELEVANT"


def test_relevance_verdicts_are_not_google_ranking_factors():
    doc = (ROOT / "skills" / "content-ia-skills.md").read_text(encoding="utf-8")
    assert "not a Google ranking factor" in doc


# --- SERP competitor assessment ---

SERP = [
    {"url": "https://a.example/guide", "position": 1, "page_type": "guide",
     "intent": "informational", "first_hand_evidence": True, "sources_cited": True,
     "last_updated": "2026-06-01", "entities": ["rooftop unit", "filter"]},
    {"url": "https://b.example/blog", "position": 2, "page_type": "blog",
     "intent": "informational", "first_hand_evidence": False, "sources_cited": False,
     "last_updated": "2021-01-01", "entities": ["hvac"]},
    {"url": "https://a.example/guide", "position": 7, "page_type": "guide",
     "intent": "informational", "first_hand_evidence": True, "sources_cited": True,
     "last_updated": "2026-06-01", "entities": ["rooftop unit"]},  # duplicate URL
]
CAPTURE = {"query": "rooftop hvac maintenance checklist", "locale": "en-US",
           "device": "mobile", "date": "2026-07-11", "source": "supplied-export"}


def test_serp_assessment_requires_capture_metadata():
    with pytest.raises(ValueError, match="query|locale|device|date|source"):
        cbe.assess_serp(SERP, capture={"query": "x"}, own_domain="ours.example")


def test_serp_assessment_records_capture_and_dedupes_results():
    r = cbe.assess_serp(SERP, capture=CAPTURE, own_domain="ours.example")
    assert r["capture"] == CAPTURE
    assert r["result_count"] == 2  # duplicate URL collapsed
    assert r["duplicates_removed"] == 1


def test_serp_assessment_distinguishes_serp_from_domain_competitors():
    r = cbe.assess_serp(SERP, capture=CAPTURE, own_domain="ours.example",
                        known_domain_competitors=["b.example"])
    kinds = {c["url"]: c["competitor_kind"] for c in r["competitors"]}
    assert kinds["https://b.example/blog"] == "domain_and_serp"
    assert kinds["https://a.example/guide"] == "serp_only"


def test_serp_assessment_fabricates_no_metrics():
    r = cbe.assess_serp(SERP, capture=CAPTURE, own_domain="ours.example")
    blob = str(r).lower()
    for fabricated in ("traffic", "backlinks", "domain_authority", "cpc", "search_volume"):
        assert fabricated not in blob


def test_serp_score_is_labeled_a_configurable_kit_heuristic():
    r = cbe.assess_serp(SERP, capture=CAPTURE, own_domain="ours.example")
    assert r["score_basis"] == "kit_heuristic"
    assert "not a Google score" in r["disclaimer"]
    assert r["weights_configurable"] is True


def test_serp_assessment_reports_unavailable_evidence():
    r = cbe.assess_serp([], capture=CAPTURE, own_domain="ours.example")
    assert r["status"] == "INSUFFICIENT_EVIDENCE"
    assert r["competitors"] == []


def test_brief_blocked_without_distinct_information_gain():
    decision = cbe.brief_decision(
        relevance={"verdict": "RELEVANT"},
        serp={"status": "OK"},
        information_gain=[],
    )
    assert decision["publish"] is False
    assert "information gain" in decision["reason"].lower()


def test_brief_allowed_with_relevance_and_information_gain():
    decision = cbe.brief_decision(
        relevance={"verdict": "RELEVANT"},
        serp={"status": "OK"},
        information_gain=["original field data from 40 rooftop installs"],
    )
    assert decision["publish"] is True


# ===================== Scope 3: six vertical profiles =====================

EXPECTED = {"generic", "ecommerce", "local-service", "saas", "publisher", "agency"}


def test_all_six_vertical_profiles_exist():
    assert set(vp.PROFILES) == EXPECTED
    doc = (ROOT / "knowledge" / "seo-vertical-profiles.md").read_text(encoding="utf-8")
    for name in EXPECTED:
        assert name in doc


def test_each_profile_defines_required_sections():
    required = ("detection_signals", "required_agents", "required_skills", "default_modules",
                "excluded_modules", "evidence_requirements", "technical_priorities",
                "conversion_model", "schema", "geo_aio", "measurement", "risks",
                "handoffs", "outputs", "stop_conditions")
    for name, profile in vp.PROFILES.items():
        for key in required:
            assert key in profile, f"{name} missing {key}"


def test_low_confidence_detection_does_not_silently_route():
    r = vp.route({"signals": []})
    assert r["route"] == "UNCONFIRMED"
    assert r["confidence"] == "low"
    assert r["action"] == "ask_or_stop"


def test_hybrid_business_declares_hybrid_route():
    r = vp.route({"signals": ["cart", "checkout", "product_schema",
                              "nap_block", "store_locator", "local_business_schema"]})
    assert r["route"] == "HYBRID"
    assert set(r["profiles"]) == {"ecommerce", "local-service"}
    assert r["declared"] is True


def test_single_strong_signal_set_routes_to_one_profile():
    r = vp.route({"signals": ["cart", "checkout", "product_schema"]})
    assert r["route"] == "SINGLE"
    assert r["profiles"] == ["ecommerce"]


def test_false_positive_signal_does_not_route():
    """A lone weak signal must not classify the site."""
    r = vp.route({"signals": ["blog"]})
    assert r["route"] in {"UNCONFIRMED", "SINGLE"}
    if r["route"] == "UNCONFIRMED":
        assert r["action"] == "ask_or_stop"


def test_profiles_reference_canonical_detection_authority_not_a_second_router():
    doc = (ROOT / "knowledge" / "seo-vertical-profiles.md").read_text(encoding="utf-8")
    assert "docs/plugin-packaging.md" in doc
    assert "second router" in doc.lower() or "single detection authority" in doc.lower()


def test_profile_agent_and_skill_references_are_canonical():
    index = (ROOT / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
    agents = (ROOT / "agents" / "AGENT_INDEX.md").read_text(encoding="utf-8")
    for name, profile in vp.PROFILES.items():
        for skill in profile["required_skills"]:
            assert f"`{skill}`" in index, f"{name}: skill {skill} not in SKILL_INDEX"
        for agent in profile["required_agents"]:
            assert agent in agents, f"{name}: agent {agent} not in AGENT_INDEX"


# ===================== Scope 4: agent-friendly pages =====================

AFP = None


def _afp() -> str:
    global AFP
    if AFP is None:
        AFP = (ROOT / "knowledge" / "agent-friendly-pages.md").read_text(encoding="utf-8")
    return AFP


def _plain(text: str) -> str:
    """Strip markdown emphasis so assertions test the claim, not the formatting."""
    return text.replace("*", "").replace("`", "").lower()


def test_agent_friendly_reference_makes_no_prohibited_claims():
    text = _plain(_afp())
    # The document must NOT assert these; it must explicitly deny them.
    assert "llms.txt is not required" in text
    assert "does not guarantee citation" in text
    assert "no special ai-only markup" in text
    # Must reject the agent-only page pattern outright.
    assert "separate agent-only page must not replace" in text
    # And must never make the affirmative claims.
    assert "llms.txt is required" not in text
    assert "chunking guarantees" not in text


def test_agent_friendly_reference_states_crawler_access_is_not_inclusion():
    text = _afp()
    assert "does not guarantee" in text.lower()


def test_agent_friendly_reference_dates_time_sensitive_crawler_rules():
    text = _afp()
    assert "2026" in text                      # crawler rules carry a check date
    assert "Google-Extended" in text
    assert "robots.txt token" in text          # not a real user-agent in logs
    assert "OAI-SearchBot" in text and "Claude-SearchBot" in text


def test_agent_friendly_reference_cross_references_rather_than_duplicating():
    text = _afp()
    assert "geo-readiness-rubric.md" in text
    assert "rendered-visual-audit" in text


def test_agent_friendly_reference_is_evidence_labeled():
    text = _afp()
    assert "FACT" in text and ("ANALYSIS" in text or "VERIFY" in text)


# ===================== Scope 5: DMA / Consent Mode v2 diagnostic =====================

def _cfg(**kw):
    base = {
        "region": "EEA", "cmp": "acme-cmp", "mode": "advanced",
        "default_set": True, "default_before_tags": True,
        "defaults": {"ad_storage": "denied", "analytics_storage": "denied",
                     "ad_user_data": "denied", "ad_personalization": "denied"},
        "update_present": True, "update_after_default": True,
        "wait_for_update_ms": 500, "duplicate_tags": False, "spa": False,
        "environment": "production",
    }
    base.update(kw)
    return base


def test_valid_default_denied_then_update_passes():
    r = cmd.diagnose(_cfg())
    assert r["status"] in {"PASS", "PARTIAL"}
    assert not [f for f in r["findings"] if f["severity"] == "critical"]


def test_update_before_default_is_critical():
    r = cmd.diagnose(_cfg(update_after_default=False))
    assert r["status"] == "FAIL"
    assert any("before" in f["finding"].lower() for f in r["findings"])


def test_missing_ad_user_data_is_critical():
    d = _cfg()
    del d["defaults"]["ad_user_data"]
    r = cmd.diagnose(d)
    assert r["status"] == "FAIL"
    assert any("ad_user_data" in f["finding"] for f in r["findings"])


def test_missing_ad_personalization_is_critical():
    d = _cfg()
    del d["defaults"]["ad_personalization"]
    r = cmd.diagnose(d)
    assert any("ad_personalization" in f["finding"] for f in r["findings"])


def test_default_granted_in_eea_is_flagged_and_never_auto_granted():
    r = cmd.diagnose(_cfg(defaults={"ad_storage": "granted", "analytics_storage": "granted",
                                    "ad_user_data": "granted", "ad_personalization": "granted"}))
    assert r["status"] == "FAIL"
    assert any("denied" in f["technical_correction"].lower() for f in r["findings"])
    # The diagnostic must never propose granting consent on the user's behalf.
    assert "grant consent" not in str(r).lower()


def test_missing_cmp_is_blocked_not_passed():
    r = cmd.diagnose(_cfg(cmp=None))
    assert r["status"] in {"FAIL", "BLOCKED"}


def test_unknown_and_stale_states_are_not_treated_as_granted():
    r = cmd.diagnose(_cfg(defaults={"ad_storage": "unknown", "analytics_storage": "denied",
                                    "ad_user_data": "denied", "ad_personalization": "denied"}))
    assert any("unknown" in f["finding"].lower() for f in r["findings"])
    matrix = r["consent_state_matrix"]
    assert matrix["ad_storage"]["treated_as"] == "denied"


def test_duplicate_initialization_flagged():
    r = cmd.diagnose(_cfg(duplicate_tags=True))
    assert any("duplicate" in f["finding"].lower() for f in r["findings"])


def test_spa_navigation_flagged():
    r = cmd.diagnose(_cfg(spa=True))
    assert any("spa" in f["finding"].lower() or "route" in f["finding"].lower()
               for f in r["findings"])


def test_region_specific_default_more_specific_wins():
    r = cmd.diagnose(_cfg(region="US", region_overrides={"US-CA": {"ad_storage": "denied"}}))
    assert r["region_resolution"]["US-CA"]["ad_storage"] == "denied"
    assert "more specific" in r["region_resolution"]["note"].lower()


def test_basic_and_advanced_modes_are_distinguished():
    basic = cmd.diagnose(_cfg(mode="basic"))
    adv = cmd.diagnose(_cfg(mode="advanced"))
    assert basic["mode_behavior"] != adv["mode_behavior"]
    assert "modeled" in str(basic["mode_behavior"]).lower()


def test_preview_vs_production_mismatch_flagged():
    r = cmd.diagnose(_cfg(environment="preview", production_config_differs=True))
    assert any("preview" in f["finding"].lower() or "production" in f["finding"].lower()
               for f in r["findings"])


def test_diagnostic_never_claims_legal_compliance():
    r = cmd.diagnose(_cfg())
    assert r["legal_review_required"] is True
    blob = str(r).lower()
    assert "compliant with the dma" not in blob
    assert "legally compliant" not in blob
    assert "qualified counsel" in blob


def test_diagnostic_exposes_no_consent_strings_or_identifiers():
    r = cmd.diagnose(_cfg(tc_string="CPxyz-consent-string", user_id="u-123"))
    blob = str(r)
    assert "CPxyz-consent-string" not in blob
    assert "u-123" not in blob


def test_diagnostic_makes_no_network_calls_and_no_tag_writes():
    src = (ROOT / "scripts" / "consent_mode_diagnostic.py").read_text(encoding="utf-8")
    for banned in ("requests", "urlopen", "httpx", "socket", "subprocess", "gtag("):
        assert banned not in src


def test_consent_skill_registered_once_with_deep_procedure():
    index = (ROOT / "skills" / "SKILL_INDEX.md").read_text(encoding="utf-8")
    assert index.count("`consent-mode-diagnostic`") == 1
    procs = (ROOT / "skills" / "deep-skill-procedures.md").read_text(encoding="utf-8")
    assert "## consent-mode-diagnostic" in procs


# ===================== Source-of-truth drift =====================

def test_integration_manifest_no_longer_claims_batch2_is_unreleased():
    text = (ROOT / "docs" / "INTEGRATION-MANIFEST.md").read_text(encoding="utf-8")
    assert "staged, not released" not in text
    assert "1.6.0" in text  # reconciled to the real changelog state


# ============== Artifact review gate: hardened behaviours ==============

def test_dc_skill_hardens_containment_injection_and_approval_expiry():
    doc = (ROOT / "skills" / "local-execution-skills.md").read_text(encoding="utf-8")
    for control in (
        "Resolve symlinks before the check",   # symlink escape
        "..",                                   # traversal
        "Pass arguments as a list",             # command injection
        "single-use",                           # approval expiry
        "Whoever created a worktree",           # cleanup ownership
        "case-insensitive path comparison",     # cross-platform
        ".env",                                 # secret paths
        "git push --force",                     # destructive boundary
    ):
        assert control in doc, f"DC skill missing control: {control}"


def test_dc_skill_makes_git_writes_approval_gated_but_reads_allowed():
    doc = (ROOT / "skills" / "local-execution-skills.md").read_text(encoding="utf-8")
    assert "Reading (`status`, `diff`, `log`" in doc
    assert "approval-gated" in doc


def test_serp_evidence_flags_stale_capture():
    old = dict(CAPTURE, date="2026-01-01")
    r = cbe.assess_serp(SERP, capture=old, own_domain="ours.example", as_of="2026-07-11")
    assert r["stale"] is True
    assert r["status"] == "STALE_EVIDENCE"


def test_serp_evidence_fresh_capture_is_not_stale():
    r = cbe.assess_serp(SERP, capture=CAPTURE, own_domain="ours.example", as_of="2026-07-11")
    assert r["stale"] is False and r["status"] == "OK"


def test_inaccessible_competitor_is_disclosed_not_silently_dropped():
    rows = SERP + [{"url": "https://blocked.example/x", "position": 3,
                    "fetch_error": "403 blocked"}]
    r = cbe.assess_serp(rows, capture=CAPTURE, own_domain="ours.example", as_of="2026-07-11")
    assert r["inaccessible"], "inaccessible result must be disclosed"
    assert r["inaccessible"][0]["evidence_state"] == "Not Run"
    # It must not be scored as if it had been read.
    assert all(c["url"] != "https://blocked.example/x" for c in r["competitors"])


def test_mixed_intent_serp_is_flagged_and_not_averaged():
    rows = [
        dict(SERP[0], url="https://x.example/1", intent="informational"),
        dict(SERP[0], url="https://y.example/2", intent="transactional"),
    ]
    r = cbe.assess_serp(rows, capture=CAPTURE, own_domain="ours.example", as_of="2026-07-11")
    assert r["mixed_intent"] is True
    assert "more than one intent" in r["intent_note"]


def test_consent_live_test_without_authorization_is_blocked():
    r = cmd.diagnose(_cfg(live_test_requested=True))
    assert r["status"] == "BLOCKED"
    assert "authoris" in r["reason"].lower() or "authoriz" in r["reason"].lower()
    assert r["evidence_inventory"]["live_verification"].startswith("Blocked")


def test_consent_server_side_tagging_flagged():
    r = cmd.diagnose(_cfg(server_side_tagging=True))
    assert any(f["area"] == "server-side" for f in r["findings"])


def test_consent_cross_domain_flagged():
    r = cmd.diagnose(_cfg(cross_domain=True))
    assert any(f["area"] == "cross-domain" for f in r["findings"])
