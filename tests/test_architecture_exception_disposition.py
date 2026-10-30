from __future__ import annotations

import copy
import json
from datetime import date

from scripts.validate_architecture_exception_disposition import DISPOSITION_PATH, validate


def _disposition() -> dict:
    return json.loads(DISPOSITION_PATH.read_text(encoding="utf-8"))


def test_remaining_p9_exceptions_have_a_current_bound_p10_reauthorization() -> None:
    assert validate(as_of=date(2026, 10, 29)) == []


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
    assert "remaining P9 architecture exceptions require explicit dated P10 reauthorization" in errors


def test_reauthorization_requires_explicit_non_expired_review_window() -> None:
    disposition = copy.deepcopy(_disposition())
    disposition["review_due"] = "2026-10-28"
    errors = validate(disposition=disposition, as_of=date(2026, 10, 29))
    assert "architecture exception reauthorization review is overdue" in errors


def test_reauthorization_review_must_move_forward() -> None:
    disposition = copy.deepcopy(_disposition())
    disposition["reviewed_on"] = disposition["review_due"]
    errors = validate(disposition=disposition, as_of=date(2026, 10, 29))
    assert "architecture exception review_due must follow reviewed_on" in errors


def test_every_reauthorized_edge_requires_one_retirement_plan() -> None:
    disposition = copy.deepcopy(_disposition())
    disposition["retirement_plans"][0]["edges"] = []
    errors = validate(disposition=disposition)
    assert any("requires edges" in error for error in errors)
    assert any("cover every exact reauthorized edge" in error for error in errors)


def test_retirement_plans_cannot_duplicate_an_edge() -> None:
    disposition = copy.deepcopy(_disposition())
    edge = disposition["retirement_plans"][0]["edges"][0]
    disposition["retirement_plans"][1]["edges"].append(edge)
    errors = validate(disposition=disposition)
    assert any("must not duplicate edges" in error for error in errors)
