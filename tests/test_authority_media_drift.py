from __future__ import annotations

import json
from pathlib import Path

from integrations.authority_media.adapters import AuthorityMediaAdapter, DriftExecutionAdapter
from integrations.authority_media.services import (
    BacklinkProfileService,
    CommonCrawlService,
    DomainHistoryService,
    DriftService,
    IPTCLabelService,
    TranscriptService,
    YouTubeSearchService,
)
from integrations.authority_media.transport import BoundedTransport
from seoctl import authority_cli
from seoctl.cli import EXIT_BLOCKED, EXIT_OK, EXIT_UNAVAILABLE
from seoctl.entrypoint import HANDLERS
from seoctl.registry import command_specs, load_registry


def _write(path: Path, value, *, json_value: bool = True) -> str:
    if json_value:
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        path.write_text(str(value), encoding="utf-8")
    return str(path)


def test_transport_requires_exact_approved_https_host():
    transport = BoundedTransport({"index.commoncrawl.org"}, max_attempts=1)
    assert transport._validate_url("https://index.commoncrawl.org/collinfo.json").startswith("https://")
    for value in (
        "http://index.commoncrawl.org/collinfo.json",
        "https://evil.example/collinfo.json",
        "https://user:pass@index.commoncrawl.org/collinfo.json",
        "https://index.commoncrawl.org:444/collinfo.json",
    ):
        try:
            transport._validate_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe URL was accepted: {value}")


def test_commoncrawl_fixture_is_bounded_and_does_not_claim_backlink_coverage(tmp_path: Path):
    fixture = tmp_path / "cc.ndjson"
    fixture.write_text(
        "\n".join(
            [
                json.dumps({"url": "https://example.com/a", "timestamp": "20260101000000", "status": "200"}),
                json.dumps({"url": "https://example.com/b", "timestamp": "20260201000000", "status": "200"}),
                json.dumps({"url": "https://example.com/a", "timestamp": "20260301000000", "status": "200"}),
            ]
        ),
        encoding="utf-8",
    )
    result = CommonCrawlService().search("example.com", fixture_path=str(fixture), page_size=10)
    assert result.status == "ok"
    assert result.data["record_count"] == 2
    assert result.data["coverage"] == "bounded_url_index_sample"
    assert any("not a complete backlink graph" in warning for warning in result.warnings)


def test_backlink_profile_and_gap_normalize_supplied_exports(tmp_path: Path):
    target = tmp_path / "target.csv"
    target.write_text(
        "referring_page,target_url,anchor,rel\n"
        "https://a.example/page,https://target.example/,Brand,nofollow\n",
        encoding="utf-8",
    )
    competitor = tmp_path / "competitor.csv"
    competitor.write_text(
        "source_url,destination_url,anchor_text,link_rel\n"
        "https://a.example/page,https://competitor.example/,Brand,nofollow\n"
        "https://b.example/post,https://competitor.example/,Guide,dofollow\n",
        encoding="utf-8",
    )
    service = BacklinkProfileService()
    profile = service.profile(str(competitor))
    assert profile.data["backlink_count"] == 2
    assert profile.data["referring_domain_count"] == 2
    assert profile.data["quality_score"] is None
    gap = service.gap(str(target), str(competitor))
    assert gap.data["gap_count"] == 1
    assert gap.data["gaps"][0]["referring_domain"] == "b.example"


def test_domain_history_fixture_preserves_public_evidence_without_contact_pii(tmp_path: Path):
    fixture = _write(
        tmp_path / "rdap.json",
        {
            "ldhName": "EXAMPLE.COM",
            "status": ["client transfer prohibited"],
            "events": [
                {"eventAction": "registration", "eventDate": "1995-08-14T04:00:00Z"},
                {"eventAction": "last update of RDAP database", "eventDate": "2026-07-01T00:00:00Z"},
            ],
            "entities": [
                {
                    "handle": "376",
                    "roles": ["registrar"],
                    "publicIds": [{"type": "IANA Registrar ID", "identifier": "376"}],
                    "vcardArray": ["vcard", [["email", {}, "text", "private@example.com"]]],
                }
            ],
            "nameservers": [{"ldhName": "A.IANA-SERVERS.NET"}],
            "secureDNS": {"delegationSigned": True},
            "rdapConformance": ["rdap_level_0"],
        },
    )
    result = DomainHistoryService().history("example.com", fixture_path=fixture)
    serialized = json.dumps(result.data)
    assert result.status == "ok"
    assert result.data["ownership_inference"] is None
    assert "private@example.com" not in serialized
    assert result.data["events"]["registration"] == ["1995-08-14T04:00:00Z"]


def test_youtube_fixture_and_missing_key_states_are_truthful(tmp_path: Path):
    missing = YouTubeSearchService(api_key="").search("technical seo")
    assert missing.status == "not_configured"
    fixture = _write(
        tmp_path / "youtube.json",
        {
            "regionCode": "US",
            "pageInfo": {"totalResults": 999999, "resultsPerPage": 1},
            "items": [
                {
                    "id": {"videoId": "abc123"},
                    "snippet": {
                        "title": "SEO Video",
                        "description": "Description",
                        "channelId": "channel",
                        "channelTitle": "Channel",
                        "publishedAt": "2026-07-01T00:00:00Z",
                    },
                }
            ],
        },
    )
    result = YouTubeSearchService(api_key="").search("technical seo", fixture_path=fixture)
    assert result.status == "ok"
    assert result.data["result_count"] == 1
    assert result.data["provider_total_results_approximate"] == 999999
    assert result.data["quota_units_estimated"] == 0


