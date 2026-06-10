"""kpMS preprocess H5-first (Phase T2b)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.kpms.preprocess import KpmsPreprocessConfig, build_kpms_inputs
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.tracking_io import write_anatomical_tracking


def _write_h5_pose(db: Path, key: TrialKey, *, t: int = 6) -> None:
    k = len(STANDARD_NODE_NAMES)
    rng = np.random.default_rng(1)
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_anatomical_tracking(
            g,
            frame_index=np.arange(t, dtype=np.uint32),
            x=rng.random((t, k), dtype=np.float32) * 200.0 + 50.0,
            y=rng.random((t, k), dtype=np.float32) * 200.0 + 50.0,
            score=np.full((t, k), 0.95, dtype=np.float32),
            valid=np.ones((t, k), dtype=np.uint8),
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
            h5=h5,
        )


def test_build_kpms_inputs_h5_only_no_sleap(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("7", "S01", "T02")
    _write_h5_pose(db, key, t=8)

    manifest = TrialManifest(
        animal_id="7",
        session="S01",
        trial="T02",
        input_h5_path=db,
        sleap_path=None,
        kpms_recording_key="7-S01-T02",
    )
    cfg = KpmsPreprocessConfig(min_fragment_frames=4, db_path=db)

    coordinates, confidences, bodyparts, skipped = build_kpms_inputs([manifest], cfg)

    assert skipped == []
    assert bodyparts == list(STANDARD_NODE_NAMES)
    assert "7-S01-T02" in coordinates
    xy = coordinates["7-S01-T02"]
    assert xy.ndim == 3
    assert xy.shape[1] == len(STANDARD_NODE_NAMES)
    assert xy.shape[2] == 2
    assert xy.shape[0] >= 4
    assert "7-S01-T02" in confidences
    assert confidences["7-S01-T02"].shape[0] == xy.shape[0]


def test_build_kpms_inputs_skips_without_pose_or_sleap(tmp_path: Path) -> None:
    db = tmp_path / "empty.h5"
    with h5py.File(db, "w") as h5:
        h5.create_group("1/S01/T01")

    manifest = TrialManifest(
        animal_id="1",
        session="S01",
        trial="T01",
        input_h5_path=db,
        sleap_path=None,
    )
    _, _, _, skipped = build_kpms_inputs(
        [manifest],
        KpmsPreprocessConfig(db_path=db),
    )
    assert skipped == ["1-S01-T01:missing_pose"]
