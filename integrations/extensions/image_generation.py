"""Bounded planning for optional image-generation providers."""

from __future__ import annotations

import hashlib
from typing import Any

from contracts.adapter import AdapterResult
from contracts.construction import ProviderServicePort

_LABELS = {
    "digitalCreation",
    "trainedAlgorithmicMedia",
    "compositeWithTrainedAlgorithmicMedia",
    "algorithmicMedia",
}
_FORMATS = {"avif", "webp", "jpeg", "png"}


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _validated_request(request: object) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise TypeError("request must be an object")
    prompt, label = (
        _required_text(request, "prompt"),
        _required_text(request, "digital_source_type"),
    )
    if label not in _LABELS:
        raise ValueError("digital_source_type is not an allowed synthetic-media label")
    optimization = request.get("optimization")
    if not isinstance(optimization, dict):
        raise ValueError("optimization is required")
    output_format = _required_text(optimization, "format").lower()
    if output_format not in _FORMATS:
        raise ValueError("optimization format must be avif, webp, jpeg, or png")
    width, height = optimization.get("width"), optimization.get("height")
    if any(
        not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 8192
        for value in (width, height)
    ):
        raise ValueError("optimization width and height must be integers from 1 to 8192")
    return {
        "prompt": prompt,
        "alt_text": _required_text(request, "alt_text"),
        "rights_basis": _required_text(request, "rights_basis"),
        "digital_source_type": label,
        "optimization": {"format": output_format, "width": width, "height": height},
    }


def _gate_result(state: str, cost: dict[str, Any] | None = None) -> AdapterResult:
    if state == "NOT_CONFIGURED":
        return AdapterResult(
            source="optional-integrations:image-gen",
            status="not_configured",
            data={"state": state, "provider": "image-gen"},
            warnings=["Image-generation provider credentials are not configured."],
        )
    return AdapterResult(
        source="optional-integrations:image-gen",
        status="blocked",
        data={"state": "BLOCKED", "provider": "image-gen", "cost": cost},
        warnings=["Image generation requires explicit cost approval within a ceiling."],
    )


class ImageGenerationService:
    """Build a provider request while keeping generation and publication behind later gates."""

    def __init__(self, providers: ProviderServicePort) -> None:
        self.providers = providers

    def plan(
        self,
        *,
        request: dict[str, Any],
        units: int,
        unit_cost: float | None,
        approved_ceiling: float | None,
        approved: bool,
    ) -> AdapterResult:
        preflight = self.providers.preflight(provider="image-gen")
        state = preflight.data["state"]
        if state == "NOT_CONFIGURED":
            return _gate_result("NOT_CONFIGURED")
        if state != "AVAILABLE":
            return AdapterResult(
                source="optional-integrations:image-gen", status=preflight.status,
                data={**preflight.data, "provider": "image-gen"}, warnings=list(preflight.warnings),
            )
        cost = self.providers.estimate(
            provider="image-gen",
            units=units,
            unit_cost=unit_cost,
            approved_ceiling=approved_ceiling,
            approved=approved,
        ).data
        if cost["state"] != "APPROVED":
            return _gate_result("BLOCKED", cost)
        normalized = _validated_request(request)
        prompt_digest = hashlib.sha256(normalized["prompt"].encode("utf-8")).hexdigest()
        data = {
            "state": "AUTHORIZED_PROVIDER_REQUEST",
            "provider": "image-gen",
            **normalized,
            "cost": cost,
            "provenance": {
                "provider": "image-gen",
                "prompt_sha256": prompt_digest,
                "generation_state": "NOT_RUN",
            },
            "auto_publish": False,
            "publish_state": "BLOCKED_PENDING_HUMAN_REVIEW",
            "required_review": [
                "rights and brand authorization",
                "visual accuracy and safety",
                "alt-text fitness for the final placement",
                "synthetic-media label preservation",
                "optimized asset verification",
            ],
            "rollback": {
                "action": "remove_generated_asset",
                "condition": "Any review, rights, provenance, labeling, or optimization gate fails.",
            },
        }
        return AdapterResult(
            source="optional-integrations:image-gen",
            status="ok",
            data=data,
            warnings=[
                "This authorizes a provider request only; no image was generated or published.",
                "Human review remains mandatory before the generated asset enters a publishing workflow.",
            ],
        )
