"""Tests for legacy virtual-trial H5 path heuristics (Phase D4a)."""

from __future__ import annotations

from pathlib import Path

from maze.controller.acquisition.gui.legacy_exit_seed import legacy_h5_candidate_paths


def test_legacy_h5_candidate_paths_explicit_source(tmp_path: Path) -> None:
    video = tmp_path / "videos" / "1_S01_T01.mp4"
    video.parent.mkdir(parents=True)
    explicit = tmp_path / "custom" / "legacy.h5"
    paths = legacy_h5_candidate_paths(
        virtual_video_path=video,
        seed_legacy_source=str(explicit),
        h5_filename="trials.h5",
        output_dir="",
    )
    assert paths == [explicit]


def test_legacy_h5_candidate_paths_default_order(tmp_path: Path) -> None:
    video = tmp_path / "cohort" / "videos" / "1_S01_T01.mp4"
    video.parent.mkdir(parents=True)
    out = tmp_path / "outputs"
    paths = legacy_h5_candidate_paths(
        virtual_video_path=video,
        seed_legacy_source="",
        h5_filename="my_trials.h5",
        output_dir=str(out),
    )
    assert paths == [
        tmp_path / "cohort" / "my_trials.h5",
        tmp_path / "cohort" / "trials.h5",
        out / "my_trials.h5",
    ]
