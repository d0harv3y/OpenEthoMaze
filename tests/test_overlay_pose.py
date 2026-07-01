"""H5-first skeleton loading for unified overlay."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from maze.core.anatomy import STANDARD_NODE_NAMES
from maze.kpms.h5_pose import resolve_canonical_trial_h5
from maze.pipeline.db.trial_key import TrialKey
from maze.pipeline.io.file_discovery import TrialManifest
from maze.pipeline.tracking_io import write_anatomical_tracking
from maze.pipeline.viz.overlay_pose import (
    OverlayPoseProvenance,
    centroid_trajectory_from_skeleton,
    load_overlay_skeleton,
    resolve_overlay_tracking_h5,
    select_overlay_trajectory,
)


def _write_pose(h5_path: Path, key: TrialKey, *, frame_indices: list[int]) -> None:
    import h5py

    t = len(frame_indices)
    k = len(STANDARD_NODE_NAMES)
    x = np.zeros((t, k), dtype=np.float32)
    y = np.zeros((t, k), dtype=np.float32)
    for row, fi in enumerate(frame_indices):
        x[row, 0] = float(fi)
        y[row, 0] = float(row)
    with h5py.File(h5_path, "a") as h5:
        g = h5.require_group(key.path().lstrip("/"))
        write_anatomical_tracking(
            g,
            frame_index=np.asarray(frame_indices, dtype=np.uint32),
            x=x,
            y=y,
            score=np.full((t, k), 0.9, dtype=np.float32),
            node_names=STANDARD_NODE_NAMES,
            pose_source="sleap_live",
            fps=30.0,
            h5=h5,
        )


def test_resolve_overlay_tracking_h5_falls_back_to_tracking_db(tmp_path: Path) -> None:
    pipeline = tmp_path / "pipeline.h5"
    tracking = tmp_path / "tracking.h5"
    key = TrialKey("1", "S04", "T01")
    pipeline.touch()
    _write_pose(tracking, key, frame_indices=[100, 101, 102])

    manifest = TrialManifest(
        animal_id="1", session="S04", trial="T01", input_h5_path=Path("")
    )
    assert resolve_overlay_tracking_h5(manifest, pipeline, tracking) == tracking.resolve()
    assert resolve_canonical_trial_h5(manifest, pipeline) is None


def test_load_overlay_skeleton_samples_by_frame_index(tmp_path: Path) -> None:
    tracking = tmp_path / "tracking.h5"
    key = TrialKey("1", "S04", "T01")
    _write_pose(tracking, key, frame_indices=[100, 101, 102])

    manifest = TrialManifest(
        animal_id="1", session="S04", trial="T01", input_h5_path=Path("")
    )
    skel = load_overlay_skeleton(
        manifest=manifest,
        key=key,
        pipeline_db=tmp_path / "missing_pipeline.h5",
        tracking_db=tracking,
        sleap_path=None,
        render_start_frame=101,
        max_frames=1,
        px_per_cm=2.42,
        jump_filter_cm=10.0,
        jump_filter_lookahead_frames=3,
    ).skeleton
    assert skel is not None
    nose = skel.nodes["nose"]
    assert nose["x"][0] == pytest.approx(101.0)
    assert nose["y"][0] == pytest.approx(1.0)


def test_centroid_trajectory_from_skeleton() -> None:
    nodes = {
        "nose": {"x": np.array([0.0, 2.0]), "y": np.array([0.0, 2.0])},
        "tail": {"x": np.array([2.0, 4.0]), "y": np.array([2.0, 4.0])},
    }
    centroid = centroid_trajectory_from_skeleton(nodes, node_names=("nose", "tail"))
    assert centroid is not None
    x, y, valid = centroid
    assert x[0] == pytest.approx(1.0)
    assert y[0] == pytest.approx(1.0)
    assert valid[0]


def test_select_overlay_trajectory_auto_uses_pose_centroid_when_skeleton_present() -> None:
    nodes = {
        "nose": {"x": np.array([10.0]), "y": np.array([20.0])},
    }
    skeleton = type("S", (), {"nodes": nodes})()
    x, y, valid, _moving, label, _detail = select_overlay_trajectory(
        primary_point="spot_hybrid",
        amb_x=np.array([0.0]),
        amb_y=np.array([0.0]),
        amb_valid=np.array([True]),
        amb_is_moving=np.array([False]),
        skeleton=skeleton,
        pose=OverlayPoseProvenance(kind="sleap_sidecar", sleap_path="/x.slp"),
        fps=30.0,
        px_per_cm=2.42,
        preference="auto",
    )
    assert label.startswith("pose_centroid:")
    assert x[0] == pytest.approx(10.0)
    assert y[0] == pytest.approx(20.0)
    assert valid[0]


def test_select_overlay_trajectory_ambulation_preference() -> None:
    x, y, _v, _m, label, _detail = select_overlay_trajectory(
        primary_point="spot_hybrid",
        amb_x=np.array([3.0]),
        amb_y=np.array([4.0]),
        amb_valid=np.array([True]),
        amb_is_moving=np.array([True]),
        skeleton=type("S", (), {"nodes": {"nose": {"x": np.array([10.0]), "y": np.array([20.0])}}})(),
        pose=OverlayPoseProvenance(kind="sleap_sidecar"),
        fps=30.0,
        px_per_cm=2.42,
        preference="ambulation",
    )
    assert label == "ambulation_metrics:spot_hybrid"
    assert x[0] == pytest.approx(3.0)
    assert y[0] == pytest.approx(4.0)


def test_load_overlay_skeleton_prefers_h5_over_sleap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracking = tmp_path / "tracking.h5"
    key = TrialKey("1", "S04", "T01")
    _write_pose(tracking, key, frame_indices=[0, 1])

    manifest = TrialManifest(
        animal_id="1", session="S04", trial="T01", input_h5_path=Path("")
    )
    sleap = tmp_path / "fake.slp"
    sleap.write_text("x", encoding="utf-8")

    def _boom(*_a, **_k):
        raise AssertionError("sleap loader should not run when H5 pose is present")

    monkeypatch.setattr("maze.pipeline.viz.overlay_pose._skeleton_from_sleap_path", _boom)

    skel = load_overlay_skeleton(
        manifest=manifest,
        key=key,
        pipeline_db=tracking,
        tracking_db=None,
        sleap_path=str(sleap),
        render_start_frame=0,
        max_frames=1,
        px_per_cm=2.42,
        jump_filter_cm=10.0,
        jump_filter_lookahead_frames=3,
    ).skeleton
    assert skel is not None
