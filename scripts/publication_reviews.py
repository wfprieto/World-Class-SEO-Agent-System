"""Authenticate current independent release decisions and unedited owner consent."""

from __future__ import annotations

import json
import re
from datetime import datetime

from scripts import publication_policy as policy
from scripts.publication_provider import (
    JsonObject,
    PublicationAPI,
    _primary_source,
    fresh_window,
    integer_value,
    object_value,
    read_object,
    repository_identity,
    text_value,
    timestamp,
)

OWNER_QUERY = """query PublicationOwnerComment($id: ID!) {
  node(id: $id) { ... on IssueComment {
    databaseId body createdAt updatedAt lastEditedAt author { login }
  } }
}"""


def _unique_pairs(pairs: list[tuple[str, object]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate decision JSON key")
        result[key] = value
    return result


def _nonfinite(_value: str) -> object:
    raise ValueError("nonfinite decision JSON is forbidden")


def _body(raw: object, composite: JsonObject, decision: str, extra: set[str]) -> JsonObject:
    value = text_value(raw, "decision body")
    if len(value.encode("utf-8")) > policy.MAX_RECORD_BYTES:
        raise ValueError("decision body exceeds its bound")
    try:
        result = object_value(json.loads(value, object_pairs_hook=_unique_pairs,
                                        parse_constant=_nonfinite), "decision body")
    except (json.JSONDecodeError, RecursionError):
        raise ValueError("decision body must be bounded strict JSON") from None
    if set(result) != set(composite) | {"decision"} | extra or result.get("decision") != decision:
        raise ValueError("decision body contract mismatch")
    for key, expected in composite.items():
        if result.get(key) != expected or type(result.get(key)) is not type(expected):
            raise ValueError("decision does not bind the exact frozen composite")
    return result


def _reviews(api: PublicationAPI, pr: int) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for page in range(1, policy.MAX_API_PAGES + 1):
        value = api.json(f"/repos/{policy.REPOSITORY}/pulls/{pr}/reviews"
                         f"?per_page={policy.PAGE_SIZE}&page={page}")
        if not isinstance(value, list) or len(value) > policy.PAGE_SIZE:
            raise ValueError("invalid review pagination")
        rows.extend(object_value(row, "review") for row in value)
        if len(value) < policy.PAGE_SIZE:
            break
    else:
        raise ValueError("review pagination exceeded its bound")
    ids = [integer_value(row.get("id"), "review ID") for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate review identities")
    return rows


def _latest(rows: list[JsonObject], login: str, actor_id: int) -> JsonObject:
    matching = []
    for row in rows:
        actor = object_value(row.get("user"), "review actor")
        if actor.get("login") == login or actor.get("id") == actor_id:
            if (integer_value(actor.get("id"), "review actor ID") != actor_id
                    or actor.get("login") != login or actor.get("type") != "Bot"):
                raise ValueError("canonical reviewer provider identity mismatch")
            matching.append(row)
    if not matching:
        raise ValueError("canonical independent review is missing")
    return max(matching, key=lambda row: (timestamp(row.get("submitted_at"), "review submitted"),
                                         integer_value(row.get("id"), "review ID")))


def _objections(body: JsonObject) -> None:
    objections = body.get("objections")
    if (not isinstance(objections, list) or not 3 <= len(objections) <= 32
            or any(not isinstance(row, str) or not 20 <= len(row.strip()) <= 10000 for row in objections)
            or len(set(objections)) != len(objections)):
        raise ValueError("review requires three distinct substantive objections")
    findings = body.get("unresolved_findings")
    if not isinstance(findings, list) or len(findings) > 100:
        raise ValueError("unresolved review findings must be explicit")
    for finding in findings:
        row = object_value(finding, "review finding")
        if (set(row) != {"severity", "finding"}
                or not isinstance(row.get("severity"), str)
                or row.get("severity") not in {"MINOR", "OBSERVATION"}
                or not text_value(row.get("finding"), "finding").strip()):
            raise ValueError("unresolved important or unknown review finding blocks publication")


def _role_reviews(
    api: PublicationAPI, pr: int, evidence_commit: str, composite: JsonObject,
    prepared: datetime, now: datetime,
) -> list[JsonObject]:
    rows = _reviews(api, pr)
    selected = []
    for login, actor_id in policy.REVIEW_ACTORS.values():
        review = _latest(rows, login, actor_id)
        if review.get("state") != "APPROVED" or review.get("commit_id") != evidence_commit:
            raise ValueError("latest canonical review is not approved for exact evidence head")
        submitted = timestamp(review.get("submitted_at"), "review submitted")
        fresh_window({"created_at": review.get("submitted_at")}, now, policy.PREPARED_TTL_SECONDS)
        if submitted < prepared:
            raise ValueError("review predates the prepared bytes")
        body = _body(review.get("body"), composite, "APPROVE_GREAT",
                     {"context_id", "execution_id", "objections", "unresolved_findings"})
        context = f"github:pull-request-review:{integer_value(review.get('id'), 'review ID')}"
        if body.get("context_id") != context or body.get("execution_id") != context:
            raise ValueError("review context must derive from its provider identity")
        _objections(body)
        selected.append(review)
    return selected


def _owner_edit_proof(api: PublicationAPI, comment: JsonObject) -> None:
    node_id = text_value(comment.get("node_id"), "owner comment node")
    response = object_value(api.graphql(OWNER_QUERY, {"id": node_id}), "owner edit response")
    if response.get("errors"):
        raise ValueError("owner edit provenance is unavailable")
    node = object_value(object_value(response.get("data"), "owner graph data").get("node"), "owner node")
    author = object_value(node.get("author"), "owner graph author")
    if ("lastEditedAt" not in node or node["lastEditedAt"] is not None
            or integer_value(node.get("databaseId"), "owner graph ID") != comment.get("id")
            or node.get("body") != comment.get("body") or author.get("login") != policy.OWNER_LOGIN
            or timestamp(node.get("createdAt"), "graph created") != timestamp(comment.get("created_at"), "created")
            or timestamp(node.get("updatedAt"), "graph updated") != timestamp(comment.get("updated_at"), "updated")):
        raise ValueError("owner decision was edited or its provider records disagree")


def _owner_decision(
    api: PublicationAPI, comment_id: int, pr: int, composite: JsonObject,
    reviews: list[JsonObject], now: datetime,
) -> JsonObject:
    comment = read_object(api, f"/repos/{policy.REPOSITORY}/issues/comments/{comment_id}")
    actor = object_value(comment.get("user"), "owner actor")
    expected_issue = f"https://api.github.com/repos/{policy.REPOSITORY}/issues/{pr}"
    if (integer_value(comment.get("id"), "owner comment") != comment_id
            or integer_value(actor.get("id"), "owner actor ID") != policy.OWNER_ID
            or actor.get("login") != policy.OWNER_LOGIN or actor.get("type") != "User"
            or comment.get("issue_url") != expected_issue):
        raise ValueError("owner decision provider identity/PR mismatch")
    created = timestamp(comment.get("created_at"), "owner created")
    if (created != timestamp(comment.get("updated_at"), "owner updated")
            or any(created <= timestamp(review.get("submitted_at"), "review submitted") for review in reviews)):
        raise ValueError("owner decision must be unedited and follow both role decisions")
    fresh_window(comment, now, policy.PREPARED_TTL_SECONDS)
    _owner_edit_proof(api, comment)
    _body(comment.get("body"), composite, "AUTHORIZE_PUBLICATION", set())
    return comment


def _pull_request(api: PublicationAPI, pr: int, candidate: str, evidence_commit: str) -> None:
    record = read_object(api, f"/repos/{policy.REPOSITORY}/pulls/{pr}")
    if integer_value(record.get("number"), "evidence PR") != pr or record.get("state") != "open" or record.get("draft") is not False:
        raise ValueError("evidence PR is not the exact open non-draft PR")
    for field, commit in (("head", evidence_commit), ("base", candidate)):
        branch = object_value(record.get(field), f"evidence {field}")
        repository_identity(branch.get("repo"), policy.REPOSITORY, policy.REPOSITORY_ID, policy.OWNER_ID)
        if branch.get("sha") != commit or (field == "base" and branch.get("ref") != "main"):
            raise ValueError("evidence PR base/head drift")


def authenticate_decisions(
    api: PublicationAPI, subject: JsonObject, *, evidence_pr: int, evidence_commit: str,
    evidence_sha256: str, artifact_id: int, archive_sha256: str, subject_sha256: str,
    owner_comment_id: int, now: datetime,
) -> JsonObject:
    candidate = text_value(subject.get("candidate_commit"), "candidate")
    if re.fullmatch(r"[0-9a-f]{40}", evidence_commit) is None:
        raise ValueError("evidence commit must be exact")
    for value in (evidence_sha256, archive_sha256, subject_sha256):
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("decision composite requires exact digests")
    _primary_source(api, candidate, text_value(subject.get("candidate_tree"), "tree"))
    _pull_request(api, integer_value(evidence_pr, "evidence PR"), candidate, evidence_commit)
    composite: JsonObject = {
        "schema_version": "1.0.0", "candidate_commit": candidate,
        "candidate_tree": subject["candidate_tree"], "evidence_commit": evidence_commit,
        "evidence_sha256": evidence_sha256, "subject_sha256": subject_sha256,
        "artifact_id": integer_value(artifact_id, "artifact ID"), "artifact_sha256": archive_sha256,
        **{field: integer_value(subject.get(field), field) for field in
           ("ci_run_id", "ci_attempt", "prepare_run_id", "prepare_attempt")},
    }
    selected = _role_reviews(api, evidence_pr, evidence_commit, composite,
                             timestamp(subject.get("prepared_at"), "prepared"), now)
    owner = _owner_decision(api, integer_value(owner_comment_id, "owner decision"),
                             evidence_pr, composite, selected, now)
    return {"owner_comment_id": owner_comment_id, "owner_created_at": owner["created_at"],
            "review_ids": [row["id"] for row in selected], "composite": composite}
