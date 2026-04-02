"""
Exit-related metrics for VAST pipeline.

VAST-specific metrics related to the exit/target zone:
- Distance to exit over time
- Latency to reach exit zone
- Time spent in exit zone
- Path efficiency (straight-line vs actual path)
- Number of exit zone entries

The VAST task involves a circular arena where vibration intensity
is proportional to the animal's distance from the exit position.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..defaults import (
    CENTER_ENTRY_DEBOUNCE_S,
    CENTER_ZONE_RADIUS_CM,
    DEFAULT_FPS,
    EXIT_ZONE_RADIUS_CM,
)


@dataclass
class ExitMetrics:
    """Container for exit-related metrics."""
    
    # Latency (in seconds) to first reach exit zone
    # NaN if exit zone was never reached
    latency_to_exit_s: float = np.nan
    
    # Total time spent in exit zone (seconds)
    time_in_exit_zone_s: float = 0.0
    
    # Fraction of trial spent in exit zone
    time_in_exit_zone_fraction: float = 0.0
    
    # Mean distance to exit (cm) across all valid frames
    mean_distance_to_exit_cm: float = np.nan
    
    # Minimum distance to exit (cm) achieved
    min_distance_to_exit_cm: float = np.nan
    
    # Path efficiency: straight-line distance / actual path distance
    # 1.0 = perfect efficiency, < 1.0 = inefficient path
    path_efficiency: float = np.nan
    
    # Number of times entered the exit zone
    n_exit_zone_entries: int = 0
    
    # Per-frame distance to exit (for detailed analysis)
    distance_to_exit_per_frame: Optional[np.ndarray] = None
    
    # Per-frame boolean: in exit zone
    in_exit_zone_per_frame: Optional[np.ndarray] = None


def calculate_exit_metrics(
    xy: np.ndarray,
    valid: np.ndarray,
    exit_pos: tuple[float, float],
    px_per_cm: float,
    fps: float = DEFAULT_FPS,
    exit_zone_radius_cm: float = EXIT_ZONE_RADIUS_CM,
) -> ExitMetrics:
    """
    Calculate exit-related metrics from position data.
    
    Args:
        xy: Position array (n_frames, 2) in pixels
        valid: Boolean array indicating valid frames
        exit_pos: Exit position (x, y) in pixels
        px_per_cm: Calibration factor (pixels per cm)
        fps: Video frame rate
        exit_zone_radius_cm: Radius of exit zone in cm
        
    Returns:
        ExitMetrics object with calculated metrics
    """
    xy = np.asarray(xy, dtype=float)
    valid = np.asarray(valid, dtype=bool)
    exit_x, exit_y = exit_pos
    
    n_frames = len(xy)
    if n_frames == 0:
        return ExitMetrics()
    
    # Convert exit zone radius to pixels
    exit_zone_radius_px = exit_zone_radius_cm * px_per_cm
    
    # Calculate distance to exit for each frame (in pixels)
    dx = xy[:, 0] - exit_x
    dy = xy[:, 1] - exit_y
    distance_to_exit_px = np.sqrt(dx**2 + dy**2)
    
    # Convert to cm
    distance_to_exit_cm = distance_to_exit_px / px_per_cm
    
    # Determine which frames are in the exit zone
    in_exit_zone = distance_to_exit_px <= exit_zone_radius_px
    
    # Only consider valid frames
    valid_in_exit = in_exit_zone & valid
    
    # Calculate latency to first reach exit zone
    exit_frames = np.where(valid_in_exit)[0]
    if len(exit_frames) > 0:
        first_exit_frame = exit_frames[0]
        latency_to_exit_s = first_exit_frame / fps
    else:
        latency_to_exit_s = np.nan
        first_exit_frame = None
    
    # Calculate time in exit zone
    n_frames_in_exit = np.sum(valid_in_exit)
    time_in_exit_zone_s = n_frames_in_exit / fps
    
    # Calculate fraction of valid time in exit zone
    n_valid_frames = np.sum(valid)
    if n_valid_frames > 0:
        time_in_exit_zone_fraction = n_frames_in_exit / n_valid_frames
    else:
        time_in_exit_zone_fraction = 0.0
    
    # Calculate mean and min distance (over valid frames)
    valid_distances = distance_to_exit_cm[valid]
    if len(valid_distances) > 0:
        mean_distance_to_exit_cm = float(np.nanmean(valid_distances))
        min_distance_to_exit_cm = float(np.nanmin(valid_distances))
    else:
        mean_distance_to_exit_cm = np.nan
        min_distance_to_exit_cm = np.nan
    
    # Calculate path efficiency
    path_efficiency = _calculate_path_efficiency(
        xy, valid, exit_pos, px_per_cm
    )
    
    # Count exit zone entries
    n_exit_zone_entries = _count_zone_entries(in_exit_zone, valid)
    
    return ExitMetrics(
        latency_to_exit_s=latency_to_exit_s,
        time_in_exit_zone_s=time_in_exit_zone_s,
        time_in_exit_zone_fraction=time_in_exit_zone_fraction,
        mean_distance_to_exit_cm=mean_distance_to_exit_cm,
        min_distance_to_exit_cm=min_distance_to_exit_cm,
        path_efficiency=path_efficiency,
        n_exit_zone_entries=n_exit_zone_entries,
        distance_to_exit_per_frame=distance_to_exit_cm,
        in_exit_zone_per_frame=in_exit_zone,
    )


def _calculate_path_efficiency(
    xy: np.ndarray,
    valid: np.ndarray,
    exit_pos: tuple[float, float],
    px_per_cm: float,
) -> float:
    """
    Calculate path efficiency (straight-line / actual path).
    
    Path efficiency measures how directly the animal moved toward the exit.
    A value of 1.0 means the animal took the most direct path.
    
    Args:
        xy: Position array (n_frames, 2) in pixels
        valid: Boolean validity array
        exit_pos: Exit position in pixels
        px_per_cm: Calibration factor
        
    Returns:
        Path efficiency ratio (0.0 to 1.0, or NaN if insufficient data)
    """
    n_frames = len(xy)
    if n_frames < 2:
        return np.nan
    
    # Find first and last valid frames
    valid_indices = np.where(valid)[0]
    if len(valid_indices) < 2:
        return np.nan
    
    first_valid = valid_indices[0]
    # Get start and end positions
    start_pos = xy[first_valid]
    # Calculate straight-line distance from start to exit
    straight_line_to_exit = np.sqrt(
        (exit_pos[0] - start_pos[0])**2 + 
        (exit_pos[1] - start_pos[1])**2
    )
    
    # Calculate actual path distance
    dx = np.diff(xy[:, 0])
    dy = np.diff(xy[:, 1])
    step_distances = np.sqrt(dx**2 + dy**2)
    
    # Only count valid transitions
    valid_transitions = valid[:-1] & valid[1:]
    step_distances = np.where(valid_transitions, step_distances, 0.0)
    actual_path = np.sum(step_distances)
    
    # Calculate efficiency
    if actual_path > 0 and np.isfinite(straight_line_to_exit):
        # Cap at 1.0 (can't be more efficient than straight line)
        efficiency = min(1.0, straight_line_to_exit / actual_path)
        return float(efficiency)
    
    return np.nan


def _count_zone_entries(
    in_zone: np.ndarray,
    valid: np.ndarray,
) -> int:
    """
    Count the number of times the animal entered the zone.

    An entry is counted when transitioning from outside to inside.

    Args:
        in_zone: Boolean array indicating frames inside zone
        valid: Boolean validity array

    Returns:
        Number of zone entries
    """
    # Combine validity: only count transitions between valid frames
    valid_in_zone = in_zone & valid

    if len(valid_in_zone) < 2:
        return 0

    # Find transitions from outside (False) to inside (True)
    entries = np.sum(
        (~valid_in_zone[:-1]) & valid_in_zone[1:]
    )

    # Also count if starting in zone (first valid frame is in zone)
    valid_indices = np.where(valid)[0]
    if len(valid_indices) > 0:
        first_valid = valid_indices[0]
        if in_zone[first_valid]:
            entries += 1

    return int(entries)


def _count_zone_entries_with_debounce(
    in_zone: np.ndarray,
    valid: np.ndarray,
    fps: float,
    debounce_s: float,
) -> int:
    """
    Count zone entries with debounce: only count re-entry after being outside
    for at least debounce_s seconds (avoids overcounting brief exits).

    Args:
        in_zone: Boolean array indicating frames inside zone
        valid: Boolean validity array
        fps: Frame rate
        debounce_s: Minimum time (seconds) outside zone before next entry counts

    Returns:
        Number of debounced zone entries
    """
    valid_in_zone = in_zone & valid
    n = len(valid_in_zone)
    if n == 0:
        return 0
    debounce_frames = max(1, int(round(fps * debounce_s)))
    entries = 0
    last_exit_frame: Optional[int] = None
    valid_indices = np.where(valid)[0]
    if len(valid_indices) == 0:
        return 0
    first_valid = int(valid_indices[0])
    for i in range(1, n):
        if valid_in_zone[i - 1] and not valid_in_zone[i]:
            last_exit_frame = i
        if not valid_in_zone[i - 1] and valid_in_zone[i]:
            if last_exit_frame is None or (i - last_exit_frame) >= debounce_frames:
                entries += 1
    if in_zone[first_valid] and valid[first_valid]:
        entries += 1
    return int(entries)


@dataclass
class CenterMetrics:
    """Container for center-zone (arena center) metrics."""

    time_in_center_s: float = 0.0
    time_in_center_fraction: float = 0.0
    n_center_entries: int = 0


def calculate_center_metrics(
    xy: np.ndarray,
    valid: np.ndarray,
    arena_center_pos: tuple[float, float],
    px_per_cm: float,
    fps: float = DEFAULT_FPS,
    center_zone_radius_cm: float = CENTER_ZONE_RADIUS_CM,
    entry_debounce_s: float = CENTER_ENTRY_DEBOUNCE_S,
) -> CenterMetrics:
    """
    Compute time-in-center and center entries (with debounce) from position data.

    Center zone is a circle around the arena center. Entries are counted with
    debounce to avoid overcounting brief exits.

    Args:
        xy: Position array (n_frames, 2) in pixels
        valid: Boolean validity array
        arena_center_pos: (x, y) arena center in pixels
        px_per_cm: Calibration
        fps: Frame rate
        center_zone_radius_cm: Radius of center zone in cm
        entry_debounce_s: Min time outside center before re-entry counts

    Returns:
        CenterMetrics with time_in_center_s, time_in_center_fraction, n_center_entries
    """
    xy = np.asarray(xy, dtype=float)
    valid = np.asarray(valid, dtype=bool)
    cx, cy = arena_center_pos
    n_frames = len(xy)
    if n_frames == 0:
        return CenterMetrics()
    radius_px = center_zone_radius_cm * px_per_cm
    dx = xy[:, 0] - cx
    dy = xy[:, 1] - cy
    dist_px = np.sqrt(dx**2 + dy**2)
    in_center = dist_px <= radius_px
    valid_in_center = in_center & valid
    n_in = np.sum(valid_in_center)
    time_in_center_s = n_in / fps if fps > 0 else 0.0
    n_valid = np.sum(valid)
    time_in_center_fraction = (n_in / n_valid) if n_valid > 0 else 0.0
    n_center_entries = _count_zone_entries_with_debounce(
        in_center, valid, fps, entry_debounce_s
    )
    return CenterMetrics(
        time_in_center_s=time_in_center_s,
        time_in_center_fraction=time_in_center_fraction,
        n_center_entries=n_center_entries,
    )


def build_xy_table_with_exit(
    xy: np.ndarray,
    valid: np.ndarray,
    exit_pos: tuple[float, float],
    px_per_cm: float,
    fps: float,
    exit_zone_radius_cm: float = EXIT_ZONE_RADIUS_CM,
    is_moving: Optional[np.ndarray] = None,
    start_frame: int = 0,
    trial_start_frame: Optional[int] = None,
) -> np.ndarray:
    """
    Build structured XY table with exit-related columns.

    When start_frame > 0, frame_index stores original video frame indices
    (start_frame + i for row i); t_s is 0-based for the analysis window.

    Args:
        xy: Position array (n_frames, 2) in pixels (analysis window)
        valid: Boolean validity array
        exit_pos: Exit position in pixels
        px_per_cm: Calibration factor
        fps: Frame rate
        exit_zone_radius_cm: Exit zone radius in cm
        is_moving: Optional boolean array for movement status
        start_frame: Original video frame index of row 0 (for frame_index column)
        trial_start_frame: If set, frames before this (in row index) are "iti_wait", rest "run".

    Returns:
        Structured array matching xy_table_dtype from storage.h5_db
    """
    from ..storage.h5_db import xy_table_dtype

    n_frames = len(xy)
    exit_x, exit_y = exit_pos
    exit_zone_radius_px = exit_zone_radius_cm * px_per_cm

    # Calculate distances to exit (pixels)
    dx = xy[:, 0] - exit_x
    dy = xy[:, 1] - exit_y
    distance_to_exit_px = np.sqrt(dx**2 + dy**2)

    # In exit zone
    in_exit_zone = distance_to_exit_px <= exit_zone_radius_px

    # Create structured array
    table = np.zeros(n_frames, dtype=xy_table_dtype())

    table["frame_index"] = (start_frame + np.arange(n_frames, dtype=np.uint32)).astype(np.uint32)
    table["t_s"] = np.arange(n_frames, dtype=np.float64) / fps
    table['x'] = xy[:, 0].astype(np.float32)
    table['y'] = xy[:, 1].astype(np.float32)
    table['dist_to_exit_px'] = distance_to_exit_px.astype(np.float32)
    table['in_exit_zone'] = in_exit_zone.astype(np.uint8)
    table['valid'] = valid.astype(np.uint8)
    if is_moving is not None:
        table['is_moving'] = is_moving.astype(np.uint8)

    # Per-frame trial_state: iti_wait before trial_start_frame, run from trial_start_frame on.
    if trial_start_frame is not None and trial_start_frame > 0 and trial_start_frame < n_frames:
        table["trial_state"][:trial_start_frame] = b"iti_wait"
        table["trial_state"][trial_start_frame:] = b"run"
    else:
        table["trial_state"] = b"run"

    return table
