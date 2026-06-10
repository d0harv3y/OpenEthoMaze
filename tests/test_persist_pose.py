"""Sidecar backfill with keep_live policy (Phase T3a)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np
import pytest

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.sleap_loader import TraceData
from maze.pipeline.persist_pose import persist_pose_from_sidecar, persist_pose_from_trace
from maze.pipeline.tracking_io import read_anatomical_tracking, write_anatomical_tracking


def _trial_key() -> TrialKey:
    return TrialKey("1", "S01", "T01")


def _write_live_pose(db: Path, key: TrialKey, *, x_value: float = 1.0) -> None:
    k = len(STANDARD_NODE_NAMES)
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_anatomical_tracking(
            g,
            frame_index=np.array([0, 1], dtype=np.uint32),
            x=np.full((2, k), x_value, dtype=np.float32),
            y=np.full((2, k), 10.0, dtype=np.float32),
            score=np.full((2, k), 0.9, dtype=np.float32),
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
            h5=h5,
        )


def _import_trace(*, x_offset: float = 100.0) -> TraceData:
    k = len(STANDARD_NODE_NAMES)
    n = 4
    traces = {
        name: {
            "x": np.full(n, x_offset + i, dtype=np.float32),
            "y": np.full(n, 200.0 + i, dtype=np.float32),
            "score": np.full(n, 0.75, dtype=np.float32),
            "visible": np.ones(n, dtype=bool),
        }
        for i, name in enumerate(STANDARD_NODE_NAMES)
    }
    return TraceData(
        traces=traces,
        node_names=list(STANDARD_NODE_NAMES),
        n_frames=n,
        fps=25.0,
        source_path=Path("import.slp"),
    )


def test_keep_live_when_sidecar_import_without_overwrite(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = _trial_key()
    _write_live_pose(db, key, x_value=1.0)
    sidecar = tmp_path / "pred.slp"
    sidecar.touch()

    with patch(
        "maze.pipeline.persist_pose.load_sleap_file",
        return_value=_import_trace(x_offset=999.0),
    ):
        result = persist_pose_from_sidecar(db, key, sidecar, overwrite_pose=False)

    assert result.action == "kept_live"
    assert result.pose_source == "sleap_live"

    with h5py.File(db, "r") as h5:
        loaded = read_anatomical_tracking(h5[key.path().lstrip("/")])
        assert loaded is not None
        assert loaded.pose_source == "sleap_live"
        np.testing.assert_allclose(loaded.x, 1.0)


def test_backfill_when_anatomical_missing(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = _trial_key()
    with h5py.File(db, "w") as h5:
        h5.create_group(key.path().lstrip("/"))

    sidecar = tmp_path / "pred.slp"
    sidecar.touch()

    with patch(
        "maze.pipeline.persist_pose.load_sleap_file",
        return_value=_import_trace(x_offset=50.0),
    ):
        result = persist_pose_from_sidecar(db, key, sidecar, overwrite_pose=False)

    assert result.action == "written"
    assert result.pose_source == "sleap_import"

    with h5py.File(db, "r") as h5:
        loaded = read_anatomical_tracking(h5[key.path().lstrip("/")])
        assert loaded is not None
        assert loaded.pose_source == "sleap_import"
        assert loaded.pose_model_path == str(sidecar.resolve())
        np.testing.assert_allclose(loaded.x[0, 0], 50.0)


def test_overwrite_live_sets_pose_superseded_attrs(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = _trial_key()
    _write_live_pose(db, key)
    sidecar = tmp_path / "batch.predictions.slp"
    sidecar.touch()

    with h5py.File(db, "a") as h5:
        g = h5[key.path().lstrip("/")]
        result = persist_pose_from_trace(
            g,
            _import_trace(x_offset=77.0),
            sleap_path=sidecar,
            overwrite_pose=True,
            h5=h5,
        )

    assert result.action == "written"
    assert result.pose_source == "sleap_import"

    with h5py.File(db, "r") as h5:
        g_anat = h5[f"{key.path().lstrip('/')}/tracking/anatomical"]
        assert "pose_superseded_at" in g_anat.attrs
        assert g_anat.attrs["pose_superseded_by"] == str(sidecar.resolve())
        loaded = read_anatomical_tracking(h5[key.path().lstrip("/")])
        assert loaded is not None
        assert loaded.pose_source == "sleap_import"
        np.testing.assert_allclose(loaded.x[0, 0], 77.0)


def test_skipped_when_sidecar_missing(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = _trial_key()
    with h5py.File(db, "w") as h5:
        h5.create_group(key.path().lstrip("/"))

    result = persist_pose_from_sidecar(db, key, tmp_path / "missing.slp")
    assert result.action == "skipped_no_sidecar"
