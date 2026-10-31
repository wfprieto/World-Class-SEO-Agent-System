"""Offline wiring tests; crypto stand-ins are NOT real execution authority."""

import hashlib
import io
import json
import zipfile
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_publication_evidence import NOW, evidence_package

from adapters.mcp_extensions import REGISTRY
from scripts import publication_authorize as authorize
from scripts import publication_policy as policy
from scripts.publication_evidence import checked_evidence, execution_seal
from scripts.publication_prerequisites import job_claims

PRODUCER_SOURCE = "c" * 40


def checked_claims(data: dict, records: dict, subject: dict, digest: str) -> list[dict]:
    """COUNTERFACTUAL source grammar only, never enabled in the real publisher."""
    with pytest.MonkeyPatch.context() as scoped:
        scoped.setitem(REGISTRY, "bing-webmaster", replace(REGISTRY["bing-webmaster"], live_state="CONFIGURABLE"))
        _data, reader = checked_evidence(json.dumps(data).encode(), records, subject,
                                          subject_sha256=digest, now=NOW)
        return job_claims(data["live"], reader)


def zipped(raw: bytes) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("result.json", raw)
    return output.getvalue()


class Producer:
    def __init__(self, gate: str, pointer: dict) -> None:
        self.gate = gate
        self.repository = "enrolled/" + gate
        independent = gate == "external_reproduction"
        context = {"repository_id": 987 if independent else 445, "owner_id": 876 if independent else 345,
                   "actor_id": 765 if independent else 245, "run_id": pointer["run_id"], "run_attempt": 1}
        self.context = context
        self.receipt = {"run": {"id": pointer["run_id"], "run_attempt": 1, "head_sha": PRODUCER_SOURCE,
            "repository": {"id": context["repository_id"], "full_name": self.repository,
                           "owner": {"id": context["owner_id"]}}, "actor": {"id": context["actor_id"]}}}
        self.rows = [{"id": identity, "run_id": pointer["run_id"], "head_sha": PRODUCER_SOURCE,
            "status": "completed", "conclusion": "success", "labels": [platform + "-latest"],
            "started_at": "2026-10-31T01:54:00Z", "completed_at": "2026-10-31T02:01:00Z"}
            for identity, platform in ((123, "ubuntu"), (456, "windows"))]
        self.archive = b""
        self.reads: list[str] = []

    def json(self, endpoint: str) -> object:
        assert self.gate == "live_authorized_smokes", "Non-live role unexpectedly read live jobs"
        expected = f"/repos/{self.repository}/actions/runs/41/attempts/1/jobs?per_page=100&page=1"
        assert endpoint == expected
        self.reads.append(endpoint)
        return {"total_count": len(self.rows), "jobs": self.rows}

    def binary(self, endpoint: str, limit: int) -> bytes:
        assert endpoint == f"/repos/{self.repository}/actions/artifacts/100/zip"
        assert limit == policy.MAX_ARCHIVE_BYTES
        return self.archive

    def graphql(self, *_args: object) -> object:
        pytest.fail("This wiring path has no GraphQL operation")


class Primary:
    def __init__(self, clients: dict[str, Producer]) -> None:
        self.clients = clients
        self.selected: list[str] = []

    def for_execution(self, gate: str, repository: str) -> Producer:
        assert self.clients[gate].repository == repository
        self.selected.append(gate)
        return self.clients[gate]

    def json(self, *_args: object) -> object:
        pytest.fail("Primary credential was used for a producer read")

    def binary(self, *_args: object) -> bytes:
        pytest.fail("Primary credential was used for a producer download")


def unit_inputs(monkeypatch: pytest.MonkeyPatch, *, bad_seal: bool = False):
    data, records, subject, digest = evidence_package()
    claims = checked_claims(data, records, subject, digest)
    clients, authorities = {}, {}
    for gate in sorted(policy.EXECUTION_GATES):
        pointer = data["executions"][gate]
        client = Producer(gate, pointer)
        seal = execution_seal(data, records, gate=gate, execution_context=client.context)
        if bad_seal and gate == "live_authorized_smokes":
            seal["execution_context"]["run_attempt"] = True
        raw = json.dumps(seal).encode()
        client.archive = zipped(raw)
        pointer["member_sha256"] = hashlib.sha256(raw).hexdigest()
        pointer["artifact_sha256"] = hashlib.sha256(client.archive).hexdigest()
        clients[gate] = client
        authorities[gate] = [{"repository": client.repository, "workflow": ".github/workflows/actual-producer.yml",
                              "source_commit": PRODUCER_SOURCE, "source_ref": "refs/heads/main"}]
    verified = []

    def fake_execution(client, **_kwargs):
        return client.receipt

    def fake_crypto(client, raw, **kwargs):
        assert kwargs["repository"] == client.repository
        assert kwargs["source_commit"] == PRODUCER_SOURCE
        assert json.loads(raw)["gate"] == client.gate
        verified.append(client.gate)

    monkeypatch.setattr(authorize, "authenticate_execution", fake_execution)
    monkeypatch.setattr(authorize, "verify_bytes", fake_crypto)
    return data, records, SimpleNamespace(subject=subject), authorities, Primary(clients), claims, verified


def test_selected_role_clients_reach_real_job_binding_after_explicit_unit_crypto_standins(monkeypatch: pytest.MonkeyPatch) -> None:
    data, records, bundle, authorities, primary, claims, verified = unit_inputs(monkeypatch)
    authorize._authenticate_executions(primary, data, records, bundle, authorities, NOW, live_claims=claims)
    assert primary.selected == sorted(policy.EXECUTION_GATES) == verified
    assert len(primary.clients["live_authorized_smokes"].reads) == 1
    assert {row["job_id"] for row in claims} == {123, 456}
    assert len(claims) > len(data["live"]["observations"]) + len(data["live"]["prerequisites"])


def test_nonbool_actual_context_comparison_precedes_job_acceptance(monkeypatch: pytest.MonkeyPatch) -> None:
    data, records, bundle, authorities, primary, claims, _verified = unit_inputs(monkeypatch, bad_seal=True)
    with pytest.raises(ValueError, match="exact evidence bytes/context"):
        authorize._authenticate_executions(primary, data, records, bundle, authorities, NOW, live_claims=claims)
    assert primary.clients["live_authorized_smokes"].reads == []


@pytest.mark.parametrize("field,value", [("head_sha", "a" * 40), ("run_id", 42), ("run_attempt", 2),
    ("status", "queued"), ("conclusion", "failure"), ("labels", ["self-hosted", "ubuntu-latest"]),
    ("completed_at", "2026-10-31T01:40:00Z")])
def test_unit_authenticated_seal_never_substitutes_for_actual_job_metadata(monkeypatch: pytest.MonkeyPatch, field: str, value: object) -> None:
    data, records, bundle, authorities, primary, claims, _verified = unit_inputs(monkeypatch)
    primary.clients["live_authorized_smokes"].rows[0][field] = value
    with pytest.raises(ValueError):
        authorize._authenticate_executions(primary, data, records, bundle, authorities, NOW, live_claims=claims)
