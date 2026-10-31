"""Cohesive DomainHistoryService operations with bounded evidence states."""

from __future__ import annotations

import urllib.parse
from collections.abc import Mapping
from typing import Any

from contracts.adapter import AdapterResult
from integrations.authority_media.input_data import (
    _host,
    _read_json,
)
from integrations.authority_media.transport import BoundedTransport


class DomainHistoryService:
    BOOTSTRAP = "https://data.iana.org/rdap/dns.json"

    def __init__(self, bootstrap_transport: BoundedTransport | None = None) -> None:
        self.bootstrap_transport = bootstrap_transport or BoundedTransport({"data.iana.org"})

    @staticmethod
    def normalize(payload: Mapping[str, Any], domain: str, source: str) -> AdapterResult:
        events = _rdap_events(payload)
        registrar = _rdap_registrar(payload)
        nameservers = _rdap_nameservers(payload)
        notices = _rdap_notices(payload)
        return AdapterResult(
            source=source,
            status="ok",
            data={
                "data_state": "AVAILABLE",
                "domain": str(payload.get("ldhName") or domain).lower(),
                "handle": payload.get("handle"),
                "status": payload.get("status", []),
                "events": events,
                "nameservers": nameservers,
                "secure_dns": payload.get("secureDNS"),
                "registrar": registrar,
                "notices": notices,
                "rdap_conformance": payload.get("rdapConformance", []),
                "ownership_inference": None,
            },
            warnings=[
                "RDAP registration data may be redacted, incomplete, delayed, or inconsistent across registries.",
                "Registrar and event data do not establish beneficial ownership or domain reputation.",
            ],
        )

    def history(self, domain: str, *, fixture_path: str | None = None) -> AdapterResult:
        host = _host(domain)
        if fixture_path:
            payload = _read_json(fixture_path)
            if not isinstance(payload, dict):
                return AdapterResult(
                    fixture_path, "invalid_response", {"data_state": "INVALID_RESPONSE"}, []
                )
            return self.normalize(payload, host, fixture_path)
        bootstrap, _ = self.bootstrap_transport.get_json(self.BOOTSTRAP)
        if not isinstance(bootstrap, dict) or not isinstance(bootstrap.get("services"), list):
            return AdapterResult(
                "iana-rdap-bootstrap", "invalid_response", {"data_state": "INVALID_RESPONSE"}, []
            )
        tld = host.rsplit(".", 1)[-1]
        base = _rdap_base(bootstrap, tld)
        if not base:
            return AdapterResult(
                "iana-rdap-bootstrap", "not_found", {"data_state": "NOT_FOUND", "domain": host}, []
            )
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme != "https" or not parsed.hostname:
            return AdapterResult(
                "iana-rdap-bootstrap", "invalid_response", {"data_state": "INVALID_RESPONSE"}, []
            )
        endpoint = base.rstrip("/") + "/domain/" + urllib.parse.quote(host, safe="")
        transport = BoundedTransport({parsed.hostname})
        payload, response = transport.get_json(endpoint, accepted_statuses=frozenset({200, 404}))
        if response.status_code == 404:
            return AdapterResult(
                endpoint, "not_found", {"data_state": "NOT_FOUND", "domain": host}, []
            )
        if not isinstance(payload, dict):
            return AdapterResult(
                endpoint, "invalid_response", {"data_state": "INVALID_RESPONSE"}, []
            )
        result = self.normalize(payload, host, endpoint)
        result.data["request_count"] = (
            self.bootstrap_transport.request_count + transport.request_count
        )
        result.data["retry_count"] = self.bootstrap_transport.retry_count + transport.retry_count
        return result


def _rdap_events(payload: Mapping[str, Any]) -> dict[str, list[str]]:
    events: dict[str, list[str]] = {}
    for item in payload.get("events", []) if isinstance(payload.get("events"), list) else []:
        if isinstance(item, dict) and item.get("eventAction") and item.get("eventDate"):
            events.setdefault(str(item["eventAction"]), []).append(str(item["eventDate"]))

    return events


def _rdap_registrar(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    registrar = None
    for entity in payload.get("entities", []) if isinstance(payload.get("entities"), list) else []:
        if not isinstance(entity, dict) or "registrar" not in entity.get("roles", []):
            continue
        registrar = {"handle": entity.get("handle"), "public_ids": entity.get("publicIds", [])}
        break

    return registrar


def _rdap_nameservers(payload: Mapping[str, Any]) -> list[str]:
    nameservers = []
    for item in (
        payload.get("nameservers", []) if isinstance(payload.get("nameservers"), list) else []
    ):
        if isinstance(item, dict) and item.get("ldhName"):
            nameservers.append(str(item["ldhName"]).lower())

    return nameservers


def _rdap_notices(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    notices = (
        [
            {"title": item.get("title"), "description": item.get("description")}
            for item in payload.get("notices", [])
            if isinstance(item, dict)
        ]
        if isinstance(payload.get("notices"), list)
        else []
    )

    return notices


def _rdap_base(bootstrap: dict[str, Any], tld: str) -> str | None:
    base = None
    for service in bootstrap["services"]:
        if not isinstance(service, list) or len(service) != 2:
            continue
        tlds, urls = service
        if (
            isinstance(tlds, list)
            and tld in {str(item).lower() for item in tlds}
            and isinstance(urls, list)
        ):
            base = next((str(url) for url in urls if str(url).startswith("https://")), None)
            break

    return base
