"""Security regressions for bounded imported evidence and derived diagnostics."""

from __future__ import annotations

import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from adapters import sitemap_validator
from integrations.product_proof import crawler, robots_policy
from scripts import consent_mode_diagnostic as consent
from scripts import serp_cluster, serp_input_bounds


def _consent_config(**updates):
    config = {
        "region": "US-CA",
        "mode": "advanced",
        "cmp": True,
        "default_set": True,
        "default_before_tags": True,
        "defaults": dict.fromkeys(consent.SIGNALS, "denied"),
    }
    config.update(updates)
    return config


def test_consent_sanitizes_selected_unselected_and_derived_overrides():
    result = consent.diagnose(_consent_config(region_overrides={
        "US": {"ad_storage": "granted", "email": "selected-secret"},
        "US-CA": {"ad_storage": "denied", "metadata": {"cookie": "nested-secret"}},
        "GB": {"analytics_storage": "denied", "user_id": "unselected-secret"},
        "resolved_defaults": {"email": "reserved-secret"},
    }))
    serialized = json.dumps(result)
    assert all(secret not in serialized for secret in (
        "selected-secret", "nested-secret", "unselected-secret", "reserved-secret",
    ))
    resolved = result["region_resolution"]
    assert resolved["requested_region"] == "US-CA"
    assert resolved["resolved_defaults"]["ad_storage"] == "denied"
    assert resolved["GB"] == {"analytics_storage": "denied"}


def test_sitemap_rejects_input_byte_limit_before_parsing(monkeypatch, tmp_path):
    monkeypatch.setattr(sitemap_validator, "MAX_SITEMAP_BYTES", 64, raising=False)
    text = "<urlset>" + (" " * 64) + "</urlset>"
    path = tmp_path / "oversized.xml"
    path.write_text(text, encoding="utf-8")
    for kwargs in ({"xml_text": text}, {"path": str(path)}):
        result = sitemap_validator.SitemapValidatorAdapter().fetch(**kwargs)
        assert result.status == "invalid"
        assert "limit" in result.data["error"].lower()
        assert result.source == (str(path) if "path" in kwargs else "xml_text")


def test_serp_cluster_rejects_excess_keywords(monkeypatch):
    monkeypatch.setattr(serp_input_bounds, "MAX_KEYWORDS", 2)
    with pytest.raises(ValueError, match="keyword.*limit"):
        serp_cluster.cluster({"a": [], "b": [], "c": []})


def test_serp_dense_graph_does_not_rescan_all_edges_per_keyword():
    class CountedKeyword(str):
        comparisons = 0
        __hash__ = str.__hash__

        def __eq__(self, other):
            CountedKeyword.comparisons += 1
            return super().__eq__(other)

    size = 60
    keywords = {CountedKeyword(f"k-{i:03}"): ["a", "b", "c", "d"] for i in range(size)}
    result = serp_cluster.cluster(keywords)
    assert len(result["edges"]) == size * (size - 1) // 2
    assert result["clusters"][0]["hub"] == "k-059"
    assert CountedKeyword.comparisons < 20 * size * size


