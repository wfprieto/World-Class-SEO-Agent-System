"""The unified CLI shares the bounded SERP loader, including volume imports."""

import argparse

import pytest

from scripts import serp_input_bounds
from seoctl import cli


@pytest.mark.parametrize("volumes", [False, True])
def test_unified_serp_cli_rejects_oversize_file_before_json_materialization(
    tmp_path, monkeypatch, volumes
):
    monkeypatch.setattr(serp_input_bounds, "MAX_INPUT_BYTES", 64)
    regular = tmp_path / "regular.json"
    regular.write_text("{}", encoding="utf-8")
    oversized = tmp_path / "oversized.json"
    oversized.write_text(" " * 128 + "{}", encoding="utf-8")
    args = argparse.Namespace(
        serps=str(regular if volumes else oversized),
        volumes=str(oversized) if volumes else None,
        strong=4,
    )
    with pytest.raises(ValueError, match="SERP input byte limit"):
        cli._cluster_serp(args)
