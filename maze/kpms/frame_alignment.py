"""Map kpMS syllable timepoints back to source (video/SLEAP) frame indices.

Mirrors :func:`maze.kpms.preprocess.build_kpms_inputs` plus the post-steps in
:func:`maze.kpms.apply.apply_kpms_checkpoint_from_manifests` (interpolate NaNs,
confidence fragment filter) so indices align with ``results_apply.h5`` syllable rows.
"""

from __future__ import annotations

from pathlib import Path
from typing import MutableMapping

import numpy as np

from ..pipeline.io.file_discovery import TrialManifest
from ..pipeline.io.sleap_loader import apply_jump_filter, load_sleap_file
from ..pipeline.tracking.trace_processing import (
    TraceProcessingParams,
    filter_frames_no_animal,
    process_trace_data,
)
from .apply import filter_low_confidence_fragments, interpolate_nans_in_coordinates
from .preprocess import KpmsPreprocessConfig, _stack_anatomical_nodes


def kpms_recording_key(manifest: TrialManifest) -> str:
    """HDF5 group name for one trial in kpMS results (matches preprocess)."""
    return manifest.kpms_results_dict_key


def kpms_aligned_coordinates_and_indices(
    manifest: TrialManifest,
    pre_cfg: KpmsPreprocessConfig,
    *,
    conf_threshold: float = 0.2,
    min_points_per_frame: int = 3,
    min_fragment_frames: int = 4,
) -> tuple[str, np.ndarray, np.ndarray] | None:
    """
    Return ``(recording_key, coordinates, source_frame_indices)``.

    ``coordinates`` matches the kpMS apply input tensor for this recording;
    ``source_frame_indices`` maps each row to the original video/SLEAP frame index.
    """
    if manifest.sleap_path is None:
        return None
    sleap_path = Path(manifest.sleap_path)
    trace = load_sleap_file(sleap_path)
    if trace is None:
        return None

    trace = apply_jump_filter(
        trace,
        max_jump_cm=pre_cfg.jump_filter_cm,
        px_per_cm=pre_cfg.px_per_cm,
        lookahead_frames=pre_cfg.jump_filter_lookahead_frames,
    )
    processed = process_trace_data(
        trace.traces,
        trace.node_names,
        TraceProcessingParams(),
    )
    valid_frames = filter_frames_no_animal(trace.traces, trace.n_frames)
    arr_xy, arr_conf = _stack_anatomical_nodes(processed, trace.n_frames)
    keep = valid_frames & np.isfinite(arr_xy).all(axis=(1, 2))
    if int(keep.sum()) < pre_cfg.min_fragment_frames:
        return None

    idx = np.flatnonzero(keep).astype(np.int64, copy=False)
    coord = arr_xy[keep]
    conf = arr_conf[keep]

    key = kpms_recording_key(manifest)
    coords_map: MutableMapping[str, np.ndarray] = {key: coord}
    conf_map: MutableMapping[str, np.ndarray] = {key: conf}
    interpolate_nans_in_coordinates(coords_map)
    filter_low_confidence_fragments(
        coords_map,
        conf_map,
        conf_thresh=conf_threshold,
        min_points=min_points_per_frame,
        min_fragment=min_fragment_frames,
    )
    if key not in coords_map:
        return None

    conf2 = conf_map[key]
    valid2 = (conf2 >= conf_threshold).sum(axis=1) >= min_points_per_frame
    if int(valid2.sum()) < min_fragment_frames:
        return None
    return key, coords_map[key], idx[valid2]


def kpms_source_frame_indices_after_apply_filters(
    manifest: TrialManifest,
    pre_cfg: KpmsPreprocessConfig,
    *,
    conf_threshold: float = 0.2,
    min_points_per_frame: int = 3,
    min_fragment_frames: int = 4,
) -> np.ndarray | None:
    """
    Return shape ``(T,)`` source frame indices into the original SLEAP/video timeline.

    ``T`` matches the syllable sequence length for this recording in apply output
    when the same preprocess/apply thresholds were used.

    Returns:
        Integer indices, or None if this trial would be skipped by preprocess/apply.
    """
    out = kpms_aligned_coordinates_and_indices(
        manifest,
        pre_cfg,
        conf_threshold=conf_threshold,
        min_points_per_frame=min_points_per_frame,
        min_fragment_frames=min_fragment_frames,
    )
    if out is None:
        return None
    return out[2]
