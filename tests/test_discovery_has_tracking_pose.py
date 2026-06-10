"""Discovery manifest has_tracking_pose column and sync attrs (Phase T2c)."""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.kpms.manifest_subset import SubsetConfig, filter_manifests, has_tracking_pose
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.discovery_sync import sync_discovery_into_h5
from maze.pipeline.io.file_discovery import (
    enrich_manifests_has_tracking_pose,
    load_manifest_csv,
    save_manifest_csv,
    DiscoveryResult,
    trial_manifest_csv_row_values,
)
from maze.pipeline.tracking_io import write_anatomical_tracking

from conftest import make_manifest


def _write_pose(db: Path, key: TrialKey) -> None:
    k = len(STANDARD_NODE_NAMES)
    with h5py.File(db, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_anatomical_tracking(
            g,
            frame_index=np.arange(4, dtype=np.uint32),
            x=np.ones((4, k), dtype=np.float32),
            y=np.full((4, k), 2.0, dtype=np.float32),
            score=np.full((4, k), 0.9, dtype=np.float32),
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
            h5=h5,
        )


def test_enrich_manifest_sets_has_tracking_pose_without_sleap(tmp_path: Path) -> None:
    db = tmp_path / "trials.h5"
    key = TrialKey("5", "S01", "T01")
    _write_pose(db, key)

    manifest = make_manifest(
        animal_id="5",
        session="S01",
        trial="T01",
        input_h5_path=db,
        sleap_path=None,
    )
    enrich_manifests_has_tracking_pose([manifest], db_path=db)

    assert manifest.has_tracking_pose is True
    assert manifest.sleap_path is None
    row = trial_manifest_csv_row_values(manifest)
    assert row[-2] == "1"


def test_load_manifest_csv_reads_has_tracking_pose(tmp_path: Path) -> None:
    csv_path = tmp_path / "manifest.csv"
    manifest = make_manifest(
        animal_id="8",
        session="S02",
        trial="T03",
        input_h5_path=tmp_path / "in.h5",
        sleap_path=None,
        has_tracking_pose=True,
    )
    save_manifest_csv(DiscoveryResult(trials=[manifest]), csv_path)

    loaded = load_manifest_csv(csv_path)[0]
    assert loaded.has_tracking_pose is True
    assert has_tracking_pose(loaded) is True


def test_sync_discovery_writes_has_tracking_pose_attr(tmp_path: Path) -> None:
    db = tmp_path / "cohort.h5"
    key = TrialKey("3", "S01", "T01")
    _write_pose(db, key)
    (tmp_path / "3_S01_T01.mp4").touch()

    sync_discovery_into_h5(db, data_dirs=[tmp_path])

    with h5py.File(db, "r") as h5:
        g = h5["3/S01/T01"]
        assert int(g.attrs["has_tracking_pose"]) == 1


def test_filter_keeps_h5_pose_from_csv_flag_without_probe(tmp_path: Path) -> None:
    manifest = make_manifest(animal_id="2", sleap_path=None, has_tracking_pose=True)
    cfg = SubsetConfig(db_path=tmp_path / "missing.h5")
    out = filter_manifests([manifest], cfg)
    assert [m.animal_id for m in out] == ["2"]
