"""kpMS preprocess H5-first (Phase T2b)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from maze.core.anatomy import BLOB_NODE_NAMES, BLOB_VERTEX_COUNT, STANDARD_NODE_NAMES
from maze.kpms.heading_idxs import anterior_posterior_idxs
from maze.kpms.preprocess import KpmsPreprocessConfig, build_kpms_inputs
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.tracking_io import write_anatomical_tracking, write_blob_tracking


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


def test_build_kpms_inputs_skips_sleap_when_input_h5_set(tmp_path: Path) -> None:
    db = tmp_path / "cohort.h5"
    with h5py.File(db, "w") as h5:
        h5.create_group("1/S01/T01")

    manifest = TrialManifest(
        animal_id="1",
        session="S01",
        trial="T01",
        input_h5_path=db,
        sleap_path=Path(r"E:\missing.predictions.slp"),
    )
    _, _, _, skipped = build_kpms_inputs(
        [manifest],
        KpmsPreprocessConfig(db_path=db),
    )
    assert skipped == ["1-S01-T01:missing_h5_pose"]


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
    assert skipped == ["1-S01-T01:missing_h5_pose"]


def _write_h5_blob(db: Path, key: TrialKey, *, t: int = 8) -> None:
    rng = np.random.default_rng(3)
    frame_index = np.arange(t, dtype=np.uint32)
    xy = rng.random((t, BLOB_VERTEX_COUNT, 2), dtype=np.float32) * 200.0 + 50.0
    valid = np.ones(t, dtype=np.uint8)
    heading_rad = np.linspace(-0.5, 0.5, t, dtype=np.float32)
    score = np.full(t, 0.85, dtype=np.float32)
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_blob_tracking(
            g,
            frame_index=frame_index,
            xy=xy,
            valid=valid,
            heading_rad=heading_rad,
            score=score,
            blob_source="backup_live",
            h5=h5,
        )


def test_build_kpms_inputs_blob_h5_only(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("7", "S01", "T02")
    _write_h5_blob(db, key, t=8)

    manifest = TrialManifest(
        animal_id="7",
        session="S01",
        trial="T02",
        input_h5_path=db,
        sleap_path=None,
        kpms_recording_key="7-S01-T02",
    )
    cfg = KpmsPreprocessConfig(
        min_fragment_frames=4,
        db_path=db,
        pose_stream="blob",
    )

    coordinates, confidences, bodyparts, skipped = build_kpms_inputs([manifest], cfg)

    assert skipped == []
    assert bodyparts == list(BLOB_NODE_NAMES)
    assert "7-S01-T02" in coordinates
    xy = coordinates["7-S01-T02"]
    assert xy.ndim == 3
    assert xy.shape[1] == len(BLOB_NODE_NAMES)
    assert xy.shape[2] == 2
    assert xy.shape[0] >= 4
    assert "7-S01-T02" in confidences
    assert confidences["7-S01-T02"].shape == (xy.shape[0], len(BLOB_NODE_NAMES))


def test_build_kpms_inputs_blob_skips_without_tracking(tmp_path: Path) -> None:
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
        KpmsPreprocessConfig(db_path=db, pose_stream="blob"),
    )
    assert skipped == ["1-S01-T01:missing_pose"]


def test_blob_anterior_posterior_idxs_from_motion_heading() -> None:
    anterior, posterior = anterior_posterior_idxs(list(BLOB_NODE_NAMES), pose_stream="blob")
    assert anterior == [0]
    assert posterior == [4]


def _write_h5_pose_frames(
    db: Path,
    key: TrialKey,
    frame_index: np.ndarray,
) -> None:
    t = int(frame_index.shape[0])
    k = len(STANDARD_NODE_NAMES)
    rng = np.random.default_rng(2)
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_anatomical_tracking(
            g,
            frame_index=frame_index.astype(np.uint32),
            x=rng.random((t, k), dtype=np.float32) * 200.0 + 50.0,
            y=rng.random((t, k), dtype=np.float32) * 200.0 + 50.0,
            score=np.full((t, k), 0.95, dtype=np.float32),
            valid=np.ones((t, k), dtype=np.uint8),
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
            h5=h5,
        )


def _write_h5_blob_frames(
    db: Path,
    key: TrialKey,
    frame_index: np.ndarray,
    *,
    valid: np.ndarray | None = None,
) -> None:
    t = int(frame_index.shape[0])
    rng = np.random.default_rng(4)
    xy = rng.random((t, BLOB_VERTEX_COUNT, 2), dtype=np.float32) * 200.0 + 50.0
    if valid is None:
        valid = np.ones(t, dtype=np.uint8)
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_blob_tracking(
            g,
            frame_index=frame_index.astype(np.uint32),
            xy=xy,
            valid=valid,
            heading_rad=np.zeros(t, dtype=np.float32),
            score=np.full(t, 0.85, dtype=np.float32),
            blob_source="backup_live",
            h5=h5,
        )


def test_build_kpms_inputs_fused_k16_aligned_frame_index(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("7", "S01", "T02")
    frame_index = np.array([10, 20, 30, 40, 50, 60, 70, 80], dtype=np.uint32)
    _write_h5_pose_frames(db, key, frame_index)
    _write_h5_blob_frames(db, key, frame_index)

    manifest = TrialManifest(
        animal_id="7",
        session="S01",
        trial="T02",
        input_h5_path=db,
        sleap_path=None,
        kpms_recording_key="7-S01-T02",
    )
    cfg = KpmsPreprocessConfig(
        min_fragment_frames=4,
        db_path=db,
        pose_stream="fused",
    )

    coordinates, confidences, bodyparts, skipped = build_kpms_inputs([manifest], cfg)

    assert skipped == []
    assert bodyparts == list(STANDARD_NODE_NAMES) + list(BLOB_NODE_NAMES)
    xy = coordinates["7-S01-T02"]
    conf = confidences["7-S01-T02"]
    assert xy.shape[1] == 16
    assert xy.shape[2] == 2
    assert xy.shape[0] >= 4
    assert conf.shape == (xy.shape[0], 16)
    assert np.isfinite(xy[:, :8]).all()
    assert np.isfinite(xy[:, 8:]).all()


def test_build_kpms_inputs_fused_partial_validity(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("3", "S01", "T01")
    frame_index = np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=np.uint32)
    _write_h5_pose_frames(db, key, frame_index)
    blob_valid = np.array([1, 1, 0, 1, 1, 1, 1, 1], dtype=np.uint8)
    _write_h5_blob_frames(db, key, frame_index, valid=blob_valid)

    manifest = TrialManifest(
        animal_id="3",
        session="S01",
        trial="T01",
        input_h5_path=db,
        sleap_path=None,
    )
    coordinates, confidences, _, skipped = build_kpms_inputs(
        [manifest],
        KpmsPreprocessConfig(min_fragment_frames=4, db_path=db, pose_stream="fused"),
    )

    assert skipped == []
    xy = coordinates["3-S01-T01"]
    conf = confidences["3-S01-T01"]
    assert not np.isfinite(xy[2, 8:]).any()
    assert conf[2, 8:].max() == 0.0
    assert np.isfinite(xy[2, :8]).all()


def test_fused_anterior_posterior_idxs() -> None:
    bodyparts = list(STANDARD_NODE_NAMES) + list(BLOB_NODE_NAMES)
    anterior, posterior = anterior_posterior_idxs(bodyparts, pose_stream="fused")
    assert anterior == [0, 8]
    assert posterior == [1, 12]
