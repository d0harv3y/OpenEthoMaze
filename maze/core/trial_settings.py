"""Canonical trial-settings model shared across pipeline readers and storage."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TrialSettings:
    """Container for trial settings parsed from controller or legacy H5 data."""

    arena_center_x_px: float
    arena_center_y_px: float
    arena_radius_px: float
    px_per_cm: float
    stage: str
    color: str
    timestamp: Optional[datetime]
    exit_number: Optional[int] = None
    exit_x: Optional[float] = None
    exit_y: Optional[float] = None
    exit_radius_px: Optional[float] = None
    roi_old: Optional[str] = None
    movement_start_threshold_m_per_frame: float = math.sqrt(2) / 150
    movement_stop_threshold_m_per_frame: float = math.sqrt(2) / 300
    movement_speed_median_window_frames: int = 3
    movement_entry_debounce_frames: int = 3
    movement_exit_debounce_frames: int = 3
    min_movement_bout_duration_frames: int = 4
    movement_inter_bout_interval_frames: int = 4
    max_movement_per_frame_cm: float = 15.0
    jump_filter_lookahead_frames: int = 3
    # Trace quality / confidence gating (aligned with ``maze.pipeline.defaults``).
    filter_frames_no_animal: bool = True
    min_confident_nodes_per_frame: int = 3
    min_node_confidence_threshold: float = 0.55
    min_valid_frame_run_length: int = 5
    min_mean_confidence_per_frame: Optional[float] = None
    trace_interpolate_nans: bool = True
    trace_max_gap_frames: int = 15
    trace_interpolate_low_conf: bool = True
    trace_confidence_threshold: float = 0.55
    trace_apply_smoothing: bool = True
    trace_smoothing_window: int = 3

    @property
    def exit_pos(self) -> Optional[tuple[float, float]]:
        if self.exit_x is not None and self.exit_y is not None:
            return (self.exit_x, self.exit_y)
        return None

    @property
    def arena_radius_cm(self) -> float:
        return self.arena_radius_px / self.px_per_cm

    @property
    def exit_radius_cm(self) -> Optional[float]:
        if self.exit_radius_px is None or self.px_per_cm <= 0:
            return None
        return self.exit_radius_px / self.px_per_cm

    @property
    def cm_per_px(self) -> float:
        return 1.0 / self.px_per_cm if self.px_per_cm > 0 else 0.0


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """Parse the timestamp strings seen in imported and controller-written H5 files."""
    formats = [
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(timestamp_str.strip(), fmt)
        except ValueError:
            continue

    return None
