"""
Ambulation metrics calculation module for VAST pipeline.

Handles:
- Distance traveled calculation
- Speed metrics (mean, max)
- Movement bout detection with hysteresis thresholds
- Immobility time calculation

Ported from my_nor_wip with VAST-specific adaptations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from ..defaults import (
    MOVEMENT_START_THRESHOLD_M_PER_FRAME,
    MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
    MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
    MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
    MOVEMENT_EXIT_DEBOUNCE_FRAMES,
    MIN_MOVEMENT_BOUT_DURATION_FRAMES,
    MOVEMENT_INTER_BOUT_INTERVAL_FRAMES,
    MIN_MOVEMENT_BOUT_DURATION_S,
    MOVEMENT_INTER_BOUT_INTERVAL_S,
    DEFAULT_FPS,
)


@dataclass
class AmbulationMetrics:
    """Container for ambulation metrics."""
    
    total_distance_m: float = 0.0
    mean_speed_mps: float = 0.0
    max_speed_mps: float = 0.0
    time_moving_s: float = 0.0
    time_immobile_s: float = 0.0
    n_movement_bouts: int = 0
    movement_bouts: list[dict] = field(default_factory=list)


def calculate_ambulation_metrics(
    xy: np.ndarray,
    valid: np.ndarray,
    px_per_cm: float,
    fps: float = DEFAULT_FPS,
    start_threshold_m: float = MOVEMENT_START_THRESHOLD_M_PER_FRAME,
    stop_threshold_m: float = MOVEMENT_STOP_THRESHOLD_M_PER_FRAME,
    speed_median_window_frames: int = MOVEMENT_SPEED_MEDIAN_WINDOW_FRAMES,
    entry_debounce_frames: int = MOVEMENT_ENTRY_DEBOUNCE_FRAMES,
    exit_debounce_frames: int = MOVEMENT_EXIT_DEBOUNCE_FRAMES,
    min_bout_duration_frames: Optional[int] = MIN_MOVEMENT_BOUT_DURATION_FRAMES,
    inter_bout_interval_frames: Optional[int] = MOVEMENT_INTER_BOUT_INTERVAL_FRAMES,
    min_bout_duration_s: float = MIN_MOVEMENT_BOUT_DURATION_S,
    inter_bout_interval_s: float = MOVEMENT_INTER_BOUT_INTERVAL_S,
) -> AmbulationMetrics:
    """
    Calculate ambulation metrics from XY position data.
    
    Args:
        xy: Position array of shape (n_frames, 2) in pixels
        valid: Boolean array indicating valid frames
        px_per_cm: Pixels per centimeter calibration
        fps: Video frame rate
        start_threshold_m: Movement start threshold (meters per frame)
        stop_threshold_m: Movement stop threshold (meters per frame)
        speed_median_window_frames: Median filter window for per-frame distance
        entry_debounce_frames: Frames required above start threshold to enter movement
        exit_debounce_frames: Frames required below stop threshold to exit movement
        min_bout_duration_frames: Minimum movement bout duration in frames (canonical)
        inter_bout_interval_frames: Merge gap in frames (canonical)
        min_bout_duration_s: Minimum movement bout duration
        inter_bout_interval_s: Merge bouts closer than this interval
        
    Returns:
        AmbulationMetrics object
    """
    xy = np.asarray(xy, dtype=float)
    valid = np.asarray(valid, dtype=bool)
    
    n_frames = len(xy)
    if n_frames < 2:
        return AmbulationMetrics()
    
    # Convert pixels to meters
    # px_per_cm -> px_per_m = px_per_cm * 100
    px_per_m = px_per_cm * 100.0
    
    # Calculate frame-to-frame displacements
    dx = np.diff(xy[:, 0])
    dy = np.diff(xy[:, 1])
    distances_px = np.sqrt(dx**2 + dy**2)
    
    # Handle NaN values
    distances_px = np.nan_to_num(distances_px, nan=0.0)
    
    # Convert to meters
    distances_m = distances_px / px_per_m
    
    # Calculate movement bouts with hysteresis
    bouts, is_moving = _detect_movement_bouts(
        distances_m=distances_m,
        valid=valid,
        fps=fps,
        start_threshold_m=start_threshold_m,
        stop_threshold_m=stop_threshold_m,
        speed_median_window_frames=speed_median_window_frames,
        entry_debounce_frames=entry_debounce_frames,
        exit_debounce_frames=exit_debounce_frames,
        min_bout_duration_s=min_bout_duration_s,
        inter_bout_interval_s=inter_bout_interval_s,
        min_bout_duration_frames=min_bout_duration_frames,
        inter_bout_interval_frames=inter_bout_interval_frames,
    )
    
    # Calculate total distance (only during movement)
    moving_mask = np.zeros(len(distances_m), dtype=bool)
    for bout in bouts:
        start = bout['start_frame']
        end = bout['end_frame']
        moving_mask[start:end] = True
    
    total_distance_m = float(np.sum(distances_m[moving_mask]))
    
    # Calculate speed metrics
    speeds_mps = distances_m * fps  # Convert per-frame to per-second
    
    if np.any(moving_mask):
        mean_speed_mps = float(np.mean(speeds_mps[moving_mask]))
        max_speed_mps = float(np.max(speeds_mps[moving_mask]))
    else:
        mean_speed_mps = 0.0
        max_speed_mps = 0.0
    
    # Calculate time moving/immobile
    time_moving_s = float(np.sum(is_moving)) / fps
    time_immobile_s = float(np.sum(~is_moving)) / fps
    
    return AmbulationMetrics(
        total_distance_m=total_distance_m,
        mean_speed_mps=mean_speed_mps,
        max_speed_mps=max_speed_mps,
        time_moving_s=time_moving_s,
        time_immobile_s=time_immobile_s,
        n_movement_bouts=len(bouts),
        movement_bouts=bouts,
    )


def _detect_movement_bouts(
    distances_m: np.ndarray,
    valid: np.ndarray,
    fps: float,
    start_threshold_m: float,
    stop_threshold_m: float,
    speed_median_window_frames: int,
    entry_debounce_frames: int,
    exit_debounce_frames: int,
    min_bout_duration_s: float,
    inter_bout_interval_s: float,
    min_bout_duration_frames: Optional[int] = None,
    inter_bout_interval_frames: Optional[int] = None,
) -> tuple[list[dict], np.ndarray]:
    """
    Detect movement bouts using hysteresis thresholds.
    
    Args:
        distances_m: Per-frame distances in meters
        valid: Boolean array for valid frames
        fps: Frame rate
        start_threshold_m: Threshold to start movement
        stop_threshold_m: Threshold to stop movement
        speed_median_window_frames: Median filter window for per-frame distance
        entry_debounce_frames: Consecutive above-threshold frames needed for entry
        exit_debounce_frames: Consecutive below-threshold frames needed for exit
        min_bout_duration_s: Minimum bout duration
        inter_bout_interval_s: Merge bouts closer than this
        
    Returns:
        Tuple of (list of bout dicts, per-frame is_moving boolean array)
    """
    n_frames = len(valid)
    n_transitions = len(distances_m)
    
    if n_transitions == 0:
        return [], np.zeros(n_frames, dtype=bool)
    
    distances_for_state = _median_filter_1d(
        distances_m,
        window=max(1, int(speed_median_window_frames)),
    )

    entry_debounce_frames = max(1, int(entry_debounce_frames))
    exit_debounce_frames = max(1, int(exit_debounce_frames))

    # Apply hysteresis with debounce to determine movement state
    movement_state = np.zeros(n_transitions, dtype=bool)
    currently_moving = False
    above_start_count = 0
    below_stop_count = 0
    pending_start: Optional[int] = None

    for i, dist in enumerate(distances_for_state):
        # Check if both frames are valid
        if not (valid[i] and valid[i + 1]):
            movement_state[i] = False
            currently_moving = False
            above_start_count = 0
            below_stop_count = 0
            pending_start = None
            continue

        if not currently_moving:
            if dist >= start_threshold_m:
                above_start_count += 1
                if pending_start is None:
                    pending_start = i
                if above_start_count >= entry_debounce_frames:
                    currently_moving = True
                    start_idx = pending_start if pending_start is not None else i
                    movement_state[start_idx:i + 1] = True
                    above_start_count = 0
                    pending_start = None
            else:
                above_start_count = 0
                pending_start = None
        else:
            movement_state[i] = True
            if dist <= stop_threshold_m:
                below_stop_count += 1
                if below_stop_count >= exit_debounce_frames:
                    stop_run_start = i - exit_debounce_frames + 1
                    movement_state[stop_run_start:i + 1] = False
                    currently_moving = False
                    below_stop_count = 0
            else:
                below_stop_count = 0
    
    # Find bouts (contiguous movement periods)
    raw_bouts = []
    in_bout = False
    bout_start = 0
    
    for i, moving in enumerate(movement_state):
        if moving and not in_bout:
            in_bout = True
            bout_start = i
        elif not moving and in_bout:
            raw_bouts.append((bout_start, i))
            in_bout = False
    
    # Handle bout extending to end
    if in_bout:
        raw_bouts.append((bout_start, len(movement_state)))
    
    # Apply minimum duration filter
    if min_bout_duration_frames is None:
        min_bout_frames = int(min_bout_duration_s * fps)
    else:
        min_bout_frames = int(min_bout_duration_frames)
    min_bout_frames = max(1, min_bout_frames)
    filtered_bouts = [
        (start, end) for start, end in raw_bouts
        if (end - start) >= min_bout_frames
    ]
    
    # Merge bouts separated by short gaps
    if inter_bout_interval_frames is None:
        min_gap_frames = int(inter_bout_interval_s * fps)
    else:
        min_gap_frames = int(inter_bout_interval_frames)
    min_gap_frames = max(0, min_gap_frames)
    if len(filtered_bouts) > 1 and min_gap_frames > 0:
        merged_bouts = [filtered_bouts[0]]
        for start, end in filtered_bouts[1:]:
            prev_end = merged_bouts[-1][1]
            if start - prev_end < min_gap_frames:
                # Merge with previous bout
                merged_bouts[-1] = (merged_bouts[-1][0], end)
            else:
                merged_bouts.append((start, end))
        filtered_bouts = merged_bouts
    
    # Calculate metrics for each bout
    bouts = []
    for start, end in filtered_bouts:
        bout_distances = distances_m[start:end]
        bout_duration_frames = end - start
        bout_duration_s = bout_duration_frames / fps
        
        total_distance = float(np.sum(bout_distances))
        mean_speed = float(np.mean(bout_distances) * fps) if len(bout_distances) > 0 else 0.0
        max_speed = float(np.max(bout_distances) * fps) if len(bout_distances) > 0 else 0.0
        
        bouts.append({
            'start_frame': int(start),
            'end_frame': int(end),
            'duration_frames': int(bout_duration_frames),
            'duration_s': float(bout_duration_s),
            'total_distance_m': total_distance,
            'mean_speed_mps': mean_speed,
            'max_speed_mps': max_speed,
        })
    
    # Build per-frame is_moving array
    is_moving = np.zeros(n_frames, dtype=bool)
    for bout in bouts:
        start = bout['start_frame']
        end = min(bout['end_frame'] + 1, n_frames)  # +1 to include end frame
        is_moving[start:end] = True
    
    return bouts, is_moving


def _median_filter_1d(values: np.ndarray, window: int) -> np.ndarray:
    """Apply a simple 1D median filter with edge padding."""
    window = max(1, int(window))
    if window <= 1 or len(values) == 0:
        return values.copy()
    if window % 2 == 0:
        window += 1

    pad = window // 2
    padded = np.pad(values, (pad, pad), mode="edge")
    filtered = np.empty_like(values)
    for i in range(len(values)):
        filtered[i] = np.median(padded[i:i + window])
    return filtered


def calculate_distance_traveled(
    xy: np.ndarray,
    valid: np.ndarray,
    px_per_cm: float,
) -> float:
    """
    Calculate total distance traveled in meters.
    
    Args:
        xy: Position array (n_frames, 2) in pixels
        valid: Boolean validity array
        px_per_cm: Calibration factor
        
    Returns:
        Total distance in meters
    """
    xy = np.asarray(xy, dtype=float)
    valid = np.asarray(valid, dtype=bool)
    
    if len(xy) < 2:
        return 0.0
    
    # Convert px to meters
    px_per_m = px_per_cm * 100.0
    
    # Calculate displacements
    dx = np.diff(xy[:, 0])
    dy = np.diff(xy[:, 1])
    distances_px = np.sqrt(dx**2 + dy**2)
    
    # Only count valid transitions
    valid_transitions = valid[:-1] & valid[1:]
    distances_px[~valid_transitions] = 0.0
    
    # Convert and sum
    distances_m = distances_px / px_per_m
    return float(np.nansum(distances_m))
