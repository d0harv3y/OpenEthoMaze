from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..pipeline.config import STANDARD_NODE_NAMES
from ..pipeline.io.file_discovery import TrialManifest
from ..pipeline.io.sleap_loader import apply_jump_filter, load_sleap_file
from ..pipeline.tracking.trace_processing import (
    TraceProcessingParams,
    filter_frames_no_animal,
    process_trace_data,
)


@dataclass(frozen=True)
class KpmsPreprocessConfig:
    """Preprocessing settings before kpMS formatting."""

    min_fragment_frames: int = 4
    jump_filter_cm: float = 15.0
    jump_filter_lookahead_frames: int = 3
    px_per_cm: float = 2.42


def build_kpms_inputs(
    manifests: list[TrialManifest],
    cfg: KpmsPreprocessConfig,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], list[str], list[str]]:
    """
    Convert trial manifests into kpMS-ready coordinates/confidences.

    Returns:
      (coordinates, confidences, bodyparts, skipped_trial_keys)
    """
    coordinates: dict[str, np.ndarray] = {}
    confidences: dict[str, np.ndarray] = {}
    skipped: list[str] = []

    for m in manifests:
        trial_key = f"{m.animal_id}-{m.session}-{m.trial}"
        if m.sleap_path is None:
            skipped.append(f"{trial_key}:missing_sleap")
            continue
        sleap_path = Path(m.sleap_path)
        trace = load_sleap_file(sleap_path)
        if trace is None:
            skipped.append(f"{trial_key}:failed_load")
            continue

        trace = apply_jump_filter(
            trace,
            max_jump_cm=cfg.jump_filter_cm,
            px_per_cm=cfg.px_per_cm,
            lookahead_frames=cfg.jump_filter_lookahead_frames,
        )

        processed = process_trace_data(
            trace.traces,
            trace.node_names,
            TraceProcessingParams(),
        )
        valid_frames = filter_frames_no_animal(trace.traces, trace.n_frames)

        arr_xy, arr_conf = _stack_nodes(processed, trace.n_frames)
        keep = valid_frames & np.isfinite(arr_xy).all(axis=(1, 2))

        if int(keep.sum()) < cfg.min_fragment_frames:
            skipped.append(f"{trial_key}:too_short_after_filter")
            continue

        coordinates[trial_key] = arr_xy[keep]
        confidences[trial_key] = arr_conf[keep]

    return coordinates, confidences, STANDARD_NODE_NAMES.copy(), skipped


def _stack_nodes(
    processed_traces: dict[str, dict[str, np.ndarray]],
    n_frames: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Stack pipeline traces into kpMS tensor shapes."""
    k = len(STANDARD_NODE_NAMES)
    xy = np.full((n_frames, k, 2), np.nan, dtype=np.float32)
    conf = np.zeros((n_frames, k), dtype=np.float32)

    for i, node_name in enumerate(STANDARD_NODE_NAMES):
        node = processed_traces.get(node_name)
        if node is None:
            continue
        x = np.asarray(node.get("x"), dtype=np.float32)
        y = np.asarray(node.get("y"), dtype=np.float32)
        score = np.asarray(node.get("score"), dtype=np.float32)
        if x.shape[0] != n_frames or y.shape[0] != n_frames or score.shape[0] != n_frames:
            continue
        xy[:, i, 0] = x
        xy[:, i, 1] = y
        conf[:, i] = score
    return xy, conf

