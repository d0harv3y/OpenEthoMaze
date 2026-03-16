"""
Trace processing module for VAST pipeline.

Handles:
- NaN interpolation for short gaps
- Low-confidence interpolation
- Temporal smoothing (moving average)
- Frame filtering (remove frames with no animal)

Ported from ehram pipeline with VAST-specific adaptations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..config import (
    IN_RANGE_POINT_NAME,
    TRACE_INTERPOLATE_NANS,
    TRACE_MAX_GAP_FRAMES,
    TRACE_INTERPOLATE_LOW_CONF,
    TRACE_CONFIDENCE_THRESHOLD,
    TRACE_APPLY_SMOOTHING,
    TRACE_SMOOTHING_WINDOW,
    MIN_CONFIDENT_NODES_PER_FRAME,
    MIN_NODE_CONFIDENCE_THRESHOLD,
    MIN_VALID_FRAME_RUN_LENGTH,
    STANDARD_NODE_NAMES,
    MIN_MEAN_CONFIDENCE_PER_FRAME,
)


@dataclass(frozen=True)
class TraceProcessingParams:
    """Parameters for trace processing."""
    
    interpolate_nans: bool = TRACE_INTERPOLATE_NANS
    max_gap_frames: int = TRACE_MAX_GAP_FRAMES
    interpolate_low_conf: bool = TRACE_INTERPOLATE_LOW_CONF
    confidence_threshold: float = TRACE_CONFIDENCE_THRESHOLD
    apply_smoothing: bool = TRACE_APPLY_SMOOTHING
    smoothing_window: int = TRACE_SMOOTHING_WINDOW


def process_xy_trace(
    xy: np.ndarray,
    valid: np.ndarray,
    score: Optional[np.ndarray] = None,
    params: Optional[TraceProcessingParams] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Apply trace processing pipeline:
      1) Interpolate NaN/invalid gaps (<= max_gap_frames)
      2) Interpolate low-confidence gaps when scores provided
      3) Moving average smoothing with NaN-safe averaging

    Args:
        xy: (F, 2) array of coordinates
        valid: (F,) boolean array indicating valid frames
        score: Optional (F,) array of confidence scores
        params: Processing parameters (uses config defaults if None)

    Returns:
        Tuple of (xy_processed, valid_processed) where valid_processed
        indicates finite coordinates.
    """
    if params is None:
        params = TraceProcessingParams()
    
    xy0 = np.asarray(xy, dtype=float)
    v0 = np.asarray(valid, dtype=bool)
    
    if xy0.ndim != 2 or xy0.shape[1] != 2:
        raise ValueError("xy must be (F, 2)")
    
    n_frames = xy0.shape[0]
    
    x = xy0[:, 0].copy()
    y = xy0[:, 1].copy()

    # Mark invalid as NaN so interpolation can operate
    x[~v0] = np.nan
    y[~v0] = np.nan

    # Step 1: Interpolate NaN gaps
    if params.interpolate_nans:
        x = _interp_short_gaps_1d(x, max_gap=params.max_gap_frames)
        y = _interp_short_gaps_1d(y, max_gap=params.max_gap_frames)

    # Step 2: Interpolate low-confidence detections
    if params.interpolate_low_conf and score is not None:
        sc = np.asarray(score, dtype=float)
        if sc.shape[0] == n_frames:
            low_conf = sc < params.confidence_threshold
            x = _interp_short_gaps_1d(
                np.where(low_conf, np.nan, x),
                max_gap=params.max_gap_frames
            )
            y = _interp_short_gaps_1d(
                np.where(low_conf, np.nan, y),
                max_gap=params.max_gap_frames
            )

    # Step 3: Temporal smoothing
    if params.apply_smoothing and params.smoothing_window >= 3:
        x = _nan_safe_moving_average_1d(x, window=params.smoothing_window)
        y = _nan_safe_moving_average_1d(y, window=params.smoothing_window)

    xy_out = np.stack([x, y], axis=1).astype(float)
    valid_out = np.isfinite(xy_out[:, 0]) & np.isfinite(xy_out[:, 1])
    
    return xy_out, valid_out


