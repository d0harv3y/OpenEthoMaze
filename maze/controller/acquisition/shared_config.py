from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from ...pipeline.defaults import (
    FILTER_FRAMES_NO_ANIMAL,
    JUMP_FILTER_LOOKAHEAD_FRAMES,
    MAX_MOVEMENT_PER_FRAME_CM,
    MIN_CONFIDENT_NODES_PER_FRAME,
    MIN_MEAN_CONFIDENCE_PER_FRAME,
    MIN_NODE_CONFIDENCE_THRESHOLD,
    MIN_VALID_FRAME_RUN_LENGTH,
    MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
    MOVEMENT_EXIT_DEBOUNCE_FRAMES,
    MOVEMENT_INTER_BOUT_INTERVAL_FRAMES,
    MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
    MOVEMENT_START_THRESHOLD_M_PER_FRAME,
    MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
    MIN_MOVEMENT_BOUT_DURATION_FRAMES,
    TRACE_APPLY_SMOOTHING,
    TRACE_CONFIDENCE_THRESHOLD,
    TRACE_INTERPOLATE_LOW_CONF,
    TRACE_INTERPOLATE_NANS,
    TRACE_MAX_GAP_FRAMES,
    TRACE_SMOOTHING_WINDOW,
)


@dataclass
class AnimalInfo:
    """Per-animal metadata."""

    animal_id: str
    tx: Optional[str] = None
    strain: Optional[str] = None
    sex: Optional[str] = None
    drug: Optional[str] = None
    experiment: Optional[str] = None
    researcher: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class SessionConfig:
    """Shared session and roster settings for acquisition tasks."""

    num_animals: int = 1
    num_trials: int = 9
    max_trial_duration_s: float = 120.0
    iti_s: float = 10.0
    seed_mode: Literal["auto", "legacy", "manual"] = "auto"
    # Used only when ``seed_mode == "auto"``.
    seed_auto_value: Optional[int] = None
    # Used only when ``seed_mode == "legacy"``.
    seed_legacy_source: Optional[str] = None
    # When ``seed_mode == "manual"``: length num_animals * num_trials, 0-based exit indices.
    exit_schedule_indices: Optional[list[int]] = None
    animals: list[AnimalInfo] = field(default_factory=list)

    def ensure_animals(self) -> None:
        """Ensure animals list has at least ``num_animals`` entries."""
        while len(self.animals) < self.num_animals:
            self.animals.append(AnimalInfo(animal_id=str(1000 + len(self.animals))))


def ensure_exit_schedule_indices_length(
    session: SessionConfig,
    *,
    n_exits: int,
    default_exit_index: int,
) -> None:
    """Pad or truncate ``session.exit_schedule_indices`` for ``num_animals * num_trials`` slots."""
    total = max(0, int(session.num_animals) * int(session.num_trials))
    n_ang = max(1, int(n_exits))
    d = max(0, min(n_ang - 1, int(default_exit_index)))
    if total <= 0:
        session.exit_schedule_indices = None
        return
    cur = session.exit_schedule_indices
    if cur is None:
        session.exit_schedule_indices = [d] * total
        return
    cur_list = [max(0, min(n_ang - 1, int(x))) for x in cur[:total]]
    if len(cur_list) < total:
        cur_list.extend([d] * (total - len(cur_list)))
    session.exit_schedule_indices = cur_list


@dataclass
class FallbackTrackingConfig:
    """Backup tracking parameters shared by acquisition tasks."""

    min_area: int = 80
    max_area: int = 0
    morph_kernel_size: int = 5
    max_jump_px: float = 0.0
    selection_mode: str = "closest_else_largest"
    min_circularity: float = 0.0
    range_low: int = 0
    range_high: int = 255
    node_max_jump_px: float = 0.0
    node_jump_confirm_frames: int = 2
    min_sleap_nodes: int = 1
    show_blob_overlay: bool = True
    max_contours: int = 0
    # Next preview click sets backup intensity range (main window + Settings Tracking).
    range_from_next_click: bool = False
    range_pick_delta: int = 12
    range_pick_half: int = 2


