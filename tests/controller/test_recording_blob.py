"""TrialRecorder blob tracking flush (Phase T1d)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from maze.controller.acquisition.recording import TrialRecorder
from maze.controller.acquisition.vast.config import VastControllerConfig
from maze.core.anatomy import BLOB_NODE_NAMES, BLOB_VERTEX_COUNT
from maze.core.schema import CONTROLLER_SCHEMA_VERSION_V2
from maze.pipeline.tracking_io import read_blob_tracking


def _ellipse_mask(
    shape: tuple[int, int],
    cx: float,
    cy: float,
    a: float,
    b: float,
) -> np.ndarray:
    mask = np.zeros(shape, dtype=np.uint8)
    t = np.linspace(0.0, 2.0 * np.pi, 64, endpoint=False)
    xs = np.clip(np.round(cx + a * np.cos(t)).astype(int), 0, shape[1] - 1)
    ys = np.clip(np.round(cy + b * np.sin(t)).astype(int), 0, shape[0] - 1)
    mask[ys, xs] = 255
    return mask


def test_trial_recorder_flushes_blob_tracking(tmp_path: Path) -> None:
    config = VastControllerConfig(
        output_dir=str(tmp_path),
        track_enable_backup=True,
    )
    config.fallback_tracking.min_area = 10
    config.fallback_tracking.range_low = 30
    config.fallback_tracking.range_high = 220

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
    rec.start(frame_shape=(120, 120, 3), fps=30.0)

    for i in range(4):
        cx = 60.0 + i * 4.0
        mask = _ellipse_mask((120, 120), cx, 60.0, 22.0, 14.0)
        rec.write_frame(
            image=np.zeros((120, 120, 3), dtype=np.uint8),
            frame_index=200 + i,
            x_px=float(cx),
            y_px=60.0,
            dist_to_exit_px=0.0,
            trial_state="run",
            region_code="center",
            valid=True,
            duty_pct=0.0,
            blob_mask=mask,
        )

    rec.stop(exit_x_px=60.0, exit_y_px=60.0)

    with h5py.File(db_path, "r") as h5:
        g_trial = h5["1/S01/T01"]
        assert h5["metadata"].attrs["controller_schema_version"] == CONTROLLER_SCHEMA_VERSION_V2

        loaded = read_blob_tracking(g_trial)
        assert loaded is not None
        assert loaded.blob_source == "backup_live"
        assert loaded.node_names == BLOB_NODE_NAMES
        assert loaded.n_vertices == BLOB_VERTEX_COUNT
        assert loaded.backup_params_json is not None
        assert loaded.backup_params_json["range_low"] == 30
        assert loaded.backup_params_json["range_high"] == 220
        np.testing.assert_array_equal(loaded.frame_index, np.array([200, 201, 202, 203], dtype=np.uint32))
        assert loaded.valid.sum() >= 3
        assert np.isfinite(loaded.xy[loaded.valid.astype(bool)]).all()
        if loaded.valid[1:].any():
            assert np.isfinite(loaded.heading_rad[1]) or loaded.score[1] >= 0.0


def test_blob_crop_offset_applied(tmp_path: Path) -> None:
    config = VastControllerConfig(output_dir=str(tmp_path), track_enable_backup=True)
    config.fallback_tracking.min_area = 10

    rec = TrialRecorder(
        output_dir=tmp_path,
        db_path=tmp_path / "trials.h5",
        animal_id="2",
        session_id="S01",
        trial="T01",
        config=config,
        virtual_source_video_path=tmp_path / "source.mp4",
    )
    rec.start(frame_shape=(80, 80, 3), fps=30.0)

    crop_mask = _ellipse_mask((40, 40), 20.0, 20.0, 12.0, 8.0)
    rec.write_frame(
        image=np.zeros((80, 80, 3), dtype=np.uint8),
        frame_index=0,
        x_px=40.0,
        y_px=40.0,
        dist_to_exit_px=0.0,
        trial_state="run",
        region_code="center",
        valid=True,
        duty_pct=0.0,
        blob_mask=crop_mask,
        blob_crop_rect=(20, 20, 60, 60),
    )
    rec.write_frame(
        image=np.zeros((80, 80, 3), dtype=np.uint8),
        frame_index=1,
        x_px=44.0,
        y_px=40.0,
        dist_to_exit_px=0.0,
        trial_state="run",
        region_code="center",
        valid=True,
        duty_pct=0.0,
        blob_mask=_ellipse_mask((40, 40), 24.0, 20.0, 12.0, 8.0),
        blob_crop_rect=(20, 20, 60, 60),
    )
    rec.stop(exit_x_px=40.0, exit_y_px=40.0)

    with h5py.File(tmp_path / "trials.h5", "r") as h5:
        loaded = read_blob_tracking(h5["2/S01/T01"])
        assert loaded is not None
        assert loaded.valid[0] == 1
        assert float(loaded.xy[0, :, 0].min()) >= 15.0


def test_cancel_discards_blob_buffer(tmp_path: Path) -> None:
    config = VastControllerConfig(output_dir=str(tmp_path), track_enable_backup=True)
    rec = TrialRecorder(
        output_dir=tmp_path,
        db_path=tmp_path / "trials.h5",
        animal_id="3",
        session_id="S01",
        trial="T01",
        config=config,
        virtual_source_video_path=tmp_path / "source.mp4",
    )
    rec.start(frame_shape=(64, 64, 3), fps=30.0)
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
        blob_mask=_ellipse_mask((64, 64), 32.0, 32.0, 10.0, 8.0),
    )
    rec.cancel()
    assert rec._blob_buffer is None
