"""Post-trial manifest built from controller H5 attrs."""

from __future__ import annotations

from pathlib import Path

import h5py

from maze.controller.acquisition.post_trial_analysis import manifest_from_controller_h5
from maze.pipeline.db.trial_key import TrialKey


def test_manifest_from_controller_h5_reads_sleap_path(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("E", "test1", "T01")
    sleap = tmp_path / "E_test1_T01.predictions.slp"
    sleap.touch()

    with h5py.File(db, "w") as h5:
        g = h5.create_group(key.path().lstrip("/"))
        g.attrs["video_path"] = str(tmp_path / "video.mp4")
        g.attrs["sleap_path"] = str(sleap)
        g.attrs["phase"] = "radial_arm"

    manifest = manifest_from_controller_h5(db, key)
    assert manifest.sleap_path == sleap
    assert manifest.input_h5_path == db
