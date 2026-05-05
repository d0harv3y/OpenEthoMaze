from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ..shared_config import AnalysisTrajectoryConfig
from ....pipeline.db import TrialKey, list_trials, open_db, read_trial_settings, read_xy_table
from ....pipeline.io.sleap_loader import TraceData, apply_jump_filter
from ....pipeline.metrics.ambulation import AmbulationMetrics, calculate_ambulation_metrics


@dataclass(frozen=True)
class TrajectorySource:
    label: str
    xy: np.ndarray
    valid: np.ndarray
    fps: float
    px_per_cm: float


def demo_source() -> TrajectorySource:
    """Default synthetic trajectory for previewing movement-bout settings."""
    n = 900
    t = np.linspace(0.0, 12.0, n)
    x = 320.0 + 140.0 * np.cos(t) + 14.0 * np.sin(7.0 * t)
    y = 240.0 + 120.0 * np.sin(t * 1.15) + 10.0 * np.cos(5.0 * t)
    # Add near-still bands.
    x[150:220] = x[149]
    y[150:220] = y[149]
    x[520:620] = x[519]
    y[520:620] = y[519]
    xy = np.column_stack([x, y]).astype(float)
    valid = np.ones(n, dtype=bool)
    return TrajectorySource(
        label="Demo trajectory",
        xy=xy,
        valid=valid,
        fps=26.7,
        px_per_cm=2.42,
    )


def list_trials_in_db(db_path: Path) -> list[TrialKey]:
    return list_trials(db_path)


def source_from_db(db_path: Path, key: TrialKey) -> Optional[TrajectorySource]:
    settings, _h5_fps, _timing = read_trial_settings(db_path, key)
    fps = 0.0
    try:
        with open_db(db_path, "r") as h5:
            fps = float(h5[key.path()].attrs.get("fps", 0.0) or 0.0)
    except Exception:
        fps = 0.0
    if fps <= 0:
        fps = 26.7
    xy_table = read_xy_table(db_path, key, point_name="spot_hybrid")
    if xy_table is None:
        xy_table = read_xy_table(db_path, key, point_name="spot")
    if xy_table is None or len(xy_table) == 0:
        return None
    xy = np.column_stack([xy_table["x"], xy_table["y"]]).astype(float)
    valid = np.asarray(xy_table["valid"] > 0, dtype=bool)
    return TrajectorySource(
        label=f"{key.animal_id}/{key.session}/{key.trial}",
        xy=xy,
        valid=valid,
        fps=fps,
        px_per_cm=float(settings.px_per_cm),
    )


def run_trajectory_preview(
    source: TrajectorySource,
    params: AnalysisTrajectoryConfig,
) -> tuple[AmbulationMetrics, np.ndarray]:
    """Apply SLEAP-style jump filter then movement-bout metrics (matches pipeline order for SLEAP)."""
    x = source.xy[:, 0].astype(float, copy=True)
    y = source.xy[:, 1].astype(float, copy=True)
    v = np.asarray(source.valid, dtype=bool)
    x[~v] = np.nan
    y[~v] = np.nan
    n = int(x.shape[0])
    score = np.where(np.isfinite(x) & np.isfinite(y), 1.0, 0.0).astype(np.float64)
    visible = (score > 0.5).astype(np.float64)
    td = TraceData(
        traces={
            "_preview": {
                "x": x,
                "y": y,
                "score": score,
                "visible": visible,
            }
        },
        node_names=["_preview"],
        n_frames=n,
        fps=float(source.fps),
        source_path=None,
    )
    apply_jump_filter(
        td,
        max_jump_cm=float(params.max_movement_per_frame_cm),
        px_per_cm=float(source.px_per_cm),
        lookahead_frames=int(params.jump_filter_lookahead_frames),
    )
    xf = td.traces["_preview"]["x"]
    yf = td.traces["_preview"]["y"]
    xy_f = np.column_stack([xf, yf])
    valid_f = np.isfinite(xf) & np.isfinite(yf)
    metrics = calculate_ambulation_metrics(
        xy=xy_f,
        valid=valid_f,
        px_per_cm=source.px_per_cm,
        fps=source.fps,
        start_threshold_m=params.movement_start_threshold_m_per_frame,
        stop_threshold_m=params.movement_stop_threshold_m_per_frame,
        speed_median_window_frames=params.movement_speed_median_window_frames,
        entry_debounce_frames=params.movement_entry_debounce_frames,
        exit_debounce_frames=params.movement_exit_debounce_frames,
        min_bout_duration_frames=params.min_movement_bout_duration_frames,
        inter_bout_interval_frames=params.movement_inter_bout_interval_frames,
    )
    return metrics, xy_f
