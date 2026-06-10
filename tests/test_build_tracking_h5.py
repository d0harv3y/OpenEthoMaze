"""Tests for offline blob materialization and kpMS tracking H5 builder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import h5py
import numpy as np
import pytest

from maze.core.anatomy import BLOB_VERTEX_COUNT, STANDARD_NODE_NAMES
from maze.controller.acquisition.profile import load_fallback_tracking_from_profile
from maze.pipeline.build_tracking_h5 import build_tracking_h5, manifest_path_for_db
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.offline_tracking import (
    materialize_blob_buffer_from_video,
    offline_blob_params_from_fallback,
)
from maze.pipeline.tracking_io import has_anatomical_tracking, has_blob_tracking, write_anatomical_tracking
from maze.repo_paths import REPO_ROOT

PB_TESTS_VAST_PROFILE = REPO_ROOT / "inputs" / "pb-tests_vast.json"

cv2 = pytest.importorskip("cv2")


def _write_synthetic_video(path: Path, n_frames: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        30.0,
        (80, 80),
        isColor=False,
    )
    for i in range(n_frames):
        img = np.full((80, 80), 220, dtype=np.uint8)
        cx = 30 + i
        cy = 40
        cv2.circle(img, (cx, cy), 12, 40, -1)
        writer.write(img)
    writer.release()


def test_materialize_blob_buffer_from_video(tmp_path: Path) -> None:
    video = tmp_path / "99_S01_T01.mp4"
    _write_synthetic_video(video)

    buffer, fps = materialize_blob_buffer_from_video(
        video,
        params=__import__(
            "maze.pipeline.offline_tracking",
            fromlist=["OfflineBlobParams"],
        ).OfflineBlobParams(min_area=20, range_low=0, range_high=128),
    )

    assert fps > 0
    assert buffer.frame_count == 8
    assert buffer.blob_source == "offline_retrack"
    valid_rows = sum(1 for v in buffer._valid_rows if v)
    assert valid_rows >= 4


def test_offline_blob_params_from_controller_profile() -> None:
    if not PB_TESTS_VAST_PROFILE.is_file():
        pytest.skip(f"missing {PB_TESTS_VAST_PROFILE}")

    ft = load_fallback_tracking_from_profile(PB_TESTS_VAST_PROFILE)
    params = offline_blob_params_from_fallback(ft)

    assert params.range_low == 21
    assert params.range_high == 41
    assert params.min_circularity == 0.4
    assert params.min_area == 80


def test_build_tracking_h5_writes_blob_and_manifest(tmp_path: Path) -> None:
    video = tmp_path / "99_S01_T01.mp4"
    _write_synthetic_video(video)
    sleap = tmp_path / "99_S01_T01.predictions.slp"
    sleap.touch()

    db = tmp_path / "kpms_tracking.h5"
    manifest = TrialManifest(
        animal_id="99",
        session="S01",
        trial="T01",
        input_h5_path=db,
        video_path=video,
        sleap_path=sleap,
        video_n_frames=8,
    )

    with patch(
        "maze.pipeline.build_tracking_h5.persist_pose_from_sidecar",
        side_effect=lambda db_path, key, sleap_path, **kw: _persist_test_pose(db_path, key),
    ):
        stats = build_tracking_h5(
            db,
            [manifest],
            skip_blob=False,
            overwrite_blob=True,
        )

    assert stats.blob_written == 1
    assert stats.anatomical_written == 1
    assert db.is_file()
    assert manifest_path_for_db(db).is_file()

    with h5py.File(db, "r") as h5:
        g = h5["99/S01/T01"]
        assert has_anatomical_tracking(g)
        assert has_blob_tracking(g)
        blob = g["tracking/blob"]
        assert blob.attrs["blob_source"] == "offline_retrack"
        assert blob["xy"].shape[1] == BLOB_VERTEX_COUNT


def _persist_test_pose(db_path: Path, key) -> object:
    from maze.pipeline.db import open_db
    from maze.pipeline.db.trial_key import resolve_trial_key_for_hdf5
    from maze.pipeline.persist_pose import PersistPoseResult

    t = 8
    k = len(STANDARD_NODE_NAMES)
    with open_db(db_path, "a") as h5:
        resolved = resolve_trial_key_for_hdf5(h5, key)
        g = h5[resolved.path().lstrip("/")]
        write_anatomical_tracking(
            g,
            frame_index=np.arange(t, dtype=np.uint32),
            x=np.ones((t, k), dtype=np.float32) * 10.0,
            y=np.ones((t, k), dtype=np.float32) * 20.0,
            score=np.ones((t, k), dtype=np.float32),
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_import",
            fps=30.0,
            h5=h5,
        )
    return PersistPoseResult(action="written", pose_source="sleap_import")
