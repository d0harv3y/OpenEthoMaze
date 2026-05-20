"""trial_filters frame policy (Phase A A6)."""

from __future__ import annotations

from maze.core.tasks import ARENA_TYPE_CIRCULAR, ARENA_TYPE_RADIAL_ARM
from maze.pipeline.trial_filters import trial_matches_frame_policy

from conftest import make_manifest


def test_trial_matches_frame_policy_circular_enforces_diff_minus_one(tmp_path) -> None:
    video = tmp_path / "trial.avi"
    video.touch()
    ok = make_manifest(video_path=video, h5_n_frames=100, video_n_frames=99)
    bad = make_manifest(video_path=video, h5_n_frames=100, video_n_frames=100)
    assert trial_matches_frame_policy(ok, ARENA_TYPE_CIRCULAR) is True
    assert trial_matches_frame_policy(bad, ARENA_TYPE_CIRCULAR) is False


def test_trial_matches_frame_policy_radial_arm_skips_diff() -> None:
    m = make_manifest(h5_n_frames=50, video_n_frames=50)
    assert trial_matches_frame_policy(m, ARENA_TYPE_RADIAL_ARM) is True


def test_trial_matches_frame_policy_controller_mode_always_passes() -> None:
    m = make_manifest(h5_n_frames=1, video_n_frames=99, input_h5_path=".")
    assert trial_matches_frame_policy(m, ARENA_TYPE_CIRCULAR, mode="controller") is True


def test_trial_matches_frame_policy_auto_skips_controller_manifest() -> None:
    m = make_manifest(h5_n_frames=1, video_n_frames=99, input_h5_path="None")
    assert trial_matches_frame_policy(m, ARENA_TYPE_CIRCULAR, mode="auto") is True