def _interp_short_gaps_1d(values: np.ndarray, max_gap: int) -> np.ndarray:
    """
    Linear-interpolate NaN runs of length <= max_gap when bounded by finite endpoints.
    
    Args:
        values: 1D array with potential NaN gaps
        max_gap: Maximum gap length to interpolate
        
    Returns:
        Array with short gaps filled via linear interpolation
    """
    v = np.asarray(values, dtype=float).copy()
    n = len(v)
    
    if n == 0:
        return v
    
    nan_mask = ~np.isfinite(v)
    if not np.any(nan_mask):
        return v

    # Find indices of NaN values
    nan_idxs = np.where(nan_mask)[0]
    if len(nan_idxs) == 0:
        return v

    # Group consecutive NaN indices into gaps
    gaps = []
    current_gap = [int(nan_idxs[0])]
    
    for i in range(1, len(nan_idxs)):
        if nan_idxs[i] == nan_idxs[i - 1] + 1:
            current_gap.append(int(nan_idxs[i]))
        else:
            if len(current_gap) <= max_gap:
                gaps.append(current_gap)
            current_gap = [int(nan_idxs[i])]
    
    # Don't forget the last gap
    if len(current_gap) <= max_gap:
        gaps.append(current_gap)

    # Interpolate each qualifying gap
    for gap in gaps:
        start_idx = gap[0] - 1
        end_idx = gap[-1] + 1
        
        # Need valid endpoints on both sides
        if start_idx < 0 or end_idx >= n:
            continue
        
        a = v[start_idx]
        b = v[end_idx]
        
        if not (np.isfinite(a) and np.isfinite(b)):
            continue
        
        # Linear interpolation
        gap_len = len(gap)
        for j, gi in enumerate(gap):
            alpha = (j + 1) / (gap_len + 1)
            v[gi] = a * (1.0 - alpha) + b * alpha
    
    return v


def _nan_safe_moving_average_1d(values: np.ndarray, window: int) -> np.ndarray:
    """
    Moving average that ignores NaNs in the computation.
    
    Args:
        values: Input array
        window: Smoothing window size
        
    Returns:
        Smoothed array
    """
    v = np.asarray(values, dtype=float)
    n = len(v)
    
    if n == 0 or window <= 1:
        return v.copy()

    # When input is shorter than the window, convolve(..., mode="same") returns
    # length max(n, window), so we must use that size for the divide output.
    if n < window:
        return v.copy()

    # Create mask for finite values
    mask = np.isfinite(v).astype(float)
    v_filled = np.where(np.isfinite(v), v, 0.0)
    
    # Convolution for moving average
    kernel = np.ones(window, dtype=float)
    numerator = np.convolve(v_filled, kernel, mode="same")
    denominator = np.convolve(mask, kernel, mode="same")
    
    # out must match numerator shape (convolve "same" can exceed n when n >= window in edge cases; typically equals n)
    out_len = len(numerator)
    out = np.full(out_len, np.nan, dtype=float)
    np.divide(numerator, denominator, out=out, where=(denominator > 0))
    out = out[:n].copy()

    # Preserve edge values (don't smooth edges)
    edge = window // 2
    if edge > 0 and n >= window:
        out[:edge] = v[:edge]
        out[n - edge:] = v[n - edge:]
    
    return out


