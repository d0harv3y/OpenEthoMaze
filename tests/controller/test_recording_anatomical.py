"""TrialRecorder anatomical tracking flush (Phase T1b)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from maze.controller.acquisition.recording import TrialRecorder
from maze.controller.acquisition.vast.config import VastControllerConfig
from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.core.schema import CONTROLLER_SCHEMA_VERSION_V2
from maze.pipeline.tracking_io import has_anatomical_tracking, read_anatomical_tracking


def test_trial_recorder_flushes_anatomical_tracking(tmp_path: Path) -> None:
    config = VastControllerConfig(
        output_dir=str(tmp_path),
        sleap_model_path="/models/live_pose",
    )
    db_path = tmp_path / "trials.h5"
    dummy_video = tmp_path / "source.mp4"
    dummy_video.write_bytes(b"")

    rec = TrialRecorder(
        output_dir=tmp_path,
        db_path=db_path,
        animal_id="1",
        session_id="S01",
        trial="T01",
        config=config,
        virtual_source_video_path=dummy_video,
    )
    rec.start(frame_shape=(480, 640, 3), fps=30.0)

    k = len(STANDARD_NODE_NAMES)
    rng = np.random.default_rng(0)
    for i in range(3):
        rec.write_frame(
            image=np.zeros((480, 640, 3), dtype=np.uint8),
            frame_index=100 + i,
            x_px=10.0,
            y_px=20.0,
            dist_to_exit_px=5.0,
            trial_state="run",
            region_code="center",
            valid=True,
            duty_pct=50.0,
            pose_xy=rng.random((k, 2), dtype=np.float64) * 400.0,
            pose_scores=np.full(k, 0.85, dtype=np.float64),
            pose_node_valid=np.array([1, 1, 1, 1, 0, 1, 1, 1], dtype=np.uint8),
            pose_node_names=list(STANDARD_NODE_NAMES),
        )

    rec.stop(exit_x_px=100.0, exit_y_px=100.0)

    with h5py.File(db_path, "r") as h5:
        g_trial = h5["1/S01/T01"]
        assert has_anatomical_tracking(g_trial)
        assert h5["metadata"].attrs["controller_schema_version"] == CONTROLLER_SCHEMA_VERSION_V2

        loaded = read_anatomical_tracking(g_trial)
        assert loaded is not None
        assert loaded.pose_source == "sleap_live"
        assert loaded.pose_model_path == "/models/live_pose"
        assert loaded.fps == pytest.approx(30.0)
        assert loaded.node_names == STANDARD_NODE_NAMES
        np.testing.assert_array_equal(loaded.frame_index, np.array([100, 101, 102], dtype=np.uint32))
        np.testing.assert_array_equal(loaded.valid[0], np.array([1, 1, 1, 1, 0, 1, 1, 1], dtype=np.uint8))


def test_trial_recorder_cancel_discards_anatomical_buffer(tmp_path: Path) -> None:
    config = VastControllerConfig(output_dir=str(tmp_path))
    rec = TrialRecorder(
        output_dir=tmp_path,
        db_path=tmp_path / "trials.h5",
        animal_id="1",
        session_id="S01",
        trial="T01",
        config=config,
        virtual_source_video_path=tmp_path / "source.mp4",
    )
    rec.start(frame_shape=(64, 64, 3), fps=30.0)
    k = len(STANDARD_NODE_NAMES)
    rec.write_frame(
        image=np.zeros((64, 64, 3), dtype=np.uint8),
        frame_index=0,
        x_px=0.0,
        y_px=0.0,
        dist_to_exit_px=0.0,
        trial_state="run",
        region_code="center",
        valid=True,
        duty_pct=0.0,
        pose_xy=np.zeros((k, 2), dtype=np.float64),
        pose_scores=np.ones(k),
        pose_node_valid=np.ones(k, dtype=np.uint8),
        pose_node_names=list(STANDARD_NODE_NAMES),
    )
    rec.cancel()
    assert rec._anatomical_buffer is None
