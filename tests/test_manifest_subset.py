"""kpMS manifest_subset filters (Phase A A6)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.kpms.manifest_subset import SubsetConfig, filter_manifests, has_tracking_pose
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.tracking_io import write_anatomical_tracking

from conftest import make_manifest


def _sample_manifests() -> list:
    return [
        make_manifest(animal_id="1", sleap_path=Path("a.slp"), is_habituation=False),
        make_manifest(animal_id="2", sleap_path=None, is_habituation=False),
        make_manifest(animal_id="3", sleap_path=Path("b.slp"), is_habituation=True),
    ]


def test_filter_manifests_requires_sleap_by_default() -> None:
    cfg = SubsetConfig(include_habituation=True)
    out = filter_manifests(_sample_manifests(), cfg)
    assert [m.animal_id for m in out] == ["1", "3"]


def test_filter_manifests_excludes_habituation_when_disabled() -> None:
    cfg = SubsetConfig(include_habituation=False)
    out = filter_manifests(_sample_manifests(), cfg)
    assert [m.animal_id for m in out] == ["1"]


def test_filter_manifests_excludes_experimental_when_disabled() -> None:
    cfg = SubsetConfig(include_experimental=False, include_habituation=True)
    out = filter_manifests(_sample_manifests(), cfg)
    assert [m.animal_id for m in out] == ["3"]


def test_has_tracking_pose_and_filter_keeps_h5_only(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("2", "S01", "T01")
    k = len(STANDARD_NODE_NAMES)
    with h5py.File(db, "w") as h5:
        g = h5.create_group(key.path().lstrip("/"))
        write_anatomical_tracking(
            g,
            frame_index=np.arange(5, dtype=np.uint32),
            x=np.ones((5, k), dtype=np.float32),
            y=np.full((5, k), 2.0, dtype=np.float32),
            score=np.full((5, k), 0.9, dtype=np.float32),
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
            h5=h5,
        )

    manifest = make_manifest(animal_id="2", sleap_path=None, input_h5_path=db)
    assert has_tracking_pose(manifest, db)
    cfg = SubsetConfig(db_path=db)
    out = filter_manifests([manifest], cfg)
    assert [m.animal_id for m in out] == ["2"]