def filter_frames_no_animal(
    traces: dict[str, dict[str, np.ndarray]],
    n_frames: int,
    min_confident_nodes: int = MIN_CONFIDENT_NODES_PER_FRAME,
    min_confidence: float = MIN_NODE_CONFIDENCE_THRESHOLD,
    min_valid_run_length: int = MIN_VALID_FRAME_RUN_LENGTH,
    min_mean_confidence: Optional[float] = MIN_MEAN_CONFIDENCE_PER_FRAME,
) -> np.ndarray:
    """
    Identify frames where no animal is present (or confidence too low).
    
    Uses:
    1. Minimum number of confident nodes per frame (individual nodes, not average).
    2. Optional: reject frame if mean(all node confidences) < min_mean_confidence.
    3. Temporal consistency - reject isolated valid frames.
    
    Args:
        traces: Dictionary of node traces from TraceData.traces
        n_frames: Total number of frames
        min_confident_nodes: Minimum nodes with confidence >= threshold
        min_confidence: Confidence threshold
        min_valid_run_length: Minimum consecutive valid frames
        min_mean_confidence: If set, also require mean(node scores) >= this per frame
    
    Returns:
        Boolean array - True for frames to keep, False to discard
    """
    if n_frames == 0:
        return np.array([], dtype=bool)
    
    # Count confident nodes per frame; optionally compute mean confidence per frame
    # Include STANDARD_NODE_NAMES and in-range (controller/legacy fallback) when present
    confident_nodes_per_frame = np.zeros(n_frames, dtype=int)
    sum_score_per_frame = np.zeros(n_frames, dtype=float)
    n_nodes_with_score = np.zeros(n_frames, dtype=int)
    nodes_to_count = list(STANDARD_NODE_NAMES)
    if IN_RANGE_POINT_NAME in traces:
        nodes_to_count = nodes_to_count + [IN_RANGE_POINT_NAME]

    for node_name in nodes_to_count:
        if node_name not in traces:
            continue

        node = traces[node_name]
        score = node.get("score")
        # Cast visible to boolean so logical ops always work, even if stored as 0/1 floats
        visible = np.asarray(node.get("visible", np.ones(n_frames, dtype=bool)), dtype=bool)

        if score is not None:
            score_arr = np.asarray(score, dtype=float)
            confident_mask = (score_arr >= min_confidence) & visible
            confident_nodes_per_frame[confident_mask] += 1
            sum_score_per_frame += np.where(np.isfinite(score_arr), score_arr, 0.0)
            n_nodes_with_score += np.isfinite(score_arr).astype(int)
        else:
            confident_nodes_per_frame[visible] += 1

    # When only in-range (no standard nodes) is present, require at least 1 confident node
    effective_min = min_confident_nodes
    if IN_RANGE_POINT_NAME in traces and not any(n in traces for n in STANDARD_NODE_NAMES):
        effective_min = 1
    # Criterion 1: Frames with enough confident nodes
    frames_with_enough_nodes = confident_nodes_per_frame >= effective_min
    
    # Criterion 1b: Optional mean confidence per frame (for noisier / OOD model data)
    if min_mean_confidence is not None and min_mean_confidence > 0 and np.any(n_nodes_with_score > 0):
        mean_conf = np.where(n_nodes_with_score > 0, sum_score_per_frame / n_nodes_with_score, 0.0)
        frames_with_enough_nodes = frames_with_enough_nodes & (mean_conf >= min_mean_confidence)
    
    # Criterion 2: Temporal consistency - remove isolated valid frames
    if min_valid_run_length > 1:
        valid_runs = _find_valid_runs(frames_with_enough_nodes, min_valid_run_length)
        valid_frames = np.zeros(n_frames, dtype=bool)
        for start, end in valid_runs:
            valid_frames[start:end] = True
    else:
        valid_frames = frames_with_enough_nodes
    
    return valid_frames


def _find_valid_runs(
    valid_mask: np.ndarray,
    min_length: int
) -> list[tuple[int, int]]:
    """
    Find runs of consecutive True values >= min_length.
    
    Returns:
        List of (start, end) tuples (end is exclusive)
    """
    if not np.any(valid_mask):
        return []
    
    runs = []
    in_run = False
    run_start = 0
    
    for i in range(len(valid_mask)):
        if valid_mask[i]:
            if not in_run:
                run_start = i
                in_run = True
        else:
            if in_run:
                run_end = i
                if run_end - run_start >= min_length:
                    runs.append((run_start, run_end))
                in_run = False
    
    # Handle run at end of array
    if in_run:
        run_end = len(valid_mask)
        if run_end - run_start >= min_length:
            runs.append((run_start, run_end))
    
    return runs


def process_trace_data(
    traces: dict[str, dict[str, np.ndarray]],
    node_names: list[str],
    params: Optional[TraceProcessingParams] = None,
) -> dict[str, dict[str, np.ndarray]]:
    """
    Process all traces in a TraceData-like dictionary.
    
    Args:
        traces: Dictionary mapping node names to trace data
        node_names: List of node names to process
        params: Processing parameters
        
    Returns:
        Processed traces dictionary
    """
    if params is None:
        params = TraceProcessingParams()
    
    processed = {}
    
    for node_name in node_names:
        if node_name not in traces:
            continue
        
        node = traces[node_name]
        x = node['x']
        y = node['y']
        score = node.get('score')
        visible = node.get('visible', np.ones(len(x), dtype=bool))
        
        # Create XY array
        xy = np.column_stack([x, y])
        
        # Process
        xy_processed, valid_processed = process_xy_trace(
            xy, visible, score, params
        )
        
        processed[node_name] = {
            'x': xy_processed[:, 0].astype(np.float32),
            'y': xy_processed[:, 1].astype(np.float32),
            'score': score if score is not None else np.ones(len(x), dtype=np.float32),
            'visible': valid_processed,
        }
    
    return processed
