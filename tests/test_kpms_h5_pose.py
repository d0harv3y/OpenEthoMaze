"""Canonical H5 pose resolution and load (Phase T2a)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from maze.core.anatomy import BLOB_NODE_NAMES, BLOB_VERTEX_COUNT, STANDARD_NODE_NAMES
from maze.kpms.h5_pose import (
    AnatomicalPoseLoad,
    BlobPoseLoad,
    load_anatomical_from_h5,
    load_blob_from_h5,
    resolve_canonical_trial_h5,
)
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.tracking_io import write_anatomical_tracking, write_blob_tracking


def _write_trial_pose(
    db: Path,
    key: TrialKey,
    *,
    frame_count: int = 3,
) -> None:
    k = len(STANDARD_NODE_NAMES)
    t = frame_count
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_anatomical_tracking(
            g,
            frame_index=np.arange(t, dtype=np.uint32),
            x=np.ones((t, k), dtype=np.float32),
            y=np.full((t, k), 2.0, dtype=np.float32),
            score=np.full((t, k), 0.9, dtype=np.float32),
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
            h5=h5,
        )


def _manifest(
    *,
    input_h5: Path | str = "",
    db: Path | None = None,
) -> TrialManifest:
    return TrialManifest(
        animal_id="1",
        session="S01",
        trial="T01",
        input_h5_path=Path(input_h5),
        video_path=Path("video.mp4") if db else None,
    )


def test_resolve_prefers_input_h5_when_it_has_pose(tmp_path: Path) -> None:
    acq = tmp_path / "acq.h5"
    results = tmp_path / "results.h5"
    key = TrialKey("1", "S01", "T01")
    _write_trial_pose(acq, key)
    results.touch()

    manifest = _manifest(input_h5=acq, db=results)
    resolved = resolve_canonical_trial_h5(manifest, results)
    assert resolved == acq.resolve()


def test_resolve_uses_db_path_when_input_h5_missing_pose(tmp_path: Path) -> None:
    acq = tmp_path / "acq.h5"
    results = tmp_path / "results.h5"
    key = TrialKey("1", "S01", "T01")
    acq.touch()
    _write_trial_pose(results, key)

    manifest = _manifest(input_h5=acq, db=results)
    assert resolve_canonical_trial_h5(manifest, results) == results.resolve()


def test_resolve_controller_first_db_only(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    _write_trial_pose(db, TrialKey("9", "S02", "T03"))

    manifest = TrialManifest(
        animal_id="9",
        session="S02",
        trial="T03",
        input_h5_path=Path(""),
    )
    assert resolve_canonical_trial_h5(manifest, db) == db.resolve()


def test_resolve_returns_none_without_tracking(tmp_path: Path) -> None:
    db = tmp_path / "v1.h5"
    with h5py.File(db, "w") as h5:
        h5.create_group("1/S01/T01")

    manifest = _manifest(db=db)
    assert resolve_canonical_trial_h5(manifest, db) is None


def test_load_anatomical_from_h5_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("1", "S01", "T01")
    _write_trial_pose(db, key, frame_count=4)

    loaded = load_anatomical_from_h5(db, key)
    assert loaded is not None
    assert isinstance(loaded, AnatomicalPoseLoad)
    assert loaded.coordinates.shape == (4, len(STANDARD_NODE_NAMES), 2)
    assert loaded.confidences.shape == (4, len(STANDARD_NODE_NAMES))
    assert loaded.node_names == STANDARD_NODE_NAMES
    assert loaded.pose_source == "sleap_live"
    assert loaded.fps == pytest.approx(30.0)
    np.testing.assert_array_equal(loaded.frame_index, np.arange(4, dtype=np.uint32))
    np.testing.assert_allclose(loaded.coordinates[:, :, 0], 1.0)
    np.testing.assert_allclose(loaded.coordinates[:, :, 1], 2.0)


def test_load_anatomical_returns_none_for_v1_trial(tmp_path: Path) -> None:
    db = tmp_path / "v1.h5"
    with h5py.File(db, "w") as h5:
        h5.create_group("1/S01/T01")

    assert load_anatomical_from_h5(db, "1/S01/T01") is None
    assert load_anatomical_from_h5(db, TrialKey("1", "S01", "T01")) is None


def test_load_anatomical_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_anatomical_from_h5(tmp_path / "missing.h5", "1/S01/T01") is None


def _write_trial_blob(db: Path, key: TrialKey, *, frame_count: int = 3) -> None:
    t = frame_count
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_blob_tracking(
            g,
            frame_index=np.arange(t, dtype=np.uint32),
            xy=np.ones((t, BLOB_VERTEX_COUNT, 2), dtype=np.float32) * 10.0,
            valid=np.ones(t, dtype=np.uint8),
            heading_rad=np.zeros(t, dtype=np.float32),
            score=np.full(t, 0.8, dtype=np.float32),
            blob_source="backup_live",
            h5=h5,
        )


def test_resolve_blob_prefers_input_h5(tmp_path: Path) -> None:
    acq = tmp_path / "acq.h5"
    results = tmp_path / "results.h5"
    key = TrialKey("1", "S01", "T01")
    _write_trial_blob(acq, key)
    results.touch()

    manifest = _manifest(input_h5=acq, db=results)
    resolved = resolve_canonical_trial_h5(manifest, results, pose_stream="blob")
    assert resolved == acq.resolve()


def test_load_blob_from_h5_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("1", "S01", "T01")
    _write_trial_blob(db, key, frame_count=4)

    loaded = load_blob_from_h5(db, key)
    assert loaded is not None
    assert isinstance(loaded, BlobPoseLoad)
    assert loaded.coordinates.shape == (4, len(BLOB_NODE_NAMES), 2)
    assert loaded.confidences.shape == (4,)
    assert loaded.node_names == BLOB_NODE_NAMES
    assert loaded.blob_source == "backup_live"
    np.testing.assert_array_equal(loaded.frame_index, np.arange(4, dtype=np.uint32))