def test_iptc_sidecar_requires_explicit_authorization_and_rejects_retired_terms(tmp_path: Path):
    metadata = _write(tmp_path / "metadata.json", {"digital_source_type": "digsrctype:digitalArt"})
    invalid = IPTCLabelService().inspect(metadata)
    assert invalid.status == "invalid_response"
    assert invalid.data["retired"]

    clean = _write(tmp_path / "clean.json", {"title": "Asset"})
    blocked = IPTCLabelService().inspect(
        clean,
        label="trainedAlgorithmicMedia",
        write=True,
        output_path=str(tmp_path / "sidecar.json"),
    )
    assert blocked.status == "blocked"
    output = tmp_path / "sidecar.json"
    written = IPTCLabelService().inspect(
        clean,
        label="trainedAlgorithmicMedia",
        write=True,
        authorize_write=True,
        output_path=str(output),
    )
    assert written.status == "ok"
    assert json.loads(output.read_text(encoding="utf-8"))["digital_source_type"].endswith("trainedAlgorithmicMedia")
    assert written.data["source_mutated"] is False


def test_transcript_check_is_structural_not_semantic(tmp_path: Path):
    transcript = _write(
        tmp_path / "captions.vtt",
        "WEBVTT\n\n00:00:00.000 --> 00:00:04.000\nWelcome to the technical SEO guide.\n",
        json_value=False,
    )
    result = TranscriptService().check(transcript, video_id="abc123")
    assert result.status == "ok"
    assert result.data["timestamp_evidence"] is True
    assert result.data["semantic_accuracy_verified"] is False


def test_drift_command_family_uses_one_evidence_store(tmp_path: Path):
    db = str(tmp_path / "evidence.db")
    first = _write(
        tmp_path / "first.json",
        {"title": "Before", "canonical": "https://example.com/", "status_code": 200, "html": "before"},
    )
    second = _write(
        tmp_path / "second.json",
        {"title": "After", "canonical": "https://example.com/new", "status_code": 200, "html": "after"},
    )
    service = DriftService()
    baseline = service.baseline("https://example.com/", first, db_path=db)
    assert baseline.status == "ok"
    watched = service.watch("https://example.com/", second, db_path=db)
    assert watched.status == "ok"
    assert watched.data["counts"]["critical"] == 1
    history = service.history("https://example.com/", db_path=db)
    assert history.data["count"] == 2
    report_path = tmp_path / "report.json"
    report = service.report("https://example.com/", db_path=db, output_path=str(report_path))
    assert report_path.is_file()
    assert report.data["report_path"] == str(report_path)


def test_cli_registry_handlers_and_fixture_commands(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    registry = load_registry()
    ids = {spec.id for spec in command_specs(registry)}
    expected = {
        "links.commoncrawl", "links.profile", "links.gap", "domain.history",
        "media.youtube-search", "media.iptc-label", "media.transcript-check",
        "drift.baseline", "drift.compare", "drift.history", "drift.report", "drift.watch",
    }
    assert expected <= ids
    assert expected <= {
        "links.commoncrawl" if "links_commoncrawl" in HANDLERS else "",
        "links.profile" if "links_profile" in HANDLERS else "",
        "links.gap" if "links_gap" in HANDLERS else "",
        "domain.history" if "domain_history" in HANDLERS else "",
        "media.youtube-search" if "media_youtube_search" in HANDLERS else "",
        "media.iptc-label" if "media_iptc_label" in HANDLERS else "",
        "media.transcript-check" if "media_transcript_check" in HANDLERS else "",
        "drift.baseline" if "drift_baseline" in HANDLERS else "",
        "drift.compare" if "drift_compare" in HANDLERS else "",
        "drift.history" if "drift_history" in HANDLERS else "",
        "drift.report" if "drift_report" in HANDLERS else "",
        "drift.watch" if "drift_watch" in HANDLERS else "",
    }

    youtube = _write(tmp_path / "youtube.json", {"items": []})
    payload, code = authority_cli.run(["media", "youtube-search", "--query", "seo", "--fixture", youtube])
    assert code == EXIT_OK
    assert payload["command"] == "media.youtube-search"

    metadata = _write(tmp_path / "metadata.json", {})
    payload, code = authority_cli.run([
        "media", "iptc-label", "--input", metadata, "--label", "trainedAlgorithmicMedia",
        "--write", "--output", str(tmp_path / "sidecar.json"),
    ])
    assert code == EXIT_BLOCKED

    payload, code = authority_cli.run(["media", "youtube-search", "--query", "seo"])
    assert code == EXIT_UNAVAILABLE


def test_runtime_adapters_expose_canonical_operations(tmp_path: Path):
    fixture = tmp_path / "cc.ndjson"
    fixture.write_text(json.dumps({"url": "https://example.com/", "status": "200"}), encoding="utf-8")
    result = AuthorityMediaAdapter().fetch(
        operation="commoncrawl",
        domain="example.com",
        fixture_path=str(fixture),
    )
    assert result.status == "ok"
    assert isinstance(DriftExecutionAdapter().service, DriftService)
