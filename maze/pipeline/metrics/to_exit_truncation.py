"""
Recompute run-band metrics truncated at first exit-zone entry.

Used for experimental VAST trial-summary export: extra long-format metrics with
``{name}_to_exit`` suffixes under the primary ``spot_hybrid`` trajectory_source, so
distance / speed / path metrics match the designed stop-at-exit window when
offline tracking finds an earlier exit than live acquisition.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from maze.core.h5_layout import resolve_ambulation_metrics_group
from maze.core.trial_settings import TrialSettings
from maze.core.tasks import ARENA_TYPE_CIRCULAR, normalize_arena_type

from ..defaults import (
    CENTER_ZONE_RADIUS_CM,
    CENTER_ZONE_RADIUS_FRACTION,
    DEFAULT_FPS,
    EXIT_ZONE_RADIUS_CM,
    HYBRID_POINT_NAME,
    TO_EXIT_METRIC_SUFFIX,
)
from .ambulation import calculate_ambulation_metrics
from .exit_metrics import calculate_exit_metrics
from .task_metrics import calculate_task_metrics, summary_fields_for_task

__all__ = [
    "TO_EXIT_METRIC_SUFFIX",
    "TO_EXIT_SKIP_METRICS",
    "decode_trial_state_column",
    "first_exit_frame_in_band",
    "compute_run_summary_to_first_exit",
    "compute_hybrid_to_exit_summary_for_trial",
    "to_exit_metric_name",
]


def to_exit_metric_name(metric: str) -> str:
    """Map a base metric id to its truncated-at-exit export name."""
    return f"{metric}{TO_EXIT_METRIC_SUFFIX}"


# Metrics not re-emitted with ``_to_exit`` (redundant with the unsuffixed field / duration).
TO_EXIT_SKIP_METRICS: frozenset[str] = frozenset(
    {
        # First-exit latency already marks the designed stop; truncated duration is
        # ``trial_duration_s_to_exit`` (∼ latency + 1/fps). Emitting
        # ``latency_to_exit_s_to_exit`` only confuses pivot tables.
        "latency_to_exit_s",
    }
)

def decode_trial_state_column(states: np.ndarray) -> np.ndarray:
    """Decode ``trial_state`` bytes/str column to a 1-d unicode array."""
    out: list[str] = []
    for s in states:
        if isinstance(s, (bytes, bytearray)):
            out.append(s.decode("utf-8", errors="replace").strip())
        else:
            out.append(str(s or "").strip())
    return np.asarray(out, dtype=object)


def first_exit_frame_in_band(
    xy: np.ndarray,
    valid: np.ndarray,
    exit_pos: tuple[float, float],
    px_per_cm: float,
    exit_zone_radius_cm: float,
) -> Optional[int]:
    """Return the first valid in-exit frame index within the band, or None."""
    exit_metrics = calculate_exit_metrics(
        xy=xy,
        valid=valid,
        exit_pos=exit_pos,
        px_per_cm=px_per_cm,
        fps=1.0,
        exit_zone_radius_cm=exit_zone_radius_cm,
    )
    in_exit = exit_metrics.in_exit_zone_per_frame
    if in_exit is None:
        return None
    hits = np.where(np.asarray(in_exit, dtype=bool) & np.asarray(valid, dtype=bool))[0]
    if len(hits) == 0:
        return None
    return int(hits[0])


def compute_run_summary_to_first_exit(
    *,
    xy_run: np.ndarray,
    valid_run: np.ndarray,
    fps: float,
    px_per_cm: float,
    exit_pos: tuple[float, float],
    arena_center_pos: tuple[float, float],
    exit_zone_radius_cm: float,
    center_zone_radius_cm: float,
    arena_type: str = ARENA_TYPE_CIRCULAR,
    movement_start_threshold_m_per_frame: float,
    movement_stop_threshold_m_per_frame: float,
    movement_speed_median_window_frames: int,
    movement_entry_debounce_frames: int,
    movement_exit_debounce_frames: int,
    min_movement_bout_duration_frames: int,
    movement_inter_bout_interval_frames: int,
    task_context: dict[str, Any] | None = None,
) -> Optional[dict[str, Any]]:
    """
    Compute run-band summary metrics on ``xy_run[:first_exit+1]``.

    Returns None when the exit zone is never entered in the run band.
    """
    if xy_run.shape[0] == 0 or fps <= 0 or px_per_cm <= 0:
        return None

    cut = first_exit_frame_in_band(
        xy_run,
        valid_run,
        exit_pos,
        px_per_cm,
        exit_zone_radius_cm,
    )
    if cut is None:
        return None

    end = cut + 1
    xy_t = xy_run[:end]
    valid_t = valid_run[:end]

    amb = calculate_ambulation_metrics(
        xy=xy_t,
        valid=valid_t,
        px_per_cm=px_per_cm,
        fps=fps,
        start_threshold_m=movement_start_threshold_m_per_frame,
        stop_threshold_m=movement_stop_threshold_m_per_frame,
        speed_median_window_frames=movement_speed_median_window_frames,
        entry_debounce_frames=movement_entry_debounce_frames,
        exit_debounce_frames=movement_exit_debounce_frames,
        min_bout_duration_frames=min_movement_bout_duration_frames,
        inter_bout_interval_frames=movement_inter_bout_interval_frames,
    )
    task = calculate_task_metrics(
        arena_type=normalize_arena_type(arena_type),
        xy=xy_t,
        valid=valid_t,
        exit_pos=exit_pos,
        arena_center_pos=arena_center_pos,
        px_per_cm=px_per_cm,
        fps=fps,
        exit_zone_radius_cm=exit_zone_radius_cm,
        center_zone_radius_cm=center_zone_radius_cm,
        task_context=task_context,
    )
    summary: dict[str, Any] = {
        "total_distance_m": amb.total_distance_m,
        "mean_speed_mps": amb.mean_speed_mps,
        "max_speed_mps": amb.max_speed_mps,
        "time_moving_s": amb.time_moving_s,
        "time_immobile_s": amb.time_immobile_s,
        "n_movement_bouts": amb.n_movement_bouts,
        **summary_fields_for_task(
            arena_type=normalize_arena_type(arena_type),
            exit_metrics=task.exit_metrics,
            center_metrics=task.center_metrics,
        ),
        "trial_duration_s": float(end) / float(fps),
        "first_exit_frame": cut,
    }
    return summary


def _center_zone_radius_cm(settings: TrialSettings) -> float:
    if settings.arena_radius_px > 0 and settings.px_per_cm > 0:
        return CENTER_ZONE_RADIUS_FRACTION * settings.arena_radius_cm
    return CENTER_ZONE_RADIUS_CM


def _exit_zone_radius_cm(settings: TrialSettings) -> float:
    return settings.exit_radius_cm or EXIT_ZONE_RADIUS_CM


def compute_hybrid_to_exit_summary_for_trial(
    g_trial: Any,
    settings: TrialSettings,
    *,
    arena_type: str | None = None,
) -> Optional[dict[str, Any]]:
    """
    Build truncated run-band metrics from an open trial group.

    Expects ``ambulation_metrics/spot_hybrid/xy`` with ``trial_state`` bands.
    """
    exit_pos = settings.exit_pos
    if exit_pos is None or settings.px_per_cm <= 0:
        return None

    g_amb = resolve_ambulation_metrics_group(g_trial)
    if g_amb is None or HYBRID_POINT_NAME not in g_amb:
        return None
    g_pt = g_amb[HYBRID_POINT_NAME]
    if "xy" not in g_pt:
        return None

    xy_table = g_pt["xy"][:]
    if xy_table.shape[0] == 0:
        return None

    fps = float(g_pt.attrs.get("fps", g_trial.attrs.get("fps", DEFAULT_FPS)) or DEFAULT_FPS)
    if fps <= 0:
        return None

    states = decode_trial_state_column(xy_table["trial_state"])
    run = states == "run"
    if not np.any(run):
        return None

    xy_run = np.column_stack(
        (xy_table["x"][run].astype(float), xy_table["y"][run].astype(float))
    )
    valid_run = xy_table["valid"][run].astype(bool)

    resolved_arena = arena_type
    if resolved_arena is None:
        raw = g_trial.attrs.get("arena_type", ARENA_TYPE_CIRCULAR)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        resolved_arena = str(raw or ARENA_TYPE_CIRCULAR)

    return compute_run_summary_to_first_exit(
        xy_run=xy_run,
        valid_run=valid_run,
        fps=fps,
        px_per_cm=settings.px_per_cm,
        exit_pos=exit_pos,
        arena_center_pos=(settings.arena_center_x_px, settings.arena_center_y_px),
        exit_zone_radius_cm=_exit_zone_radius_cm(settings),
        center_zone_radius_cm=_center_zone_radius_cm(settings),
        arena_type=resolved_arena,
        movement_start_threshold_m_per_frame=settings.movement_start_threshold_m_per_frame,
        movement_stop_threshold_m_per_frame=settings.movement_stop_threshold_m_per_frame,
        movement_speed_median_window_frames=settings.movement_speed_median_window_frames,
        movement_entry_debounce_frames=settings.movement_entry_debounce_frames,
        movement_exit_debounce_frames=settings.movement_exit_debounce_frames,
        min_movement_bout_duration_frames=settings.min_movement_bout_duration_frames,
        movement_inter_bout_interval_frames=settings.movement_inter_bout_interval_frames,
    )
