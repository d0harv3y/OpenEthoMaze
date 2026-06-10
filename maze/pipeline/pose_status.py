"""
Pose overwrite policy helpers and user-visible status strings (Phase T3b).

See ``docs/h5_tracking_contract.md`` § Pose overwrite policy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from maze.pipeline.db import open_db
from maze.pipeline.db.trial_attributes import write_trial_attrs
from maze.pipeline.db.trial_key import TrialKey, resolve_trial_key_for_hdf5
from maze.pipeline.persist_pose import PersistPoseResult, PosePersistAction
from maze.pipeline.tracking_io import AnatomicalTrackingData, read_anatomical_tracking

PoseOverwritePolicy = Literal["keep_live", "prefer_import"]


def policy_to_overwrite_pose(policy: str | None) -> bool:
    """Return True when policy opts into replacing live acquisition pose."""
    return str(policy or "keep_live").strip() == "prefer_import"


def overwrite_pose_to_policy(overwrite_pose: bool) -> PoseOverwritePolicy:
    return "prefer_import" if overwrite_pose else "keep_live"


def _short_sidecar_name(path: Path | str | None) -> str:
    if path is None:
        return ""
    name = Path(path).name
    if not name:
        return ""
    return f"…{name}" if len(name) > 24 else name


def format_pose_status_label(
    anatomical: AnatomicalTrackingData | None,
    *,
    persist_action: PosePersistAction | None = None,
    sleap_path: Path | str | None = None,
    overwrite_pose: bool = False,
) -> str:
    """
    Format a status-bar / trial-summary pose line per ``h5_tracking_contract.md``.

    Examples:
      ``Pose: live (8 nodes, 2400 frames)``
      ``Pose: imported from …predictions.slp (8 nodes, 2400 frames)``
      ``Pose: imported from …slp (overwrote live)``
      ``Pose: live kept; import skipped``
    """
    if persist_action == "kept_live":
        return "Pose: live kept; import skipped"

    if anatomical is None:
        return "Pose: none"

    n_nodes = len(anatomical.node_names)
    n_frames = int(anatomical.frame_index.shape[0])
    counts = f"({n_nodes} nodes, {n_frames} frames)"
    sidecar = _short_sidecar_name(sleap_path or anatomical.pose_model_path)

    if persist_action == "written" and overwrite_pose and anatomical.pose_source == "sleap_import":
        if sidecar:
            return f"Pose: imported from {sidecar} (overwrote live)"
        return f"Pose: imported {counts} (overwrote live)"

    if anatomical.pose_source == "sleap_live":
        return f"Pose: live {counts}"

    if anatomical.pose_source in ("sleap_import", "dlc_import"):
        if sidecar:
            return f"Pose: imported from {sidecar} {counts}"
        return f"Pose: imported {counts}"

    return f"Pose: {anatomical.pose_source} {counts}"


def status_for_persist_result(
    result: PersistPoseResult,
    anatomical: AnatomicalTrackingData | None,
    *,
    sleap_path: Path | str | None = None,
    overwrite_pose: bool = False,
) -> str:
    """Build the pose status string for a :class:`PersistPoseResult`."""
    return format_pose_status_label(
        anatomical,
        persist_action=result.action,
        sleap_path=sleap_path,
        overwrite_pose=overwrite_pose,
    )


def read_anatomical_for_trial(db_path: Path, key: TrialKey) -> AnatomicalTrackingData | None:
    """Read ``tracking/anatomical`` for ``key`` in ``db_path``."""
    try:
        with open_db(db_path, "r") as h5:
            resolved = resolve_trial_key_for_hdf5(h5, key)
            group_path = resolved.path().lstrip("/")
            if group_path not in h5:
                return None
            return read_anatomical_tracking(h5[group_path])
    except OSError:
        return None


def read_pose_status_label(db_path: Path, key: TrialKey) -> str:
    """
    Read pose status for a trial: prefer ``pose_persist_status`` attr, else derive from H5.
    """
    try:
        with open_db(db_path, "r") as h5:
            resolved = resolve_trial_key_for_hdf5(h5, key)
            group_path = resolved.path().lstrip("/")
            if group_path not in h5:
                return "Pose: none"
            g_trial = h5[group_path]
            raw = g_trial.attrs.get("pose_persist_status")
            if raw is not None:
                text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                if text.strip():
                    return text.strip()
            anatomical = read_anatomical_tracking(g_trial)
    except OSError:
        # Concurrent append (e.g. post-trial analyze) on Windows HDF5.
        return "Pose: —"
    return format_pose_status_label(anatomical)


def write_pose_status_attrs(
    db_path: Path,
    key: TrialKey,
    *,
    status: str,
    policy: PoseOverwritePolicy,
) -> None:
    """Persist pose summary and policy on the trial group."""
    write_trial_attrs(
        db_path,
        key,
        {
            "pose_persist_status": status,
            "pose_overwrite_policy": policy,
        },
    )
