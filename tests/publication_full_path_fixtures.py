"""COUNTERFACTUAL offline universe, never real execution or publication evidence.

Only external Git/gh process results, clock IO and fixture policy DATA are modeled.
All publication validators and public lifecycle functions execute unchanged. Git
responses model a descendant data-only E; they are not claims about actual objects.
The signature JSON models an external verifier's output, NOT a real signature.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts import publication_authorize as authorization
from scripts import publication_completion as completion
from scripts import publication_git as git_io
from scripts import publication_policy as policy
from scripts import publication_publish as publisher
from scripts import publication_transport as transport
from scripts.publication_authorize import canonical
from scripts.publication_evidence import execution_seal
from tests.test_publication_artifacts import verified_shape, zip_bytes
from tests.test_publication_evidence import evidence_package
from tests.test_publication_subject import payloads

OBSERVED = datetime(2026, 10, 31, 2, tzinfo=UTC)
NOW = OBSERVED + timedelta(minutes=10)
CANDIDATE, TREE, PRODUCER = "a" * 40, "b" * 40, "c" * 40
PREFIX = f"/repos/{policy.REPOSITORY}"
PUBLICATION_RUN, COMPLETION_ARTIFACT = 404, 424
SELECTION = {"prepare_run_id": 2, "artifact_id": 88, "evidence_pr": 77,
             "owner_comment_id": 901}


def stamp(minutes: int = 0) -> str:
    return (OBSERVED + timedelta(minutes=minutes)).isoformat()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FixtureClock:
    current = NOW

    @classmethod
    def now(cls, zone):
        assert zone is UTC
        return cls.current


class GitProcessModel:
    """Finite exact-command Git PROCESS seam; genuine git/read_evidence stay real."""

    def __init__(self, universe):
        self.universe = universe
        self.calls = []
        self.cached_commit, self.blobs, self.evidence_alias = None, {}, None

    def __call__(self, args, *, cwd, limit, timeout):
        u = self.universe
        assert cwd == u.root and limit == policy.MAX_EVIDENCE_BYTES and timeout == 20
        command = tuple(args[1:])
        self.calls.append(command)
        evidence = self.evidence_alias or u.evidence_commit
        fixed = {
            ("rev-parse", "HEAD"): CANDIDATE.encode() + b"\n",
            ("merge-base", "--is-ancestor", CANDIDATE, evidence): b"",
            ("-c", "core.hooksPath=", "fetch", "--no-tags", "--no-write-fetch-head",
             f"https://github.com/{policy.REPOSITORY}.git", evidence): b"",
        }
        if command in fixed:
            return fixed[command]
        if self.cached_commit != u.evidence_commit:
            members = {**u.records, git_io.ENTRY: canonical(u.evidence)}
            self.blobs = {hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw,
                                      usedforsecurity=False).hexdigest(): (name, raw)
                          for name, raw in members.items()}
            self.cached_commit = u.evidence_commit
        blobs = self.blobs
        if command == ("diff-tree", "--raw", "-r", "-z", "--no-renames", "--no-abbrev",
                       CANDIDATE, evidence):
            return b"".join(f":000000 100644 {'0' * 40} {blob} A\0{name}\0".encode()
                            for blob, (name, _raw) in sorted(blobs.items()))
        if command == ("ls-tree", "-r", "-z", evidence, "--", "publication-evidence"):
            return b"".join(f"100644 blob {blob}\t{name}\0".encode()
                            for blob, (name, _raw) in sorted(blobs.items()))
        if len(command) == 3 and command[:2] == ("cat-file", "-s") and command[2] in blobs:
            return str(len(blobs[command[2]][1])).encode()
        if len(command) == 3 and command[:2] == ("cat-file", "blob") and command[2] in blobs:
            return blobs[command[2]][1]
        raise AssertionError(f"Unmodeled Git operation: {command}")


class CounterfactualPublication:
    """Stateful provider PROCESS results only; GitHubCLI itself is not replaced."""

    def __init__(self, directory: Path):
        self.directory, self.root = directory, directory / "counterfactual-source"
        self.evidence, self.records, self.subject, self.subject_digest = evidence_package()
        self.files = {**payloads(), "publication-subject.json": canonical(self.subject) + b"\n"}
        assert digest(self.files["publication-subject.json"]) == self.subject_digest
        self.responses, self.archives, self.invocations = {}, {}, {}
        self.calls, self.writes, self.attestations = [], [], []
        self.release, self.tag, self.assets, self.asset_data = None, None, {}, {}
        self.phase, self.on_read, self.job_overrides = "publish", None, {}
        self.clock = type("IsolatedFixtureClock", (FixtureClock,), {"current": NOW})
        self.authorities = self._authorities()
        self._primary()
        self._preparation()
        self.reseal_evidence()
        self.git_process = GitProcessModel(self)

    @staticmethod
    def _repository(name, repository_id, owner_id):
        return {"full_name": name, "id": repository_id, "private": False,
                "owner": {"id": owner_id, "login": name.split("/")[0]}}

    def _authorities(self):
        identities = {"live_authorized_smokes": ("synthetic-live-lab/seo-live", 501, 601, 701),
                      "seven_archetype_benchmark": ("synthetic-benchmark-lab/seo-benchmark", 502, 602, 702),
                      "external_reproduction": ("synthetic-repro-lab/seo-reproducer", 987, 876, 765)}
        return {gate: [{"repository": name, "repository_id": repo, "owner_id": owner,
                        "actor_id": actor, "workflow": ".github/workflows/own-execution.yml",
                        "source_commit": PRODUCER, "source_ref": "refs/heads/main",
                        "independent": gate == "external_reproduction"}]
                for gate, (name, repo, owner, actor) in identities.items()}

    def _run(self, repo, run_id, workflow, workflow_id, commit, start, end, actor=None):
        actor = actor or {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN, "type": "User"}
        return {"id": run_id, "run_attempt": 1, "repository": repo, "head_repository": repo,
                "workflow_id": workflow_id, "path": workflow, "event": "workflow_dispatch",
                "head_branch": "main", "head_sha": commit, "status": "completed",
                "conclusion": "success", "actor": actor, "triggering_actor": actor,
                "created_at": stamp(start), "run_started_at": stamp(start), "updated_at": stamp(end)}

    def _install_run(self, repo, run, jobs):
        prefix = f"/repos/{repo['full_name']}"
        self.responses[prefix] = repo
        self.responses[prefix + f"/actions/workflows/{run['path'].split('/')[-1]}"] = {
            "id": run["workflow_id"], "path": run["path"], "state": "active"}
        endpoint = prefix + f"/actions/runs/{run['id']}"
        self.responses[endpoint] = self.responses[endpoint + "/attempts/1"] = run
        self.responses[endpoint + "/attempts/1/jobs?per_page=100&page=1"] = {
            "total_count": len(jobs), "jobs": jobs}

    def _artifact(self, repo, run, identity, name, archive, minute):
        endpoint = f"/repos/{repo['full_name']}/actions/artifacts/{identity}"
        self.responses[endpoint] = {
            "id": identity, "name": name, "size_in_bytes": len(archive), "digest": "sha256:" + digest(archive),
            "expired": False, "created_at": stamp(minute), "updated_at": stamp(minute),
            "expires_at": stamp(60 * 24), "workflow_run": {
                "id": run, "repository_id": repo["id"], "head_repository_id": repo["id"],
                "head_sha": CANDIDATE if repo["id"] == policy.REPOSITORY_ID else PRODUCER}}
        self.archives[endpoint + "/zip"] = archive

    def _primary(self):
        repo = self._repository(policy.REPOSITORY, policy.REPOSITORY_ID, policy.OWNER_ID)
        run = self._run(repo, 1, policy.VALIDATION_WORKFLOW, policy.VALIDATION_WORKFLOW_ID,
                        CANDIDATE, -30, -10)
        run["event"] = "push"
        jobs = [{"id": index + 1, "name": name, "status": "completed", "conclusion": "success"}
                for index, name in enumerate(sorted(policy.EXPECTED_CI_JOBS))]
        self._install_run(repo, run, jobs)
        self.responses[PREFIX + f"/actions/workflows/{policy.VALIDATION_WORKFLOW_ID}"] = {
            "id": policy.VALIDATION_WORKFLOW_ID, "path": policy.VALIDATION_WORKFLOW, "state": "active"}
        self.responses[PREFIX + "/branches/main"] = {"protected": True, "commit": {"sha": CANDIDATE}}
        self.responses[PREFIX + "/git/ref/heads/main"] = {"object": {"sha": CANDIDATE}}
        self.responses[PREFIX + "/git/commits/" + CANDIDATE] = {"sha": CANDIDATE, "tree": {"sha": TREE}}
        self.invocations[(policy.REPOSITORY, policy.PUBLICATION_WORKFLOW)] = PUBLICATION_RUN

    def _preparation(self):
        repo = self.responses[PREFIX]
        run = self._run(repo, 2, policy.PREPARATION_WORKFLOW, 222, CANDIDATE, -9, -5)
        jobs = [{"id": index + 51, "name": name, "status": "completed", "conclusion": "success"}
                for index, name in enumerate(("build", "attest"))]
        self._install_run(repo, run, jobs)
        self._artifact(repo, 2, 88, "publication-candidate", zip_bytes(self.files), -5)
        self.invocations[(policy.REPOSITORY, policy.PREPARATION_WORKFLOW)] = 2

    def _producer(self, gate):
        entry = self.authorities[gate][0]
        context = {key: entry[key] for key in ("repository_id", "owner_id", "actor_id")}
        pointer = self.evidence["executions"][gate]
        context.update({"run_id": pointer["run_id"], "run_attempt": 1})
        raw = canonical(execution_seal(self.evidence, self.records, gate=gate, execution_context=context))
        archive = zip_bytes({"result.json": raw})
        pointer.update(artifact_sha256=digest(archive), member_sha256=digest(raw))
        repo = self._repository(entry["repository"], entry["repository_id"], entry["owner_id"])
        actor = {"id": entry["actor_id"], "login": "synthetic-producer", "type": "User"}
        run = self._run(repo, pointer["run_id"], entry["workflow"], 333, PRODUCER, -4, 0, actor)
        jobs = [{"id": identity, "name": platform, "run_id": pointer["run_id"], "run_attempt": 1,
                 "head_sha": PRODUCER, "status": "completed", "conclusion": "success",
                 "labels": [platform + "-latest"], "started_at": stamp(-4), "completed_at": stamp()}
                for platform, identity in (("ubuntu", 123), ("windows", 456))]
        self._install_run(repo, run, jobs)
        self._artifact(repo, pointer["run_id"], 100, "own-execution-result", archive, 0)
        self.invocations[(entry["repository"], entry["workflow"])] = pointer["run_id"]

    def reseal_evidence(self):
        for gate in sorted(policy.EXECUTION_GATES):
            self._producer(gate)
        members = {**self.records, git_io.ENTRY: canonical(self.evidence)}
        inventory = [{"path": path, "sha256": digest(raw), "bytes": len(raw)}
                     for path, raw in sorted(members.items())]
        self.evidence_digest = digest(canonical(inventory))
        self.evidence_commit = hashlib.sha256(canonical(inventory) + b"synthetic-descendant-E").hexdigest()[:40]
        self._decisions()

    def _decisions(self):
        repo = self.responses[PREFIX]
        composite = {"schema_version": "1.0.0", "candidate_commit": CANDIDATE, "candidate_tree": TREE,
                     "evidence_commit": self.evidence_commit, "evidence_sha256": self.evidence_digest,
                     "subject_sha256": self.subject_digest, "artifact_id": 88,
                     "artifact_sha256": self.responses[PREFIX + "/actions/artifacts/88"]["digest"][7:],
                     **{key: self.subject[key] for key in ("ci_run_id", "ci_attempt", "prepare_run_id", "prepare_attempt")}}
        self.responses[PREFIX + "/pulls/77"] = {
            "number": 77, "state": "open", "draft": False,
            "head": {"sha": self.evidence_commit, "repo": repo},
            "base": {"sha": CANDIDATE, "ref": "main", "repo": repo}}
        rows = []
        for index, (login, actor) in enumerate(policy.REVIEW_ACTORS.values()):
            identity = 801 + index
            body = {**composite, "decision": "APPROVE_GREAT", "context_id": f"github:pull-request-review:{identity}",
                    "execution_id": f"github:pull-request-review:{identity}",
                    "objections": ["Synthetic only: verify exact prepared byte identities at every boundary.",
                                   "Synthetic only: reject revoked context before the next provider mutation.",
                                   "Synthetic only: do not confuse this test with real execution authority."],
                    "unresolved_findings": []}
            rows.append({"id": identity, "user": {"login": login, "id": actor, "type": "Bot"},
                         "commit_id": self.evidence_commit, "state": "APPROVED", "body": json.dumps(body),
                         "submitted_at": stamp(1 + index)})
        self.responses[PREFIX + "/pulls/77/reviews?per_page=100&page=1"] = rows
        body = json.dumps({**composite, "decision": "AUTHORIZE_PUBLICATION"})
        self.responses[PREFIX + "/issues/comments/901"] = {
            "id": 901, "node_id": "IC_synthetic_only", "body": body,
            "user": {"id": policy.OWNER_ID, "login": policy.OWNER_LOGIN, "type": "User"},
            "issue_url": f"https://api.github.com/repos/{policy.REPOSITORY}/issues/77",
            "created_at": stamp(3), "updated_at": stamp(3)}
        self.graph = {"data": {"node": {"databaseId": 901, "body": body, "createdAt": stamp(3),
                                      "updatedAt": stamp(3), "lastEditedAt": None,
                                      "author": {"login": policy.OWNER_LOGIN}}}}

    def install(self, monkeypatch):
        (self.root / "governance").mkdir(parents=True)
        (self.root / "governance/publication-execution-authorities.json").write_bytes(canonical({
            "schema_version": "1.0.0", "repository_id": policy.REPOSITORY_ID,
            "authorities": self.authorities}))
        environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": policy.REPOSITORY,
                       "GITHUB_REPOSITORY_ID": str(policy.REPOSITORY_ID), "GITHUB_REF": "refs/heads/main",
                       "GITHUB_SHA": CANDIDATE, "GITHUB_RUN_ID": str(PUBLICATION_RUN),
                       "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "publish"}
        for key, value in environment.items():
            monkeypatch.setenv(key, value)
        trusted_git = shutil.which("git")
        assert trusted_git is not None and Path(trusted_git).is_absolute()
        monkeypatch.setenv("PATH", str(Path(trusted_git).parent))
        for key in ("PUBLICATION_LIVE_READ_TOKEN", "PUBLICATION_BENCHMARK_READ_TOKEN", "PUBLICATION_REPRODUCTION_READ_TOKEN"):
            monkeypatch.setenv(key, "synthetic-read-only-sentinel")
        for module in (authorization, publisher, completion):
            monkeypatch.setattr(module, "datetime", self.clock)
        monkeypatch.setattr(git_io, "run_bounded", self.git_process)
        monkeypatch.setattr(transport, "run_bounded", self.process)
        monkeypatch.setattr(transport, "primary_token", lambda: None)
        self.api = transport.GitHubCLI(self.root, executable=sys.executable)

    def publication_run(self):
        repo = self.responses[PREFIX]
        run = self._run(repo, PUBLICATION_RUN, policy.PUBLICATION_WORKFLOW, 444, CANDIDATE, 4, 10)
        jobs = []
        for index, name in enumerate(("authorize", "publish", "complete")):
            active = name == self.phase
            done = self.phase == "completed" or name == "authorize" or (self.phase == "complete" and name == "publish")
            jobs.append({"id": 9001 + index, "name": name, "run_id": PUBLICATION_RUN,
                         "head_sha": CANDIDATE, "status": "in_progress" if active else "completed" if done else "queued",
                         "conclusion": "success" if done else None})
            jobs[-1].update(self.job_overrides.get(name, {}))
        if self.phase != "completed":
            run.update(status="in_progress", conclusion=None)
        return run, {"total_count": 3, "jobs": jobs}

    def process(self, args, *, limit, body=None, github_token=None, **kwargs):
        assert args[0] == self.api.executable and not kwargs
        arguments = args[1:]
        if arguments[:2] == ["attestation", "verify"]:
            return self._verified(arguments)
        assert arguments[:3] == ["api", "--hostname", "github.com"]
        endpoint = arguments[3]
        method = arguments[arguments.index("--method") + 1] if "--method" in arguments else "GET"
        self.calls.append((method, endpoint))
        if endpoint == "graphql":
            assert method == "POST" and json.loads(body)["variables"] == {"id": "IC_synthetic_only"}
            result = canonical(self.graph)
        elif method != "GET":
            result = canonical(self._write(method, endpoint, body))
        elif "/releases/assets/" in endpoint:
            result = self.asset_data[int(endpoint.rsplit("/", 1)[-1])]
        else:
            result = self._read("/" + endpoint)
        if method == "GET" and self.on_read is not None:
            self.on_read(endpoint)
        assert len(result) <= limit
        return result

    def _read(self, path):
        run, jobs = self.publication_run()
        dynamic = {PREFIX + f"/actions/runs/{PUBLICATION_RUN}": run,
                   PREFIX + f"/actions/runs/{PUBLICATION_RUN}/attempts/1": run,
                   PREFIX + f"/actions/runs/{PUBLICATION_RUN}/attempts/1/jobs?per_page=100&page=1": jobs,
                   PREFIX + "/git/matching-refs/tags/v1.7.1": [] if self.tag is None else [self.tag],
                   PREFIX + "/git/ref/tags/v1.7.1": self.tag,
                   PREFIX + "/releases?per_page=100&page=1": [] if self.release is None else [self.release],
                   PREFIX + "/releases/81": self.release, PREFIX + "/releases/tags/v1.7.1": self.release,
                   PREFIX + "/releases/81/assets?per_page=100&page=1": list(self.assets.values()),
                   PREFIX + "/actions/workflows/release.yml": {"id": 444, "path": policy.PUBLICATION_WORKFLOW, "state": "active"}}
        if path in self.archives:
            return self.archives[path]
        return canonical(deepcopy(dynamic[path] if path in dynamic else self.responses[path]))

    def _write(self, method, endpoint, raw):
        self.writes.append((method, endpoint))
        if endpoint.startswith("https://uploads.github.com/"):
            name = endpoint.split("?name=", 1)[1]
            assert method == "POST" and name not in {row["name"] for row in self.assets.values()}
            identity = 1001 + len(self.assets)
            result = {"id": identity, "name": name, "size": len(raw), "state": "uploaded",
                      "digest": "sha256:" + digest(raw)}
            self.assets[identity], self.asset_data[identity] = result, raw
            return result
        value = json.loads(raw)
        if endpoint == PREFIX[1:] + "/git/refs":
            assert method == "POST" and self.tag is None
            self.tag = {"ref": value["ref"], "object": {"type": "commit", "sha": value["sha"]}}
            return self.tag
        if endpoint == PREFIX[1:] + "/releases":
            assert method == "POST" and self.release is None
            self.release = {"id": 81, "tag_name": value["tag_name"], "draft": True,
                            "prerelease": False, "published_at": None, "immutable": False}
            return self.release
        assert endpoint == PREFIX[1:] + "/releases/81" and method == "PATCH"
        assert value == {"draft": False, "make_latest": "true"}
        self.release.update(draft=False, published_at=NOW.isoformat())
        return self.release

    def _verified(self, arguments):
        path = Path(arguments[2])
        repository, signer = arguments[4], arguments[6]
        workflow = signer.removeprefix(repository + "/")
        source, reference, predicate = arguments[8], arguments[12], arguments[15]
        assert arguments[10] == source and arguments[13] == "--deny-self-hosted-runners"
        run = self.invocations[(repository, workflow)]
        invocation = f"https://github.com/{repository}/actions/runs/{run}/attempts/1"
        result = verified_shape(path.name, digest(path.read_bytes()))
        verification = result[0]["verificationResult"]
        certificate = verification["signature"]["certificate"]
        signer_uri = f"https://github.com/{repository}/{workflow}@{reference}"
        certificate.update(subjectAlternativeName=signer_uri, buildSignerURI=signer_uri,
                           buildSignerDigest=source, sourceRepositoryURI="https://github.com/" + repository,
                           sourceRepositoryDigest=source, sourceRepositoryRef=reference, runInvocationURI=invocation)
        verification["verifiedTimestamps"][0]["timestamp"] = NOW.isoformat()
        verification["statement"].update(predicateType=predicate,
                                         predicate={"runDetails": {"metadata": {"invocationId": invocation}}})
        self.attestations.append((repository, workflow, source, path.name, predicate))
        return canonical(result)

    def install_completion(self, raw):
        self._artifact(self.responses[PREFIX], PUBLICATION_RUN, COMPLETION_ARTIFACT,
                       "publication-completion", zip_bytes({completion.MEMBER: raw}), 10)
