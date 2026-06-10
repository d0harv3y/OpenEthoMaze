"""Pose overwrite policy and status strings (Phase T3b)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.persist_pose import PersistPoseResult
from maze.pipeline.pose_status import (
    format_pose_status_label,
    policy_to_overwrite_pose,
    read_anatomical_for_trial,
    read_pose_status_label,
    status_for_persist_result,
    write_pose_status_attrs,
)
from maze.pipeline.tracking_io import write_anatomical_tracking


def _write_pose(
    db: Path,
    key: TrialKey,
    *,
    pose_source: str,
    n_frames: int = 4,
    model_path: str = "/data/trial.predictions.slp",
) -> None:
    k = len(STANDARD_NODE_NAMES)
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_anatomical_tracking(
            g,
            frame_index=np.arange(n_frames, dtype=np.uint32),
            x=np.ones((n_frames, k), dtype=np.float32),
            y=np.full((n_frames, k), 2.0, dtype=np.float32),
            score=np.full((n_frames, k), 0.9, dtype=np.float32),
            node_names=STANDARD_NODE_NAMES,
            pose_source=pose_source,  # type: ignore[arg-type]
            fps=30.0,
            pose_model_path=model_path,
            h5=h5,
        )


def test_policy_to_overwrite_pose() -> None:
    assert policy_to_overwrite_pose("keep_live") is False
    assert policy_to_overwrite_pose("prefer_import") is True
    assert policy_to_overwrite_pose(None) is False


def test_format_status_strings(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("1", "S01", "T01")
    _write_pose(db, key, pose_source="sleap_live", n_frames=2400)

    anatomical = read_anatomical_for_trial(db, key)
    assert anatomical is not None
    assert (
        format_pose_status_label(anatomical)
        == "Pose: live (8 nodes, 2400 frames)"
    )
    assert (
        status_for_persist_result(
            PersistPoseResult(action="kept_live", pose_source="sleap_live"),
            anatomical,
            sleap_path=tmp_path / "pred.slp",
        )
        == "Pose: live kept; import skipped"
    )


def test_read_pose_status_prefers_trial_attr(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("1", "S01", "T01")
    _write_pose(db, key, pose_source="sleap_live")
    write_pose_status_attrs(
        db,
        key,
        status="Pose: live kept; import skipped",
        policy="keep_live",
    )
    assert read_pose_status_label(db, key) == "Pose: live kept; import skipped"


def test_import_overwrite_status_string(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("1", "S01", "T01")
    _write_pose(
        db,
        key,
        pose_source="sleap_import",
        model_path=str(tmp_path / "batch.predictions.slp"),
    )
    anatomical = read_anatomical_for_trial(db, key)
    text = status_for_persist_result(
        PersistPoseResult(action="written", pose_source="sleap_import"),
        anatomical,
        sleap_path=tmp_path / "batch.predictions.slp",
        overwrite_pose=True,
    )
    assert "overwrote live" in text
    assert "batch.predictions.slp" in text
