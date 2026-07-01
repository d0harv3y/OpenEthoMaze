"""Skeleton pose for unified overlay: H5 ``tracking/anatomical`` first, SLEAP sidecar fallback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

import numpy as np

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.kpms.h5_pose import AnatomicalPoseLoad, load_anatomical_from_h5, resolve_canonical_trial_h5
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.io.sleap_loader import TraceData, apply_jump_filter, get_skeleton_edges, load_sleap_file
from maze.pipeline.tracking.trace_processing import TraceProcessingParams, process_trace_data
from maze.pipeline.viz.overlay_frame_align import xy_rows_for_source_frames
from maze.pipeline.viz.overlay_provenance import OverlayPoseProvenance


@dataclass(frozen=True)
class OverlaySkeleton:
    nodes: dict[str, dict[str, np.ndarray]]
    edges: list[tuple[int, int]]


@dataclass(frozen=True)
class OverlaySkeletonLoad:
    skeleton: OverlaySkeleton | None
    pose: OverlayPoseProvenance


def resolve_overlay_tracking_h5(
    manifest: TrialManifest,
    pipeline_db: Path,
    tracking_db: Path | None,
) -> Path | None:
    """Resolve canonical trial H5 with ``tracking/anatomical`` (contract read order)."""
    path = resolve_canonical_trial_h5(manifest, pipeline_db)
    if path is not None:
        return path
    if tracking_db is not None:
        return resolve_canonical_trial_h5(manifest, tracking_db)
    return None


def _anatomical_to_trace_data(pose: AnatomicalPoseLoad) -> TraceData:
    t = int(pose.coordinates.shape[0])
    k = int(pose.coordinates.shape[1])
    traces: dict[str, dict[str, np.ndarray]] = {}
    for i, name in enumerate(pose.node_names):
        if i >= k:
            break
        visible = np.ones(t, dtype=bool)
        if pose.valid is not None:
            visible = np.asarray(pose.valid, dtype=bool)
        conf = pose.confidences
        score = conf[:, i] if conf.ndim == 2 else conf
        traces[name] = {
            "x": np.asarray(pose.coordinates[:, i, 0], dtype=np.float64),
            "y": np.asarray(pose.coordinates[:, i, 1], dtype=np.float64),
            "score": np.asarray(score, dtype=np.float32),
            "visible": visible,
        }
    return TraceData(
        traces=traces,
        node_names=list(pose.node_names),
        n_frames=t,
        fps=float(pose.fps),
    )


def _sample_processed_traces_for_overlay(
    processed: dict[str, dict[str, np.ndarray]],
    node_names: Sequence[str],
    fi_rows: np.ndarray,
    render_start_frame: int,
    max_frames: int,
) -> dict[str, dict[str, np.ndarray]] | None:
    n_rows = int(fi_rows.shape[0])
    overlay_rows = xy_rows_for_source_frames(
        fi_rows, n_rows, render_start_frame, max_frames
    )
    out: dict[str, dict[str, np.ndarray]] = {}
    for node_name in node_names:
        if node_name not in processed:
            continue
        node = processed[node_name]
        xs = np.full(max_frames, np.nan, dtype=np.float64)
        ys = np.full(max_frames, np.nan, dtype=np.float64)
        ok = overlay_rows >= 0
        if np.any(ok):
            rows_ok = overlay_rows[ok]
            xs[ok] = node["x"][rows_ok]
            ys[ok] = node["y"][rows_ok]
        out[node_name] = {"x": xs, "y": ys}
    return out or None


def _process_traces(
    trace_data: TraceData,
    *,
    px_per_cm: float,
    jump_filter_cm: float,
    jump_filter_lookahead_frames: int,
) -> dict[str, dict[str, np.ndarray]]:
    filtered = apply_jump_filter(
        trace_data,
        max_jump_cm=jump_filter_cm,
        px_per_cm=px_per_cm,
        lookahead_frames=jump_filter_lookahead_frames,
    )
    return process_trace_data(
        filtered.traces,
        filtered.node_names,
        TraceProcessingParams(),
    )


def _skeleton_from_anatomical_pose(
    pose: AnatomicalPoseLoad,
    *,
    render_start_frame: int,
    max_frames: int,
    px_per_cm: float,
    jump_filter_cm: float,
    jump_filter_lookahead_frames: int,
    node_names: Sequence[str],
) -> dict[str, dict[str, np.ndarray]] | None:
    trace_data = _anatomical_to_trace_data(pose)
    if trace_data.n_frames <= 0:
        return None
    processed = _process_traces(
        trace_data,
        px_per_cm=px_per_cm,
        jump_filter_cm=jump_filter_cm,
        jump_filter_lookahead_frames=jump_filter_lookahead_frames,
    )
    fi_rows = np.asarray(pose.frame_index, dtype=np.int64).ravel()
    return _sample_processed_traces_for_overlay(
        processed,
        node_names,
        fi_rows,
        render_start_frame,
        max_frames,
    )


def _skeleton_from_sleap_path(
    sleap_path: Path,
    *,
    render_start_frame: int,
    max_frames: int,
    px_per_cm: float,
    jump_filter_cm: float,
    jump_filter_lookahead_frames: int,
    node_names: Sequence[str],
) -> dict[str, dict[str, np.ndarray]] | None:
    trace_data = load_sleap_file(sleap_path)
    if trace_data is None or trace_data.n_frames <= 0:
        return None
    processed = _process_traces(
        trace_data,
        px_per_cm=px_per_cm,
        jump_filter_cm=jump_filter_cm,
        jump_filter_lookahead_frames=jump_filter_lookahead_frames,
    )
    fi_rows = np.arange(trace_data.n_frames, dtype=np.int64)
    return _sample_processed_traces_for_overlay(
        processed,
        node_names,
        fi_rows,
        render_start_frame,
        max_frames,
    )


def load_overlay_skeleton(
    *,
    manifest: TrialManifest,
    key: TrialKey,
    pipeline_db: Path,
    tracking_db: Path | None,
    sleap_path: str | None,
    render_start_frame: int,
    max_frames: int,
    px_per_cm: float,
    jump_filter_cm: float,
    jump_filter_lookahead_frames: int,
    node_names: Sequence[str] = STANDARD_NODE_NAMES,
) -> OverlaySkeletonLoad:
    """
    Load per-overlay-frame skeleton node coordinates.

    Read order: canonical H5 ``tracking/anatomical`` (``input_h5_path`` / pipeline /
    tracking db), then ``sleap_path`` sidecar.
    """
    h5_path = resolve_overlay_tracking_h5(manifest, pipeline_db, tracking_db)
    if h5_path is not None:
        pose = load_anatomical_from_h5(h5_path, key)
        if pose is not None:
            nodes = _skeleton_from_anatomical_pose(
                pose,
                render_start_frame=render_start_frame,
                max_frames=max_frames,
                px_per_cm=px_per_cm,
                jump_filter_cm=jump_filter_cm,
                jump_filter_lookahead_frames=jump_filter_lookahead_frames,
                node_names=node_names,
            )
            if nodes:
                return OverlaySkeletonLoad(
                    skeleton=OverlaySkeleton(nodes=nodes, edges=get_skeleton_edges()),
                    pose=OverlayPoseProvenance(
                        kind="h5_anatomical",
                        h5_path=str(h5_path),
                        pose_source_attr=pose.pose_source or None,
                    ),
                )

    if sleap_path and Path(sleap_path).is_file():
        sleap_resolved = str(Path(sleap_path).resolve())
        try:
            nodes = _skeleton_from_sleap_path(
                Path(sleap_path),
                render_start_frame=render_start_frame,
                max_frames=max_frames,
                px_per_cm=px_per_cm,
                jump_filter_cm=jump_filter_cm,
                jump_filter_lookahead_frames=jump_filter_lookahead_frames,
                node_names=node_names,
            )
        except OSError:
            nodes = None
        if nodes:
            return OverlaySkeletonLoad(
                skeleton=OverlaySkeleton(nodes=nodes, edges=get_skeleton_edges()),
                pose=OverlayPoseProvenance(
                    kind="sleap_sidecar",
                    sleap_path=sleap_resolved,
                ),
            )

    return OverlaySkeletonLoad(
        skeleton=None,
        pose=OverlayPoseProvenance(kind="none"),
    )


def centroid_trajectory_from_skeleton(
    nodes: dict[str, dict[str, np.ndarray]],
    *,
    node_names: Sequence[str] = STANDARD_NODE_NAMES,
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Mean of finite skeleton node positions per overlay frame (body centroid)."""
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    for name in node_names:
        if name not in nodes:
            continue
        xs.append(np.asarray(nodes[name]["x"], dtype=np.float64))
        ys.append(np.asarray(nodes[name]["y"], dtype=np.float64))
    if not xs:
        return None
    stack_x = np.stack(xs, axis=0)
    stack_y = np.stack(ys, axis=0)
    valid_nodes = np.isfinite(stack_x) & np.isfinite(stack_y)
    with np.errstate(invalid="ignore"):
        x = np.nanmean(np.where(valid_nodes, stack_x, np.nan), axis=0)
        y = np.nanmean(np.where(valid_nodes, stack_y, np.nan), axis=0)
    valid = np.any(valid_nodes, axis=0) & np.isfinite(x) & np.isfinite(y)
    return x, y, valid


