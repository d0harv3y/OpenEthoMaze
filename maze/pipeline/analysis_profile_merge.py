"""Merge GUI analysis profile (trajectory + trace quality) into :class:`TrialSettings`."""

from __future__ import annotations

from dataclasses import replace

from maze.controller.acquisition.shared_config import (
    AnalysisTraceQualityConfig,
    AnalysisTrajectoryConfig,
)
from maze.core.trial_settings import TrialSettings


def merge_analysis_profile_into_trial_settings(
    base: TrialSettings,
    traj: AnalysisTrajectoryConfig,
    tq: AnalysisTraceQualityConfig,
) -> TrialSettings:
    """Return a copy of ``base`` with movement-bout and trace-quality fields replaced."""
    return replace(
        base,
        movement_start_threshold_m_per_frame=traj.movement_start_threshold_m_per_frame,
        movement_stop_threshold_m_per_frame=traj.movement_stop_threshold_m_per_frame,
        movement_speed_median_window_frames=traj.movement_speed_median_window_frames,
        movement_entry_debounce_frames=traj.movement_entry_debounce_frames,
        movement_exit_debounce_frames=traj.movement_exit_debounce_frames,
        min_movement_bout_duration_frames=traj.min_movement_bout_duration_frames,
        movement_inter_bout_interval_frames=traj.movement_inter_bout_interval_frames,
        max_movement_per_frame_cm=traj.max_movement_per_frame_cm,
        jump_filter_lookahead_frames=traj.jump_filter_lookahead_frames,
        filter_frames_no_animal=tq.filter_frames_no_animal,
        min_confident_nodes_per_frame=tq.min_confident_nodes_per_frame,
        min_node_confidence_threshold=tq.min_node_confidence_threshold,
        min_valid_frame_run_length=tq.min_valid_frame_run_length,
        min_mean_confidence_per_frame=tq.min_mean_confidence_per_frame,
        trace_interpolate_nans=tq.trace_interpolate_nans,
        trace_max_gap_frames=tq.trace_max_gap_frames,
        trace_interpolate_low_conf=tq.trace_interpolate_low_conf,
        trace_confidence_threshold=tq.trace_confidence_threshold,
        trace_apply_smoothing=tq.trace_apply_smoothing,
        trace_smoothing_window=tq.trace_smoothing_window,
    )
