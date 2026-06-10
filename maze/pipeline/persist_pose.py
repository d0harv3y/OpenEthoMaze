"""
Backfill ``tracking/anatomical`` from SLEAP sidecars with ``keep_live`` policy (Phase T3a).

See ``docs/h5_tracking_contract.md`` § Pose overwrite policy.

Default: preserve ``pose_source=sleap_live`` acquisition pose. Sidecar import writes
``sleap_import`` only when anatomical is missing or ``overwrite_pose=True``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from maze.pipeline.db import open_db
from maze.pipeline.db.trial_key import TrialKey, resolve_trial_key_for_hdf5
from maze.pipeline.defaults import DEFAULT_FPS
from maze.pipeline.io.sleap_loader import TraceData, load_sleap_file
from maze.pipeline.run_provenance import utc_now_iso
from maze.pipeline.tracking_io import (
    has_anatomical_tracking,
    read_anatomical_tracking,
    write_anatomical_tracking,
)

log = logging.getLogger(__name__)

PosePersistAction = Literal[
    "written",
    "kept_live",
    "unchanged",
    "skipped_no_sidecar",
    "skipped_failed_load",
]


@dataclass(frozen=True)
class PersistPoseResult:
    """Outcome of a sidecar → H5 anatomical persist attempt."""

    action: PosePersistAction
    pose_source: str | None = None


def trace_to_anatomical_arrays(
    trace: TraceData,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Convert :class:`TraceData` to dense ``tracking/anatomical`` dataset arrays."""
    node_names = list(trace.node_names)
    if not node_names:
        raise ValueError("trace has no node_names")

    t = int(trace.n_frames)
    k = len(node_names)
    x = np.full((t, k), np.nan, dtype=np.float32)
    y = np.full((t, k), np.nan, dtype=np.float32)
    score = np.zeros((t, k), dtype=np.float32)
    valid = np.zeros((t, k), dtype=np.uint8)

    for j, node_name in enumerate(node_names):
        node = trace.traces.get(node_name)
        if node is None:
            continue
        x[:, j] = np.asarray(node["x"], dtype=np.float32).reshape(-1)[:t]
        y[:, j] = np.asarray(node["y"], dtype=np.float32).reshape(-1)[:t]
        score[:, j] = np.asarray(
            node.get("score", np.ones(t, dtype=np.float32)),
            dtype=np.float32,
        ).reshape(-1)[:t]
        visible = node.get("visible")
        if visible is not None:
            valid[:, j] = np.asarray(visible, dtype=np.uint8).reshape(-1)[:t]
        else:
            valid[:, j] = (
                np.isfinite(x[:, j]) & np.isfinite(y[:, j]) & (score[:, j] > 0)
            ).astype(np.uint8)

    frame_index = np.arange(t, dtype=np.uint32)
    return frame_index, x, y, score, valid


def _resolve_fps(trace: TraceData, fps: float | None) -> float:
    if fps is not None and fps > 0:
        return float(fps)
    if trace.fps > 0:
        return float(trace.fps)
    return DEFAULT_FPS


def persist_pose_from_trace(
    g_trial,
    trace: TraceData,
    *,
    sleap_path: Path,
    overwrite_pose: bool = False,
    fps: float | None = None,
    h5=None,
) -> PersistPoseResult:
    """
    Write ``tracking/anatomical`` from an in-memory :class:`TraceData`.

    Used by :func:`persist_pose_from_sidecar` and unit tests.
    """
    existing = read_anatomical_tracking(g_trial)
    if existing is not None and not overwrite_pose:
        if existing.pose_source == "sleap_live":
            return PersistPoseResult(action="kept_live", pose_source=existing.pose_source)
        return PersistPoseResult(action="unchanged", pose_source=existing.pose_source)

    frame_index, x, y, score, valid = trace_to_anatomical_arrays(trace)
    if frame_index.shape[0] == 0:
        return PersistPoseResult(action="skipped_failed_load")

    g_anat = write_anatomical_tracking(
        g_trial,
        frame_index=frame_index,
        x=x,
        y=y,
        score=score,
        valid=valid,
        node_names=tuple(trace.node_names),
        pose_source="sleap_import",
        fps=_resolve_fps(trace, fps),
        pose_model_path=str(sleap_path.resolve()),
        h5=h5,
    )

    if existing is not None and existing.pose_source == "sleap_live" and overwrite_pose:
        g_anat.attrs["pose_superseded_at"] = utc_now_iso()
        g_anat.attrs["pose_superseded_by"] = str(sleap_path.resolve())

    log.info(
        "persisted anatomical pose from %s (overwrite=%s, prior=%s)",
        sleap_path,
        overwrite_pose,
        existing.pose_source if existing else None,
    )
    return PersistPoseResult(action="written", pose_source="sleap_import")


def persist_pose_from_sidecar(
    db_path: Path,
    key: TrialKey,
    sleap_path: Path,
    *,
    overwrite_pose: bool = False,
    fps: float | None = None,
) -> PersistPoseResult:
    """
    Backfill ``tracking/anatomical`` from a SLEAP sidecar when allowed.

    Default ``keep_live``: existing ``sleap_live`` pose is never replaced unless
    ``overwrite_pose=True``.
    """
    path = Path(sleap_path)
    if not path.is_file():
        return PersistPoseResult(action="skipped_no_sidecar")

    with open_db(db_path, "a") as h5:
        resolved = resolve_trial_key_for_hdf5(h5, key)
        group_path = resolved.path().lstrip("/")
        if group_path not in h5:
            return PersistPoseResult(action="skipped_failed_load")
        g_trial = h5[group_path]

        if has_anatomical_tracking(g_trial) and not overwrite_pose:
            existing = read_anatomical_tracking(g_trial)
            if existing is not None:
                if existing.pose_source == "sleap_live":
                    return PersistPoseResult(action="kept_live", pose_source=existing.pose_source)
                return PersistPoseResult(action="unchanged", pose_source=existing.pose_source)

        trace = load_sleap_file(path)
        if trace is None or trace.n_frames <= 0:
            return PersistPoseResult(action="skipped_failed_load")

        return persist_pose_from_trace(
            g_trial,
            trace,
            sleap_path=path,
            overwrite_pose=overwrite_pose,
            fps=fps,
            h5=h5,
        )
