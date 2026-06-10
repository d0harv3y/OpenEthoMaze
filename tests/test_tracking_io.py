"""Round-trip tests for tracking v2 HDF5 I/O (Phase T0) and acquisition buffer (T1a)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from maze.core.anatomy import BLOB_NODE_NAMES, BLOB_VERTEX_COUNT, STANDARD_NODE_NAMES
from maze.core.schema import CONTROLLER_SCHEMA_VERSION_V2
from maze.pipeline.tracking_io import (
    AnatomicalTrackingBuffer,
    flush_anatomical_tracking_buffer,
    has_anatomical_tracking,
    has_tracking_group,
    read_anatomical_tracking,
    read_blob_tracking,
    write_anatomical_tracking,
    write_blob_tracking,
)


def _make_trial_group(h5: h5py.File) -> h5py.Group:
    return h5.create_group("mouse1/session1/trial01")


def test_flush_empty_buffer_on_empty_trial_group(tmp_path: Path) -> None:
    db = tmp_path / "empty.h5"
    with h5py.File(db, "w") as h5:
        g_trial = _make_trial_group(h5)
        buf = AnatomicalTrackingBuffer(
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
        )
        assert flush_anatomical_tracking_buffer(buf, g_trial, h5=h5) is None
        assert not has_tracking_group(g_trial)
        assert read_anatomical_tracking(g_trial) is None
        assert "metadata" not in h5


def test_anatomical_buffer_append_and_flush(tmp_path: Path) -> None:
    db = tmp_path / "buffer.h5"
    k = len(STANDARD_NODE_NAMES)
    rng = np.random.default_rng(99)

    buf = AnatomicalTrackingBuffer(
        node_names=STANDARD_NODE_NAMES,
        pose_source="sleap_live",
        fps=25.0,
        pose_model_path="/ckpt/live.slp",
    )
    for i in range(3):
        buf.append_frame(
            frame_index=10 + i,
            x=rng.random(k, dtype=np.float32),
            y=rng.random(k, dtype=np.float32),
            score=rng.random(k, dtype=np.float32),
            valid=np.ones(k, dtype=np.uint8),
        )

    with h5py.File(db, "w") as h5:
        g_trial = _make_trial_group(h5)
        group = buf.flush(g_trial, h5=h5)
        assert group is not None
        assert has_anatomical_tracking(g_trial)
        assert h5["metadata"].attrs["controller_schema_version"] == CONTROLLER_SCHEMA_VERSION_V2

        loaded = read_anatomical_tracking(g_trial)
        assert loaded is not None
        assert len(loaded.frame_index) == 3
        np.testing.assert_array_equal(loaded.frame_index, np.array([10, 11, 12], dtype=np.uint32))
        assert loaded.pose_source == "sleap_live"
        assert loaded.fps == pytest.approx(25.0)
        assert loaded.pose_model_path == "/ckpt/live.slp"


def test_anatomical_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    t = 5
    k = len(STANDARD_NODE_NAMES)
    rng = np.random.default_rng(42)

    frame_index = np.arange(100, 100 + t, dtype=np.uint32)
    x = rng.random((t, k), dtype=np.float32) * 640.0
    y = rng.random((t, k), dtype=np.float32) * 480.0
    score = rng.random((t, k), dtype=np.float32)
    valid = np.ones((t, k), dtype=np.uint8)
    valid[2, 0] = 0

    with h5py.File(db, "w") as h5:
        g_trial = _make_trial_group(h5)
        write_anatomical_tracking(
            g_trial,
            frame_index=frame_index,
            x=x,
            y=y,
            score=score,
            valid=valid,
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
            pose_model_path="/models/mouse_pose.slp",
            h5=h5,
        )

        assert has_tracking_group(g_trial)
        assert has_anatomical_tracking(g_trial)
        assert h5["metadata"].attrs["controller_schema_version"] == CONTROLLER_SCHEMA_VERSION_V2

        loaded = read_anatomical_tracking(g_trial)
        assert loaded is not None
        np.testing.assert_array_equal(loaded.frame_index, frame_index)
        np.testing.assert_allclose(loaded.x, x)
        np.testing.assert_allclose(loaded.y, y)
        np.testing.assert_allclose(loaded.score, score)
        np.testing.assert_array_equal(loaded.valid, valid)
        assert loaded.node_names == STANDARD_NODE_NAMES
        assert loaded.pose_source == "sleap_live"
        assert loaded.fps == pytest.approx(30.0)
        assert loaded.pose_model_path == "/models/mouse_pose.slp"


def test_blob_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    t = 4
    rng = np.random.default_rng(7)

    frame_index = np.array([0, 1, 2, 3], dtype=np.uint32)
    xy = rng.random((t, BLOB_VERTEX_COUNT, 2), dtype=np.float32) * 512.0
    xy[1] = np.nan
    valid = np.array([1, 0, 1, 1], dtype=np.uint8)
    heading_rad = np.array([0.1, np.nan, 1.5, -0.3], dtype=np.float32)
    score = np.array([0.9, 0.0, 0.7, 0.85], dtype=np.float32)
    backup_params = {"range_low": 40, "range_high": 255, "min_area": 120}

    with h5py.File(db, "w") as h5:
        g_trial = _make_trial_group(h5)
        write_blob_tracking(
            g_trial,
            frame_index=frame_index,
            xy=xy,
            valid=valid,
            heading_rad=heading_rad,
            score=score,
            blob_source="backup_live",
            backup_params_json=backup_params,
            h5=h5,
        )

        loaded = read_blob_tracking(g_trial)
        assert loaded is not None
        np.testing.assert_array_equal(loaded.frame_index, frame_index)
        np.testing.assert_allclose(loaded.xy, xy, equal_nan=True)
        np.testing.assert_array_equal(loaded.valid, valid)
        np.testing.assert_allclose(loaded.heading_rad, heading_rad, equal_nan=True)
        np.testing.assert_allclose(loaded.score, score)
        assert loaded.node_names == BLOB_NODE_NAMES
        assert loaded.blob_source == "backup_live"
        assert loaded.n_vertices == BLOB_VERTEX_COUNT
        assert loaded.backup_params_json == backup_params


def test_read_missing_tracking_returns_none(tmp_path: Path) -> None:
    db = tmp_path / "v1.h5"
    with h5py.File(db, "w") as h5:
        g_trial = _make_trial_group(h5)
        assert read_anatomical_tracking(g_trial) is None
        assert read_blob_tracking(g_trial) is None
        assert not has_tracking_group(g_trial)


def test_anatomical_shape_mismatch_raises(tmp_path: Path) -> None:
    db = tmp_path / "bad.h5"
    with h5py.File(db, "w") as h5:
        g_trial = _make_trial_group(h5)
        with pytest.raises(ValueError, match="x shape"):
            write_anatomical_tracking(
                g_trial,
                frame_index=np.array([0, 1], dtype=np.uint32),
                x=np.zeros((2, 3), dtype=np.float32),
                y=np.zeros((2, len(STANDARD_NODE_NAMES)), dtype=np.float32),
                score=np.zeros((2, len(STANDARD_NODE_NAMES)), dtype=np.float32),
                node_names=STANDARD_NODE_NAMES,
                pose_source="sleap_import",
                fps=25.0,
            )


def test_blob_wrong_vertex_count_raises(tmp_path: Path) -> None:
    db = tmp_path / "bad_blob.h5"
    with h5py.File(db, "w") as h5:
        g_trial = _make_trial_group(h5)
        with pytest.raises(ValueError, match="xy shape"):
            write_blob_tracking(
                g_trial,
                frame_index=np.array([0], dtype=np.uint32),
                xy=np.zeros((1, 4, 2), dtype=np.float32),
                valid=np.array([1], dtype=np.uint8),
                heading_rad=np.array([0.0], dtype=np.float32),
                score=np.array([1.0], dtype=np.float32),
                blob_source="offline_retrack",
            )