def is_moving_from_trajectory(
    x: np.ndarray,
    y: np.ndarray,
    valid: np.ndarray,
    *,
    fps: float,
    px_per_cm: float,
    min_speed_mps: float = 0.01,
) -> np.ndarray:
    """Derive per-frame movement from overlay trajectory displacement."""
    n = int(len(x))
    out = np.zeros(n, dtype=bool)
    if n < 2 or px_per_cm <= 0 or fps <= 0:
        return out
    dx = np.diff(x)
    dy = np.diff(y)
    speed_mps = np.sqrt(dx**2 + dy**2) / (px_per_cm * 100.0) * fps
    out[1:] = (speed_mps >= min_speed_mps) & valid[:-1] & valid[1:]
    return out


TrajectoryPreference = Literal["auto", "ambulation", "pose_centroid"]


def select_overlay_trajectory(
    *,
    primary_point: str,
    amb_x: np.ndarray,
    amb_y: np.ndarray,
    amb_valid: np.ndarray,
    amb_is_moving: np.ndarray,
    skeleton: OverlaySkeleton | None,
    pose: OverlayPoseProvenance,
    fps: float,
    px_per_cm: float,
    preference: TrajectoryPreference = "auto",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, str, str]:
    """
    Choose green-dot trajectory for the overlay clip.

    ``auto`` uses pose centroid when skeleton pose is available (H5 or SLEAP);
    otherwise ``ambulation_metrics`` primary point (frame_index mapped).
    """
    amb_frac = float(np.mean(amb_valid)) if len(amb_valid) else 0.0
    amb_label = f"ambulation_metrics:{primary_point}"
    amb_detail = (
        f"{amb_label} in pipeline H5, frame_index-mapped "
        f"({amb_frac:.0%} valid frames in clip)"
    )

    use_pose = preference == "pose_centroid" or (
        preference == "auto" and skeleton is not None
    )
    if preference == "ambulation":
        use_pose = False

    if use_pose and skeleton is not None:
        centroid = centroid_trajectory_from_skeleton(skeleton.nodes)
        if centroid is not None:
            x, y, valid = centroid
            is_moving = is_moving_from_trajectory(
                x, y, valid, fps=fps, px_per_cm=px_per_cm
            )
            pose_label = f"pose_centroid:{pose.kind}"
            pose_detail = (
                f"mean of skeleton nodes from {pose.summary()}"
                + (
                    f" (skipped {amb_label}: preference={preference})"
                    if preference != "ambulation"
                    else ""
                )
            )
            return x, y, valid, is_moving, pose_label, pose_detail

    return amb_x, amb_y, amb_valid, amb_is_moving, amb_label, amb_detail
