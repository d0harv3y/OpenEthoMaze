"""Tests for first-exit truncation of run-band metrics."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from maze.core.h5_layout import write_xy_table
from maze.core.schema import XY_ROW_DTYPE
from maze.pipeline.db import (
    TrialKey,
    ensure_trial_group,
    init_database,
    write_trial_settings,
)
from maze.pipeline.defaults import (
    EXIT_ZONE_RADIUS_CM,
    HYBRID_POINT_NAME,
    TO_EXIT_METRIC_SUFFIX,
)
from maze.pipeline.exports.csv_trials import export_trial_summary
from maze.pipeline.metrics.to_exit_truncation import (
    compute_run_summary_to_first_exit,
    first_exit_frame_in_band,
    to_exit_metric_name,
)


def test_first_exit_frame_in_band() -> None:
    px_per_cm = 10.0
    exit_pos = (0.0, 0.0)
    # Exit radius 12.5 cm → 125 px. Frames: outside, outside, inside, inside, outside.
    xy = np.array(
        [
            [200.0, 0.0],
            [180.0, 0.0],
            [50.0, 0.0],
            [40.0, 0.0],
            [200.0, 0.0],
        ],
        dtype=float,
    )
    valid = np.ones(len(xy), dtype=bool)
    cut = first_exit_frame_in_band(xy, valid, exit_pos, px_per_cm, EXIT_ZONE_RADIUS_CM)
    assert cut == 2


def test_compute_run_summary_to_first_exit_excludes_post_exit_distance() -> None:
    fps = 10.0
    px_per_cm = 10.0
    exit_pos = (0.0, 0.0)
    arena_center = (0.0, 0.0)
    # Approach exit over frames 0..2, graze at frame 2, then wander far (would inflate distance).
    xy = np.array(
        [
            [200.0, 0.0],
            [150.0, 0.0],
            [50.0, 0.0],  # first in-exit
            [50.0, 500.0],
            [50.0, 1000.0],
        ],
        dtype=float,
    )
    valid = np.ones(len(xy), dtype=bool)
    full = compute_run_summary_to_first_exit(
        xy_run=xy,
        valid_run=valid,
        fps=fps,
        px_per_cm=px_per_cm,
        exit_pos=exit_pos,
        arena_center_pos=arena_center,
        exit_zone_radius_cm=EXIT_ZONE_RADIUS_CM,
        center_zone_radius_cm=12.5,
        movement_start_threshold_m_per_frame=0.0,
        movement_stop_threshold_m_per_frame=0.0,
        movement_speed_median_window_frames=1,
        movement_entry_debounce_frames=1,
        movement_exit_debounce_frames=1,
        min_movement_bout_duration_frames=1,
        movement_inter_bout_interval_frames=1,
    )
    assert full is not None
    assert full["first_exit_frame"] == 2
    assert abs(full["trial_duration_s"] - 0.3) < 1e-9
    assert abs(full["latency_to_exit_s"] - 0.2) < 1e-6
    # Truncated path cannot include the huge post-exit steps.
    assert full["total_distance_m"] < 1.0


def test_compute_run_summary_none_when_never_exits() -> None:
    xy = np.array([[200.0, 0.0], [180.0, 0.0]], dtype=float)
    valid = np.ones(2, dtype=bool)
    out = compute_run_summary_to_first_exit(
        xy_run=xy,
        valid_run=valid,
        fps=10.0,
        px_per_cm=10.0,
        exit_pos=(0.0, 0.0),
        arena_center_pos=(0.0, 0.0),
        exit_zone_radius_cm=EXIT_ZONE_RADIUS_CM,
        center_zone_radius_cm=12.5,
        movement_start_threshold_m_per_frame=0.0,
        movement_stop_threshold_m_per_frame=0.0,
        movement_speed_median_window_frames=1,
        movement_entry_debounce_frames=1,
        movement_exit_debounce_frames=1,
        min_movement_bout_duration_frames=1,
        movement_inter_bout_interval_frames=1,
    )
    assert out is None


def _make_xy(n: int, *, exit_at: int | None, fps: float = 10.0) -> np.ndarray:
    table = np.zeros(n, dtype=XY_ROW_DTYPE)
    table["frame_index"] = np.arange(n, dtype=np.uint32)
    table["t_s"] = np.arange(n, dtype=np.float64) / fps
    table["valid"] = 1
    table["is_moving"] = 1
    table["trial_state"] = b"run"
    # Far from exit (0,0) by default; enter zone at exit_at.
    for i in range(n):
        if exit_at is not None and i >= exit_at:
            table["x"][i] = 40.0
            table["y"][i] = 0.0
            table["dist_to_exit_px"][i] = 40.0
        else:
            table["x"][i] = 200.0
            table["y"][i] = 0.0
            table["dist_to_exit_px"][i] = 200.0
    return table


def test_export_emits_to_exit_metric_suffixes_for_experimental_only(tmp_path: Path) -> None:
    db = tmp_path / "vast.h5"
    init_database(db)
    fps = 10.0
    px_per_cm = 10.0
    exit_radius_px = EXIT_ZONE_RADIUS_CM * px_per_cm

    exp_key = TrialKey("1", "S01", "T01")
    hab_key = TrialKey("1", "H01", "T01")
    for key in (exp_key, hab_key):
        ensure_trial_group(db, key)
        write_trial_settings(
            db,
            key,
            arena_radius_px=300.0,
            px_per_cm=px_per_cm,
            arena_center_x_px=0.0,
            arena_center_y_px=0.0,
            exit_number=1,
            exit_x=0.0,
            exit_y=0.0,
            exit_radius_px=exit_radius_px,
            h5_fps=fps,
        )

    with h5py.File(db, "a") as h5:
        for key, exit_at in ((exp_key, 3), (hab_key, 3)):
            g = h5[key.path()]
            g.attrs["analysis_duration_s"] = 1.0
            g.attrs["fps"] = fps
            g.attrs["primary_trajectory"] = HYBRID_POINT_NAME
            write_xy_table(g, HYBRID_POINT_NAME, _make_xy(10, exit_at=exit_at, fps=fps), fps)

    out = export_trial_summary(db_path=db, output_path=tmp_path / "trial_summary.csv")
    df = pd.read_csv(out)
    assert set(df["trajectory_source"].unique()) == {HYBRID_POINT_NAME}

    exp = df[(df["session"] == "S01") & (df["trial"] == "T01")]
    hab = df[df["session"] == "H01"]
    assert to_exit_metric_name("trial_duration_s") in set(exp["metric"])
    assert to_exit_metric_name("total_distance_m") in set(exp["metric"])
    assert to_exit_metric_name("latency_to_exit_s") not in set(exp["metric"])
    assert not any(str(m).endswith(TO_EXIT_METRIC_SUFFIX) for m in hab["metric"])

    dur = float(
        exp.loc[exp["metric"] == to_exit_metric_name("trial_duration_s"), "value"].iloc[0]
    )
    assert abs(dur - 0.4) < 1e-6  # frames 0..3 inclusive; latency would be 0.3 s
