from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..core.anatomy import BLOB_NODE_NAMES, STANDARD_NODE_NAMES
from ..pipeline.db.trial_key import TrialKey
from ..pipeline.io.file_discovery import TrialManifest
from ..pipeline.io.sleap_loader import TraceData, apply_jump_filter, load_sleap_file
from ..pipeline.tracking.trace_processing import (
    TraceProcessingParams,
    filter_frames_no_animal,
    process_trace_data,
)
from .h5_pose import (
    AnatomicalPoseLoad,
    BlobPoseLoad,
    load_anatomical_from_h5,
    load_blob_from_h5,
    resolve_canonical_trial_h5,
)
from .heading_idxs import PoseStream


@dataclass(frozen=True)
class KpmsPreprocessConfig:
    """Preprocessing settings before kpMS formatting."""

    min_fragment_frames: int = 4
    jump_filter_cm: float = 15.0
    jump_filter_lookahead_frames: int = 3
    px_per_cm: float = 2.42
    #: If True, keep every video frame in coordinates (NaN where invalid) so time axes
    #: match full-length kpMS ``results.h5`` / native fits. Default False matches ORM fit/apply.
    retain_all_frames: bool = False
    #: Results / cohort HDF5 passed to apply or fit; used when ``input_h5_path`` is empty.
    db_path: Path | None = None
    #: Pose stream: anatomical (A), blob (B), fused (C = A∥B).
    pose_stream: PoseStream = "anatomical"


def _effective_db_path(cfg: KpmsPreprocessConfig) -> Path:
    return Path(cfg.db_path) if cfg.db_path is not None else Path("")


def _bodyparts_for_stream(pose_stream: PoseStream) -> tuple[str, ...]:
    if pose_stream == "blob":
        return BLOB_NODE_NAMES
    if pose_stream == "fused":
        return STANDARD_NODE_NAMES + BLOB_NODE_NAMES
    return STANDARD_NODE_NAMES


_FusedStreamTensors = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]


def build_kpms_inputs(
    manifests: list[TrialManifest],
    cfg: KpmsPreprocessConfig,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], list[str], list[str]]:
    """
    Convert trial manifests into kpMS-ready coordinates/confidences.

    Stream A (``pose_stream='anatomical'``): read order per trial is
    ``tracking/anatomical`` in canonical trial H5, then ``sleap_path`` sidecar,
    else skip with ``missing_pose``.

    Stream B (``pose_stream='blob'``): ``tracking/blob`` in canonical trial H5 only;
    no sleap fallback.

    Stream C (``pose_stream='fused'``): concatenate anatomical + blob per ``frame_index``.
    Missing stream halves are ``NaN`` coordinates with zero confidence.

    Returns:
      (coordinates, confidences, bodyparts, skipped_trial_keys)
    """
    coordinates: dict[str, np.ndarray] = {}
    confidences: dict[str, np.ndarray] = {}
    skipped: list[str] = []
    db_path = _effective_db_path(cfg)
    bodyparts = list(_bodyparts_for_stream(cfg.pose_stream))

    for m in manifests:
        trial_key = m.kpms_results_dict_key
        loaded = _load_pose_for_manifest(m, db_path, cfg)
        if isinstance(loaded, str):
            skipped.append(f"{trial_key}:{loaded}")
            continue

        arr_xy, arr_conf, keep = loaded
        if int(keep.sum()) < cfg.min_fragment_frames:
            skipped.append(f"{trial_key}:too_short_after_filter")
            continue

        if cfg.retain_all_frames:
            coordinates[trial_key] = arr_xy
            confidences[trial_key] = arr_conf
        else:
            coordinates[trial_key] = arr_xy[keep]
            confidences[trial_key] = arr_conf[keep]

    return coordinates, confidences, bodyparts, skipped


