"""Synthetic tests for stimulus ↔ bout join."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pytest

from maze.core.h5_layout import write_feedback_table, write_xy_table
from maze.core.schema import FEEDBACK_ROW_DTYPE, XY_ROW_DTYPE
from maze.kpms.behavior_ethogram.stimulus_join import (
    StimulusJoinFilterConfig,
    TrialStimulusFrames,
    enrich_bout_row_with_stimulus,
    filter_bout_rows,
    mean_scalar_over_rows,
    read_trial_stimulus_frames,
    verify_trial_stimulus_h5,
)
from maze.pipeline.db.trial_key import TrialKey


def _bout_row(**kwargs: str) -> dict[str, str]:
    base = {
        "stream": "anatomical",
        "seed": "042",
        "trial_key": "3243/S01/T01",
        "animal_id": "3243",
        "session": "S01",
        "trial": "T01",
        "phase": "experimental",
        "exit_number": "1",
        "sex": "F",
        "strain": "wt",
        "tx": "n/a",
        "experiment": "VASTcont",
        "drug": "n/a",
        "cohort": "",
        "researcher": "",
        "is_habituation": "0",
        "raw_syllable_id": "1",
        "bout_index": "0",
        "row_start": "0",
        "row_end_exclusive": "3",
        "bout_frames": "3",
        "bout_duration_s": "0.1",
        "bout_primary_state": "run",
    }
    base.update(kwargs)
    return base


def test_filter_bout_rows_defaults() -> None:
    rows = [
        _bout_row(experiment="VASTcont", strain="wt"),
        _bout_row(experiment="LASTalt", strain="wt"),
        _bout_row(experiment="VASTcont", strain="?"),
        _bout_row(experiment="VASTcont", strain="wt", sex=""),
    ]
    cfg = StimulusJoinFilterConfig()
    out = filter_bout_rows(rows, cfg)
    assert len(out) == 1
    assert out[0]["experiment"] == "VASTcont"
    assert out[0]["strain"] == "wt"


def test_filter_bout_rows_fail_fast_unmapped_strain() -> None:
    rows = [_bout_row(strain="het")]
    cfg = StimulusJoinFilterConfig()
    with pytest.raises(ValueError, match="unmapped strain"):
        filter_bout_rows(rows, cfg)


def test_mean_scalar_over_rows_averages_mapped_frames() -> None:
    values = np.array([10.0, 20.0, 30.0, 40.0], dtype=np.float64)
    src = np.array([0, 1, 1, 3], dtype=np.int64)
    mean = mean_scalar_over_rows(values, src, row_start=1, row_end_exclusive=3)
    assert mean == pytest.approx(20.0)


def test_enrich_bout_row_with_stimulus() -> None:
    row = _bout_row(row_start="0", row_end_exclusive="2")
    stimulus = TrialStimulusFrames(
        motor_fb=np.array([0.1, 0.3, 0.5], dtype=np.float64),
        dist_to_exit_px=np.array([100.0, 200.0, 300.0], dtype=np.float64),
    )
    src = np.array([0, 1, 2], dtype=np.int64)
    out = enrich_bout_row_with_stimulus(row, stimulus=stimulus, source_frame_indices=src)
    assert out["bout_mean_duty"] == pytest.approx(0.2)
    assert out["bout_mean_dist_px"] == pytest.approx(150.0)


def _write_synthetic_trial_h5(path: Path, *, n_frames: int = 10) -> TrialKey:
    key = TrialKey(animal_id="3243", session="S01", trial="T01")
    duty = np.linspace(0.0, 1.0, n_frames, dtype=np.float32)
    dist = np.linspace(500.0, 50.0, n_frames, dtype=np.float32)
    with h5py.File(path, "w") as h5:
        g = h5.create_group(key.path().lstrip("/"))
        fb = np.zeros(n_frames, dtype=FEEDBACK_ROW_DTYPE)
        fb["frame_index"] = np.arange(n_frames, dtype=np.uint32)
        fb["motor_fb"] = duty
        write_feedback_table(g, fb)
        xy = np.zeros(n_frames, dtype=XY_ROW_DTYPE)
        xy["frame_index"] = np.arange(n_frames, dtype=np.uint32)
        xy["dist_to_exit_px"] = dist
        write_xy_table(g, "spot", xy, fps=30.0)
    return key


def test_read_trial_stimulus_frames_and_verify(tmp_path: Path) -> None:
    h5_path = tmp_path / "trial.h5"
    key = _write_synthetic_trial_h5(h5_path)
    with h5py.File(h5_path, "r") as h5:
        g = h5[key.path().lstrip("/")]
        frames = read_trial_stimulus_frames(g)
    assert frames is not None
    assert frames.motor_fb.shape == (10,)
    assert frames.dist_to_exit_px[0] == pytest.approx(500.0)
    report = verify_trial_stimulus_h5(h5_path, key)
    assert report.ok