def test_robots_adversarial_wildcards_finish_with_bounded_work():
    code = (
        "from integrations.product_proof.crawler import RobotsPolicy; "
        "policy=RobotsPolicy([{'user_agents':['*'], 'rules':"
        "[{'directive':'disallow','path':'/'+'*a'*30+'b$'}]}]); "
        "assert policy.allowed('https://example.com/'+'a'*80) is True"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=3,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("robots wildcard matching exceeded its bounded execution window")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(("pattern", "target", "blocked"), [
    ("/folder", "/folder/page", True), ("/folder$", "/folder/page", False),
    ("/folder$", "/folder", True), ("/a*b$", "/a12b", True),
    ("/a*b$", "/a12bc", False), ("/a**b", "/ab/c", True),
    ("/file?x=1$", "/file?x=1", True), ("/[a]+.txt", "/[a]+.txt", True),
    ("/[a]+.txt", "/aaa.txt", False), ("/a$b", "/a$b", True),
    ("", "/anything", False), ("*$", "/anything", True),
])
def test_robots_preserves_literal_wildcard_and_anchor_semantics(pattern, target, blocked):
    groups, _, _ = crawler.parse_robots(f"User-agent: *\nDisallow: {pattern}\n")
    assert crawler.RobotsPolicy(groups).allowed("https://example.com" + target) is not blocked


def test_robots_agent_specificity_and_allow_ties():
    groups, _, _ = crawler.parse_robots(
        "User-agent: *\nDisallow: /\nUser-agent: Googlebot\nDisallow: /private\n"
        "Allow: /private\nUser-agent: Googlebot-News\nDisallow: /news\n"
    )
    policy = crawler.RobotsPolicy(groups)
    assert policy.allowed("https://example.com/private", "Googlebot") is True
    assert policy.allowed("https://example.com/news", "Googlebot-News") is False
    assert policy.allowed("https://example.com/elsewhere", "Googlebot-News") is True
    assert policy.allowed("https://example.com/elsewhere", "OtherBot") is False


def test_robots_shared_work_budget_is_explicit_not_disallowed(monkeypatch):
    groups, _, _ = crawler.parse_robots("User-agent: *\nDisallow: /aaaaax\nDisallow: /aaaaay\n")
    monkeypatch.setattr(robots_policy, "MAX_ROBOTS_MATCH_WORK", 8)
    with pytest.raises(ValueError, match="work limit.*unknown"):
        crawler.RobotsPolicy(groups).allowed("https://example.com/aaaaaz")


def test_robots_input_bounds_and_missing_evidence(monkeypatch):
    monkeypatch.setattr(robots_policy, "MAX_ROBOTS_BYTES", 16)
    with pytest.raises(ValueError, match="byte limit.*unknown"):
        crawler.parse_robots("é" * 9)
    body = b"User-agent: *\nDisallow: /secret\n"

    class FixtureHttp:
        def get(self, url):
            return crawler.HttpHop(url, url, 200, {}, body, 0)

    record = crawler.SiteCrawler(http=FixtureHttp())._robots("https", "example.com")
    assert record.status_code == 0 and record.errors
    assert record.groups == []


def test_robots_group_path_and_target_bounds(monkeypatch):
    monkeypatch.setattr(robots_policy, "MAX_ROBOTS_RULES", 3)
    with pytest.raises(ValueError, match="rule/group limit.*unknown"):
        crawler.parse_robots("User-agent: *\nDisallow: /a\nDisallow: /b\n")
    monkeypatch.setattr(robots_policy, "MAX_ROBOTS_PATH_CHARACTERS", 4)
    with pytest.raises(ValueError, match="path limit.*unknown"):
        crawler.RobotsPolicy([{"user_agents": ["*"], "rules": [{"path": "/large"}]}])
    with pytest.raises(ValueError, match="limit.*unknown"):
        crawler.RobotsPolicy([]).allowed("https://example.com/large")


def test_sitemap_count_limit_and_namespace_duplicate_controls(monkeypatch):
    monkeypatch.setattr(sitemap_validator, "MAX_SITEMAP_LOCATIONS", 3)
    xml = '<urlset xmlns="urn:sitemaps"><loc>b</loc><loc>a</loc><loc>a</loc></urlset>'
    result = sitemap_validator.SitemapValidatorAdapter().fetch(xml_text=xml)
    assert result.status == "needs-review"
    assert result.data == {"url_count": 3, "duplicates": ["a"], "urls": ["b", "a", "a"]}
    result = sitemap_validator.SitemapValidatorAdapter().fetch(xml_text=xml.replace("</urlset>", "<loc>c</loc></urlset>"))
    assert result.status == "invalid" and "location limit" in result.data["error"].lower()
    assert "url_count" not in result.data


def test_sitemap_unicode_byte_ceiling_and_malformed_control(monkeypatch):
    xml = "<urlset><loc>é</loc></urlset>"
    monkeypatch.setattr(sitemap_validator, "MAX_SITEMAP_BYTES", len(xml))
    assert sitemap_validator.SitemapValidatorAdapter().fetch(xml_text=xml).status == "invalid"
    monkeypatch.setattr(sitemap_validator, "MAX_SITEMAP_BYTES", len(xml.encode("utf-8")))
    assert sitemap_validator.SitemapValidatorAdapter().fetch(xml_text=xml).status == "ok"
    assert sitemap_validator.SitemapValidatorAdapter().fetch(xml_text="<urlset>").status == "invalid"


def test_sitemap_retains_exact_large_duplicate_count_and_sample():
    rows = [f"https://example.com/{i}" for i in range(4000)] * 2
    xml = "<urlset>" + "".join(f"<loc>{url}</loc>" for url in rows) + "</urlset>"
    result = sitemap_validator.SitemapValidatorAdapter().fetch(xml_text=xml)
    assert result.data["url_count"] == 8000
    assert result.data["duplicates"] == sorted(set(rows))
    assert result.data["urls"] == rows[:100]


def test_serp_results_bytes_and_edges_are_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(serp_input_bounds, "MAX_RESULTS_PER_KEYWORD", 3)
    with pytest.raises(ValueError, match="results per keyword limit"):
        serp_cluster.cluster({"a": ["a", "b", "c", "d"]})
    monkeypatch.setattr(serp_input_bounds, "MAX_INPUT_BYTES", 20)
    with pytest.raises(ValueError, match="byte limit"):
        serp_cluster.cluster({"a": ["é" * 10]})
    path = tmp_path / "serps.json"
    path.write_text(" " * 21, encoding="utf-8")
    with pytest.raises(ValueError, match="byte limit"):
        serp_cluster.load_json(str(path))
    monkeypatch.setattr(serp_input_bounds, "MAX_INPUT_BYTES", 1000)
    monkeypatch.setattr(serp_input_bounds, "MAX_EDGES", 1)
    with pytest.raises(ValueError, match="edge count limit"):
        serp_cluster.cluster({"a": ["u", "v", "w"], "b": ["u", "v", "w"], "c": ["u", "v", "w"]})


def test_serp_threshold_volume_ties_and_boundary_inputs(monkeypatch):
    monkeypatch.setattr(serp_input_bounds, "MAX_KEYWORDS", 3)
    monkeypatch.setattr(serp_input_bounds, "MAX_RESULTS_PER_KEYWORD", 3)
    serps = {"c": ["u", "v", "w"], "b": ["u", "v", "w"], "a": None}
    result = serp_cluster.cluster(serps, volumes={"b": 10, "c": 20}, strong=9)
    assert result["clusters"][0]["hub"] == "c"
    assert result["clusters"][0]["hub_volume"] == 20
    assert result["edges"] == [{"a": "b", "b": "c", "shared": 3}]
    assert result == serp_cluster.cluster(dict(reversed(list(serps.items()))), {"c": 20, "b": 10}, strong=9)


@pytest.mark.parametrize("invalid", ["private-invalid-value", {"email": "private-invalid-value"}, ["private-invalid-value"], None])
def test_consent_invalid_signal_values_are_not_echoed_or_granted(invalid):
    result = consent.diagnose(_consent_config(
        defaults=dict.fromkeys(consent.SIGNALS, "granted"),
        region_overrides={"US-CA": {"ad_storage": invalid}},
    ))
    assert "private-invalid-value" not in json.dumps(result)
    assert result["consent_state_matrix"]["ad_storage"]["declared_default"] == "invalid"
    assert result["consent_state_matrix"]["ad_storage"]["treated_as"] == "denied"
    assert result["region_resolution"]["resolved_defaults"]["ad_storage"] == "denied"
    assert result["status"] != "PASS"


def test_consent_redacts_nested_aliases_in_every_returned_branch():
    secret = {"metadata": [{"ACCESS-TOKEN": "token-marker", "client-id": "client-marker"}]}
    result = consent.diagnose(_consent_config(environment=secret, extra=secret))
    assert "token-marker" not in json.dumps(result)
    assert "client-marker" not in json.dumps(result)
    assert result["implementation_topology"]["environment"]["metadata"][0]["ACCESS-TOKEN"] == "[REDACTED]"


@pytest.mark.parametrize("alias", [
    {"ad_storage": "aliased-sensitive-state"},
    [{"ad_storage": "aliased-sensitive-state"}],
    [{"consent_state_matrix": {"ad_storage": {"declared_default": "aliased-sensitive-state"}}}],
])
def test_consent_invalid_signal_alias_does_not_retain_raw_values(alias):
    result = consent.diagnose(_consent_config(defaults={"ad_storage": "aliased-sensitive-state"}, extra=alias))
    assert "aliased-sensitive-state" not in json.dumps(result)
    assert result["consent_state_matrix"]["ad_storage"]["treated_as"] == "denied"


def test_serp_standalone_script_keeps_its_cli_import_contract():
    result = subprocess.run(
        [sys.executable, "scripts/serp_cluster.py", "--help"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert "--strong" in result.stdout


def test_sitemap_file_read_stops_at_limit_plus_one(monkeypatch):
    class LimitedStream(BytesIO):
        requested = []

        def read(self, size=-1):
            self.requested.append(size)
            return super().read(size)

    stream = LimitedStream(b"x" * 100)
    monkeypatch.setattr(sitemap_validator, "MAX_SITEMAP_BYTES", 64)
    monkeypatch.setattr(sitemap_validator, "Path", lambda _: SimpleNamespace(open=lambda mode: stream))
    result = sitemap_validator.SitemapValidatorAdapter().fetch(path="oversized.xml")
    assert result.status == "invalid" and stream.requested == [65]


def test_consent_cli_envelope_cannot_reintroduce_sensitive_values(tmp_path):
    from seoctl.cli import run

    config = _consent_config(region_overrides={
        "US-CA": {"ad_storage": "cli-invalid-state", "access_token": "cli-sensitive-token"},
        "note": {"cookie": "cli-reserved-cookie"},
    })
    path = tmp_path / "consent.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    payload, exit_code = run(["privacy", "consent", "--config", str(path)])
    serialized = json.dumps(payload)
    assert exit_code == 0
    assert all(marker not in serialized for marker in ("cli-invalid-state", "cli-sensitive-token", "cli-reserved-cookie"))
    assert payload["data"]["region_resolution"]["requested_region"] == "US-CA"


@pytest.mark.parametrize("region", [{"email": "region-sensitive-marker"}, ["region-sensitive-marker"], "region-sensitive-marker"])
def test_consent_invalid_region_cannot_leak_through_stringified_metadata(region):
    result = consent.diagnose(_consent_config(region=region))
    assert "region-sensitive-marker" not in json.dumps(result).lower()
    assert result["region_resolution"]["requested_region"] == "unknown"
    assert result["implementation_topology"]["region"] == "unknown"
    assert result["status"] != "PASS"


@pytest.mark.parametrize("region", ["DE-private-region-marker", "GB-private-region-marker"])
def test_invalid_consent_required_region_cannot_leak_into_granted_findings(region, tmp_path):
    from seoctl.cli import run

    config = _consent_config(region=region, defaults=dict.fromkeys(consent.SIGNALS, "granted"))
    path = tmp_path / "region.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    report = consent.diagnose(config)
    envelope, exit_code = run(["privacy", "consent", "--config", str(path)])
    assert "private-region-marker" not in json.dumps([report, envelope]).lower()
    assert report["region_resolution"]["requested_region"] == "unknown"
    assert any(finding["area"] == "region" for finding in report["findings"])
    assert report["status"] == "FAIL"
    assert report["implementation_topology"]["consent_required_region"] is True
    assert all(row["treated_as"] == "denied" for row in report["consent_state_matrix"].values())
    assert exit_code == 5
