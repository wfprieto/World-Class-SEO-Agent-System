from __future__ import annotations

import copy
import json

from scripts.validate_architecture_exception_disposition import DISPOSITION_PATH, validate


def _disposition() -> dict:
    return json.loads(DISPOSITION_PATH.read_text(encoding="utf-8"))


def test_remaining_p8_exceptions_have_a_bound_p9_reauthorization() -> None:
    assert validate() == []


def test_edge_set_change_invalidates_overdue_disposition() -> None:
    disposition = copy.deepcopy(_disposition())
    disposition["expected_edges_sha256"] = "0" * 64
    assert "overdue architecture exception edge set does not match disposition" in validate(
        disposition=disposition
    )


def test_disposition_cannot_hide_an_incomplete_count_or_earlier_target() -> None:
    disposition = copy.deepcopy(_disposition())
    disposition["expected_exception_count"] -= 1
    disposition["target_phase"] = "P7"
    errors = validate(disposition=disposition)
    assert "overdue architecture exception count does not match disposition" in errors
    assert "remaining P8 architecture exceptions require explicit dated P9 reauthorization" in errors
