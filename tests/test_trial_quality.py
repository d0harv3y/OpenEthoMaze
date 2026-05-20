"""trial_quality data checks (Phase A A6)."""

from __future__ import annotations

from pathlib import Path

from maze.pipeline.trial_quality import (
    REASON_FRAME_MISMATCH,
    REASON_MISSING_FRAME_COUNTS,
    REASON_MISSING_SLEAP,
    REASON_MISSING_VIDEO,
    detect_trial_data_quality,
)

from conftest import make_manifest


def test_detect_trial_data_quality_missing_video(tmp_path: Path) -> None:
    m = make_manifest(video_path=tmp_path / "missing.avi")
    assert detect_trial_data_quality(m, expected_frame_diff=None) == REASON_MISSING_VIDEO


def test_detect_trial_data_quality_frame_mismatch(tmp_path: Path) -> None:
    video = tmp_path / "trial.avi"
    video.touch()
    m = make_manifest(
        video_path=video,
        h5_n_frames=100,
        video_n_frames=100,
    )
    assert detect_trial_data_quality(m, expected_frame_diff=-1) == REASON_FRAME_MISMATCH


def test_detect_trial_data_quality_ok_when_policy_met(tmp_path: Path) -> None:
    video = tmp_path / "trial.avi"
    video.touch()
    m = make_manifest(
        video_path=video,
        h5_n_frames=100,
        video_n_frames=99,
    )
    assert detect_trial_data_quality(m, expected_frame_diff=-1) is None


def test_detect_trial_data_quality_missing_sleap_file(tmp_path: Path) -> None:
    video = tmp_path / "trial.avi"
    video.touch()
    m = make_manifest(
        video_path=video,
        sleap_path=tmp_path / "missing.h5.slp",
        h5_n_frames=10,
        video_n_frames=9,
    )
    assert detect_trial_data_quality(m, expected_frame_diff=-1) == REASON_MISSING_SLEAP


def test_detect_trial_data_quality_missing_frame_counts(tmp_path: Path) -> None:
    video = tmp_path / "trial.avi"
    video.touch()
    m = make_manifest(video_path=video, h5_n_frames=None, video_n_frames=10)
    assert detect_trial_data_quality(m, expected_frame_diff=None) == REASON_MISSING_FRAME_COUNTS
