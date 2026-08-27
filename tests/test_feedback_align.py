"""Tests for feedback/table alignment to ambulation xy timeline."""

from __future__ import annotations

import numpy as np
import pytest

from maze.core.schema import FEEDBACK_ROW_DTYPE, XY_ROW_DTYPE
from maze.pipeline.db.feedback_align import (
    align_feedback_to_xy_table,
    feedback_table_matches_xy,
    is_run_relative_legacy_feedback,
)


def _xy_table(n: int, *, run_start: int = 0) -> np.ndarray:
    xy = np.zeros(n, dtype=XY_ROW_DTYPE)
    xy["frame_index"] = np.arange(n, dtype=np.uint32)
    xy["trial_state"] = b"run"
    if run_start > 0:
        xy["trial_state"][:run_start] = b"iti_wait"
    xy["dist_to_exit_px"] = np.linspace(100.0, 10.0, n, dtype=np.float32)
    return xy


def _run_relative_feedback(n_run: int, duty: float = 50.0) -> np.ndarray:
    fb = np.zeros(n_run, dtype=FEEDBACK_ROW_DTYPE)
    fb["frame_index"] = np.arange(n_run, dtype=np.uint32)
    fb["trial_state"] = b"run"
    fb["motor_fb"] = duty
    fb["light_fb"] = duty * 0.5
    return fb


def _full_feedback(n: int, *, run_start: int) -> np.ndarray:
    fb = np.zeros(n, dtype=FEEDBACK_ROW_DTYPE)
    fb["frame_index"] = np.arange(n, dtype=np.uint32)
    fb["trial_state"] = b"run"
    fb["trial_state"][:run_start] = b"iti_wait"
    fb["motor_fb"] = 10.0
    fb["motor_fb"][run_start:] = 80.0
    return fb


def test_feedback_table_matches_xy_when_aligned() -> None:
    xy = _xy_table(100, run_start=20)
    fb = _full_feedback(100, run_start=20)
    assert feedback_table_matches_xy(fb, xy)


def test_is_run_relative_legacy_feedback() -> None:
    xy = _xy_table(3600, run_start=278)
    fb = _run_relative_feedback(3323)
    assert is_run_relative_legacy_feedback(fb, xy, run_start_frame=278)
    assert not is_run_relative_legacy_feedback(_full_feedback(3600, run_start=278), xy, run_start_frame=278)


def test_align_run_relative_expands_to_video_timeline() -> None:
    run_start = 278
    n_video = 3600
    xy = _xy_table(n_video, run_start=run_start)
    fb_legacy = _run_relative_feedback(3323, duty=42.0)
    aligned = align_feedback_to_xy_table(xy, fb_legacy, run_start_frame=run_start)
    assert len(aligned) == n_video
    assert feedback_table_matches_xy(aligned, xy)
    assert aligned["motor_fb"][run_start] == pytest.approx(42.0)
    assert aligned["motor_fb"][run_start + 100] == pytest.approx(42.0)
    assert np.isnan(aligned["motor_fb"][0])
    assert np.isnan(aligned["motor_fb"][run_start - 1])
    assert np.isfinite(aligned["motor_fb"][n_video - 1])


def test_align_full_length_reindexes_when_shorter_video() -> None:
    run_start = 10
    xy = _xy_table(100, run_start=run_start)
    fb_source = _full_feedback(120, run_start=run_start)
    aligned = align_feedback_to_xy_table(xy, fb_source, run_start_frame=run_start)
    assert len(aligned) == 100
    assert aligned["motor_fb"][run_start] == pytest.approx(80.0)
    assert aligned["motor_fb"][0] == pytest.approx(10.0)


def test_align_idempotent_when_already_matched() -> None:
    xy = _xy_table(50, run_start=5)
    fb = _full_feedback(50, run_start=5)
    again = align_feedback_to_xy_table(xy, fb, run_start_frame=5)
    assert feedback_table_matches_xy(again, xy)
    np.testing.assert_array_equal(again["motor_fb"], fb["motor_fb"])


def test_feedback_table_from_source_wm_fills_iti_from_source() -> None:
    from maze.pipeline.db.feedback_align import feedback_table_from_source_wm

    run_start = 278
    n_video = 3600
    n_source = 3601
    xy = _xy_table(n_video, run_start=run_start)
    w = np.zeros(n_source, dtype=np.float32)
    w[run_start:] = 50.0
    m = np.zeros(n_source, dtype=np.float32)
    m[run_start:] = 42.0
    aligned_run_only = align_feedback_to_xy_table(
        xy,
        _run_relative_feedback(n_video - run_start, duty=42.0),
        run_start_frame=run_start,
    )
    assert np.isnan(aligned_run_only["motor_fb"][0])
    backfilled = feedback_table_from_source_wm(
        xy,
        w,
        m,
        trial_start_frame=run_start,
    )
    assert feedback_table_matches_xy(backfilled, xy)
    assert backfilled["motor_fb"][0] == pytest.approx(0.0)
    assert backfilled["light_fb"][run_start - 1] == pytest.approx(0.0)
    assert backfilled["motor_fb"][run_start] == pytest.approx(42.0)
    assert backfilled["light_fb"][-1] == pytest.approx(50.0)


def test_build_feedback_table_from_wm_sets_states() -> None:
    from maze.pipeline.db.feedback import build_feedback_table_from_wm

    w = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    m = np.array([4.0, 5.0, 6.0], dtype=np.float32)
    fb = build_feedback_table_from_wm(w, m, trial_start_frame=1)
    assert fb["trial_state"][0] == b"iti_wait"
    assert fb["trial_state"][1] == b"run"
    assert fb["light_fb"][2] == pytest.approx(3.0)
    assert fb["motor_fb"][0] == pytest.approx(4.0)
