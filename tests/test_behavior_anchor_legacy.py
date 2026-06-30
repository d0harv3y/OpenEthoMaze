"""Tests for legacy speed adapter and anchor artifact store."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from maze.core.h5_layout import ensure_group, open_db, write_xy_table
from maze.core.schema import XY_ROW_DTYPE
from maze.kpms.behavior_ethogram.anchor_build import build_is_moving_anchor
from maze.kpms.behavior_ethogram.anchor_legacy import load_legacy_vast_speed, run_phase_mask
from maze.kpms.behavior_ethogram.anchor_store import (
    IsMovingAnchor,
    TrialAnchorFrames,
    read_is_moving_anchor,
    write_is_moving_anchor,
)
from maze.kpms.behavior_ethogram.paths import anchor_dir
from maze.pipeline.io.file_discovery import TrialManifest


def _write_legacy_trial_h5(path, *, n_frames: int = 10, fps: float = 10.0) -> None:
    xy = np.zeros(n_frames, dtype=XY_ROW_DTYPE)
    xy["frame_index"] = np.arange(n_frames, dtype=np.uint32)
    xy["x"] = np.linspace(0, 90, n_frames, dtype=np.float32)
    xy["y"] = 0.0
    xy["valid"] = 1
    xy["trial_state"] = b"run"
    xy["trial_state"][:3] = b"iti_wait"
    with open_db(path, "w") as h5:
        g = ensure_group(h5, "1")
        g = ensure_group(g, "S01")
        g = ensure_group(g, "T01")
        g.attrs["fps"] = fps
        g.attrs["px_per_cm"] = 1.0
        write_xy_table(g, "spot_hybrid", xy, fps)


def _manifest(h5_path) -> TrialManifest:
    return TrialManifest(
        animal_id="1",
        session="S01",
        trial="T01",
        input_h5_path=Path(h5_path),
    )


def test_load_legacy_vast_speed_derives_speed_and_states(tmp_path) -> None:
    db = tmp_path / "legacy.h5"
    _write_legacy_trial_h5(db)
    loaded = load_legacy_vast_speed(db, _manifest(db))
    assert loaded is not None
    assert loaded.trial_key == "1-S01-T01"
    assert len(loaded.speed_mps) == 10
    assert loaded.speed_mps[0] == 0.0
    assert loaded.speed_mps[1] > 0.0
    assert run_phase_mask(loaded.trial_state).sum() == 7


def test_anchor_store_round_trip(tmp_path) -> None:
    art = anchor_dir(tmp_path, "is_moving", "cal1")
    anchor = IsMovingAnchor(
        calibration_id="cal1",
        fps=20.0,
        trials=(
            TrialAnchorFrames(
                trial_key="1-S01-T01",
                source_frame_index=np.array([0, 1, 2], dtype=np.int64),
                is_moving=np.array([False, True, True]),
            ),
        ),
        params={"enter_mps": 0.2, "exit_mps": 0.05, "min_dwell_ms": 100.0},
        input_hashes={"legacy_db": "abc"},
    )
    write_is_moving_anchor(art, anchor)
    loaded = read_is_moving_anchor(art)
    assert loaded.calibration_id == "cal1"
    assert loaded.params["enter_mps"] == 0.2
    np.testing.assert_array_equal(loaded.trials[0].is_moving, anchor.trials[0].is_moving)


def test_build_is_moving_anchor_from_synthetic_legacy(tmp_path) -> None:
    db = tmp_path / "legacy.h5"
    _write_legacy_trial_h5(db, n_frames=30, fps=10.0)
    art = anchor_dir(tmp_path, "is_moving", "syn")
    anchor = build_is_moving_anchor(db, [_manifest(db)], art, calibration_id="syn")
    assert len(anchor.trials) == 1
    trial = anchor.trials[0]
    assert trial.is_moving.dtype == bool
    assert not trial.is_moving[:3].any()  # iti_wait masked out
    assert trial.is_moving[10:].any()
