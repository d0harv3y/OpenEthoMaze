"""Tests for stored video_path prefix remapping."""

from __future__ import annotations

from pathlib import Path

from maze.pipeline import video_paths


def test_remap_video_path_prefix(tmp_path: Path) -> None:
    source_root = tmp_path / "lab" / "videos"
    target_root = tmp_path / "local" / "videos"
    video = target_root / "cohort" / "1_S01_T01.avi"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"x")

    remaps = [(str(source_root), str(target_root))]
    stored = source_root / "cohort" / "1_S01_T01.avi"
    assert video_paths.remap_video_path(stored, remaps) == video

    video_paths.set_runtime_video_path_prefix_remaps(remaps)
    try:
        assert video_paths.resolve_video_path(stored) == video.resolve()
        assert video_paths.video_path_for_storage(stored) == str(video.resolve())
    finally:
        video_paths.set_runtime_video_path_prefix_remaps(None)


def test_resolve_video_path_prefers_existing_original(tmp_path: Path) -> None:
    video = tmp_path / "1_S01_T01.avi"
    video.write_bytes(b"x")
    remaps = [(str(tmp_path / "missing"), str(tmp_path))]
    video_paths.set_runtime_video_path_prefix_remaps(remaps)
    try:
        assert video_paths.resolve_video_path(video) == video.resolve()
    finally:
        video_paths.set_runtime_video_path_prefix_remaps(None)


def test_set_runtime_video_path_prefix_remaps(tmp_path: Path) -> None:
    source_root = tmp_path / "e"
    target_root = tmp_path / "c"
    video = target_root / "trial.avi"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"x")
    stored = source_root / "trial.avi"

    video_paths.set_runtime_video_path_prefix_remaps([(str(source_root), str(target_root))])
    try:
        assert video_paths.resolve_video_path(stored) == video.resolve()
    finally:
        video_paths.set_runtime_video_path_prefix_remaps(None)
