"""Counterfactual full-E chronology controls; real current Bing still denies."""

from datetime import timedelta

import pytest
from test_publication_benchmark import rewrite_records
from test_publication_evidence import NOW, evidence_package, validate_package


@pytest.mark.parametrize("command", ["render.page", "render.screenshot", "indexnow.submit"])
def test_earliest_actual_request_cannot_precede_required_setup_even_if_observation_finishes_later(command: str) -> None:
    data, records, subject, digest = evidence_package()
    assert validate_package(data, records, subject, digest) == data

    def earlier_actual_request(row):
        if row["kind"] != "normalized_observation" or command not in row["capabilities"]:
            return None
        return {**row, "requests": [{**request, "occurred_at": (NOW - timedelta(minutes=3, seconds=30)).isoformat()}
                                   if request["command_id"] == command else request for request in row["requests"]]}

    changed, raw = rewrite_records(data, records, earlier_actual_request)
    assert changed != data and raw != records
    with pytest.raises(ValueError, match="Prerequisite|setup|submission"):
        validate_package(changed, raw, subject, digest)
