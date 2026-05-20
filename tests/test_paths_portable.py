"""Portable path defaults (Phase A PR-A1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maze.pipeline import paths as pipeline_paths
from maze.kpms import apply as kpms_apply


@pytest.mark.parametrize(
    "value",
    [
        pipeline_paths.DEFAULT_DATA_DIR,
        pipeline_paths.DEFAULT_OUTPUT_H5,
        kpms_apply.DEFAULT_MANIFEST_CSV,
    ],
)
def test_default_paths_have_no_lab_hardcoded_roots(value: Path) -> None:
    text = str(value).replace("/", "\\")
    assert "IMPRESS" not in text
    assert r"E:\videos" not in text
    assert r"E:\vast_analysis" not in text


def test_repo_root_matches_package_layout(repo_root: Path) -> None:
    assert (repo_root / "maze" / "pipeline" / "paths.py").is_file()
    assert pipeline_paths.DEFAULT_OUTPUT_H5.is_relative_to(repo_root)
    assert kpms_apply.DEFAULT_MANIFEST_CSV.is_relative_to(repo_root)