def _load_pose_for_manifest(
    manifest: TrialManifest,
    db_path: Path,
    cfg: KpmsPreprocessConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | str:
    """Return ``(xy, conf, keep)`` or a skip reason string."""
    if cfg.pose_stream == "fused":
        return _load_fused_for_manifest(manifest, db_path, cfg)
    if cfg.pose_stream == "blob":
        return _load_blob_for_manifest(manifest, db_path, cfg)
    return _load_anatomical_for_manifest(manifest, db_path, cfg)


def _load_fused_for_manifest(
    manifest: TrialManifest,
    db_path: Path,
    cfg: KpmsPreprocessConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | str:
    anat = _try_load_anatomical_tensors(manifest, db_path, cfg)
    blob = _try_load_blob_tensors(manifest, db_path, cfg)
    if anat is None and blob is None:
        return "missing_pose"
    return _fuse_anatomical_blob_tensors(anat, blob)


def _try_load_anatomical_tensors(
    manifest: TrialManifest,
    db_path: Path,
    cfg: KpmsPreprocessConfig,
) -> _FusedStreamTensors | None:
    """Return ``(frame_index, xy, conf, row_keep)`` for stream A, or ``None``."""
    canonical = resolve_canonical_trial_h5(manifest, db_path, pose_stream="anatomical")
    if canonical is not None:
        key = TrialKey(
            animal_id=str(manifest.animal_id),
            session=str(manifest.h5_session),
            trial=str(manifest.trial),
        )
        pose = load_anatomical_from_h5(canonical, key)
        if pose is not None:
            arr_xy, arr_conf, keep = _preprocess_h5_pose(pose, cfg)
            return (
                np.asarray(pose.frame_index, dtype=np.uint32),
                arr_xy,
                arr_conf,
                keep,
            )

    if manifest.sleap_path is None:
        return None

    trace = load_sleap_file(Path(manifest.sleap_path))
    if trace is None:
        return None

    arr_xy, arr_conf, keep = _preprocess_sleap_trace(trace, cfg)
    frame_index = np.arange(arr_xy.shape[0], dtype=np.uint32)
    return frame_index, arr_xy, arr_conf, keep


def _try_load_blob_tensors(
    manifest: TrialManifest,
    db_path: Path,
    cfg: KpmsPreprocessConfig,
) -> _FusedStreamTensors | None:
    """Return ``(frame_index, xy, conf, row_keep)`` for stream B, or ``None``."""
    canonical = resolve_canonical_trial_h5(manifest, db_path, pose_stream="blob")
    if canonical is None:
        return None

    key = TrialKey(
        animal_id=str(manifest.animal_id),
        session=str(manifest.h5_session),
        trial=str(manifest.trial),
    )
    pose = load_blob_from_h5(canonical, key)
    if pose is None:
        return None

    arr_xy, arr_conf, keep = _preprocess_h5_blob(pose, cfg)
    return (
        np.asarray(pose.frame_index, dtype=np.uint32),
        arr_xy,
        arr_conf,
        keep,
    )


def _fuse_anatomical_blob_tensors(
    anat: _FusedStreamTensors | None,
    blob: _FusedStreamTensors | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Align streams on sorted union of ``frame_index``; concatenate A∥B (K=16).

    Missing stream rows at a shared frame index leave that half as NaN / conf 0.
    """
    k_anat = len(STANDARD_NODE_NAMES)
    k_blob = len(BLOB_NODE_NAMES)
    k_total = k_anat + k_blob

    frame_parts: list[np.ndarray] = []
    if anat is not None:
        frame_parts.append(np.asarray(anat[0], dtype=np.uint32).reshape(-1))
    if blob is not None:
        frame_parts.append(np.asarray(blob[0], dtype=np.uint32).reshape(-1))
    union_fi = np.unique(np.concatenate(frame_parts))
    union_fi.sort()
    t = int(union_fi.shape[0])

    fused_xy = np.full((t, k_total, 2), np.nan, dtype=np.float32)
    fused_conf = np.zeros((t, k_total), dtype=np.float32)
    fused_keep = np.zeros(t, dtype=bool)

    if anat is not None:
        a_fi, a_xy, a_conf, a_keep = anat
        src_map = {int(f): i for i, f in enumerate(np.asarray(a_fi, dtype=np.uint32).reshape(-1))}
        for out_i, fi in enumerate(union_fi):
            src_i = src_map.get(int(fi))
            if src_i is None:
                continue
            fused_xy[out_i, :k_anat] = a_xy[src_i]
            fused_conf[out_i, :k_anat] = a_conf[src_i]
            if a_keep[src_i]:
                fused_keep[out_i] = True

    if blob is not None:
        b_fi, b_xy, b_conf, b_keep = blob
        src_map = {int(f): i for i, f in enumerate(np.asarray(b_fi, dtype=np.uint32).reshape(-1))}
        for out_i, fi in enumerate(union_fi):
            src_i = src_map.get(int(fi))
            if src_i is None:
                continue
            fused_xy[out_i, k_anat:] = b_xy[src_i]
            fused_conf[out_i, k_anat:] = b_conf[src_i]
            if b_keep[src_i]:
                fused_keep[out_i] = True

    return fused_xy, fused_conf, fused_keep


def _load_blob_for_manifest(
    manifest: TrialManifest,
    db_path: Path,
    cfg: KpmsPreprocessConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | str:
    canonical = resolve_canonical_trial_h5(manifest, db_path, pose_stream="blob")
    if canonical is None:
        return "missing_pose"

    key = TrialKey(
        animal_id=str(manifest.animal_id),
        session=str(manifest.h5_session),
        trial=str(manifest.trial),
    )
    pose = load_blob_from_h5(canonical, key)
    if pose is None:
        return "missing_pose"
    return _preprocess_h5_blob(pose, cfg)


def _load_anatomical_for_manifest(
    manifest: TrialManifest,
    db_path: Path,
    cfg: KpmsPreprocessConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | str:
    canonical = resolve_canonical_trial_h5(manifest, db_path, pose_stream="anatomical")
    if canonical is not None:
        key = TrialKey(
            animal_id=str(manifest.animal_id),
            session=str(manifest.h5_session),
            trial=str(manifest.trial),
        )
        pose = load_anatomical_from_h5(canonical, key)
        if pose is not None:
            return _preprocess_h5_pose(pose, cfg)

    if manifest.sleap_path is None:
        return "missing_pose"

    trace = load_sleap_file(Path(manifest.sleap_path))
    if trace is None:
        return "failed_load"

    return _preprocess_sleap_trace(trace, cfg)


def _preprocess_sleap_trace(
    trace: TraceData,
    cfg: KpmsPreprocessConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
    arr_xy, arr_conf = _stack_anatomical_nodes(processed, trace.n_frames)
    valid_frames = filter_frames_no_animal(trace.traces, trace.n_frames)
    keep = valid_frames & np.isfinite(arr_xy).all(axis=(1, 2))
    return arr_xy, arr_conf, keep


def _preprocess_h5_pose(
    pose: AnatomicalPoseLoad,
    cfg: KpmsPreprocessConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    traces, node_names, n_frames = _anatomical_pose_to_traces(pose)
    if pose.pose_source != "sleap_live":
        trace = TraceData(traces=traces, node_names=node_names, n_frames=n_frames)
        trace = apply_jump_filter(
            trace,
            max_jump_cm=cfg.jump_filter_cm,
            px_per_cm=cfg.px_per_cm,
            lookahead_frames=cfg.jump_filter_lookahead_frames,
        )
        traces = trace.traces
        node_names = trace.node_names
        n_frames = trace.n_frames

    processed = process_trace_data(traces, node_names, TraceProcessingParams())
    arr_xy, arr_conf = _stack_anatomical_nodes(processed, n_frames)
    valid_frames = filter_frames_no_animal(traces, n_frames)
    keep = valid_frames & np.isfinite(arr_xy).all(axis=(1, 2))
    return arr_xy, arr_conf, keep


def _preprocess_h5_blob(
    pose: BlobPoseLoad,
    cfg: KpmsPreprocessConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    del cfg  # blob stream skips jump filter and trace processing
    n_frames = int(pose.coordinates.shape[0])
    k = len(BLOB_NODE_NAMES)
    arr_xy = _stack_blob_nodes(pose.coordinates, pose.node_names, n_frames)
    frame_score = np.asarray(pose.confidences, dtype=np.float32).reshape(-1)
    arr_conf = np.broadcast_to(frame_score[:, None], (n_frames, k)).copy()
    valid = np.asarray(pose.valid, dtype=np.uint8).reshape(-1)
    invalid_frame = valid == 0
    arr_xy[invalid_frame] = np.nan
    arr_conf[invalid_frame] = 0.0
    invalid_xy = ~np.isfinite(arr_xy).all(axis=(1, 2))
    arr_conf[invalid_xy] = 0.0
    keep = (valid > 0) & np.isfinite(arr_xy).all(axis=(1, 2))
    return arr_xy, arr_conf, keep


def _anatomical_pose_to_traces(
    pose: AnatomicalPoseLoad,
) -> tuple[dict[str, dict[str, np.ndarray]], list[str], int]:
    n_frames = int(pose.frame_index.shape[0])
    traces: dict[str, dict[str, np.ndarray]] = {}
    for j, name in enumerate(pose.node_names):
        visible = np.isfinite(pose.coordinates[:, j, :]).all(axis=1)
        if pose.valid is not None:
            visible = visible & (pose.valid[:, j] > 0)
        traces[str(name)] = {
            "x": np.asarray(pose.coordinates[:, j, 0], dtype=np.float32),
            "y": np.asarray(pose.coordinates[:, j, 1], dtype=np.float32),
            "score": np.asarray(pose.confidences[:, j], dtype=np.float32),
            "visible": visible.astype(bool),
        }
    return traces, [str(n) for n in pose.node_names], n_frames


def _stack_anatomical_nodes(
    processed_traces: dict[str, dict[str, np.ndarray]],
    n_frames: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Stack pipeline traces into kpMS tensor shapes for stream A."""
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


def _stack_blob_nodes(
    coordinates: np.ndarray,
    node_names: tuple[str, ...] | list[str],
    n_frames: int,
) -> np.ndarray:
    """Align blob H5 coordinates to canonical ``BLOB_NODE_NAMES`` order."""
    k = len(BLOB_NODE_NAMES)
    xy = np.full((n_frames, k, 2), np.nan, dtype=np.float32)
    name_to_src = {str(name): i for i, name in enumerate(node_names)}
    for i, node_name in enumerate(BLOB_NODE_NAMES):
        src = name_to_src.get(node_name)
        if src is None:
            continue
        pts = np.asarray(coordinates[:, src, :], dtype=np.float32)
        if pts.shape != (n_frames, 2):
            continue
        xy[:, i, :] = pts
    return xy