@dataclass
class AnalysisTrajectoryConfig:
    """Movement-bout analysis knobs (frame-based canonical units)."""

    movement_start_threshold_m_per_frame: float = MOVEMENT_START_THRESHOLD_M_PER_FRAME
    movement_stop_threshold_m_per_frame: float = MOVEMENT_STOP_THRESHOLD_M_PER_FRAME
    movement_speed_median_window_frames: int = MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES
    movement_entry_debounce_frames: int = MOVEMENT_ENTRY_DEBOUNCE_FRAMES
    movement_exit_debounce_frames: int = MOVEMENT_EXIT_DEBOUNCE_FRAMES
    min_movement_bout_duration_frames: int = MIN_MOVEMENT_BOUT_DURATION_FRAMES
    movement_inter_bout_interval_frames: int = MOVEMENT_INTER_BOUT_INTERVAL_FRAMES
    max_movement_per_frame_cm: float = MAX_MOVEMENT_PER_FRAME_CM
    jump_filter_lookahead_frames: int = JUMP_FILTER_LOOKAHEAD_FRAMES


@dataclass
class AnalysisTraceQualityConfig:
    """SLEAP trace interpolation, smoothing, and per-frame confidence gates (pipeline-aligned)."""

    trace_interpolate_nans: bool = TRACE_INTERPOLATE_NANS
    trace_max_gap_frames: int = TRACE_MAX_GAP_FRAMES
    trace_interpolate_low_conf: bool = TRACE_INTERPOLATE_LOW_CONF
    trace_confidence_threshold: float = TRACE_CONFIDENCE_THRESHOLD
    trace_apply_smoothing: bool = TRACE_APPLY_SMOOTHING
    trace_smoothing_window: int = TRACE_SMOOTHING_WINDOW
    min_confident_nodes_per_frame: int = MIN_CONFIDENT_NODES_PER_FRAME
    min_node_confidence_threshold: float = MIN_NODE_CONFIDENCE_THRESHOLD
    min_valid_frame_run_length: int = MIN_VALID_FRAME_RUN_LENGTH
    min_mean_confidence_per_frame: Optional[float] = MIN_MEAN_CONFIDENCE_PER_FRAME
    filter_frames_no_animal: bool = FILTER_FRAMES_NO_ANIMAL


@dataclass
class AcquisitionConfig:
    """Shared acquisition shell configuration independent of task geometry."""

    session: SessionConfig = field(default_factory=SessionConfig)
    output_dir: Optional[str] = None
    h5_filename: str = "trials.h5"
    arena_type: str = ""
    run_mode: str = "continuous"
    fallback_tracking: FallbackTrackingConfig = field(default_factory=FallbackTrackingConfig)
    sleap_confidence_pct: int = 50
    sleap_every_n: int = 1
    sleap_exit_min_keypoints: int = 2
    fallback_exit_blob_overlap_pct: float = 15.0
    track_exit_either_success: bool = False
    sleap_model_path: str = ""
    track_show: bool = True
    track_async: bool = False
    track_enable_backup: bool = True
    track_enable_sleap: bool = True
    overlay_opacity_pct: int = 70
    arduino_port: Optional[str] = None
    run_analysis_after_trial: bool = False
    # Optional per-profile override for virtual source timing.
    # When set (>0), virtual playback uses constant effective_fps = segment_frames / duration_override_s,
    # where segment_frames = total_frames − anchor_frame (anchor = 0 on open, or last seek index).
    virtual_duration_override_s: Optional[float] = None
    # Next preview click sets arena center (VAST) or RAM template center (RAM).
    preview_set_center_from_next_click: bool = False
    analysis_trajectory: AnalysisTrajectoryConfig = field(default_factory=AnalysisTrajectoryConfig)
    analysis_trace_quality: AnalysisTraceQualityConfig = field(
        default_factory=AnalysisTraceQualityConfig
    )
