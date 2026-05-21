"""inference_backend registry and skip-existing helpers (Phase C C2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from maze.pipeline.inference_backend import (
    BACKEND_KIND_SLEAP_NN,
    DeepLabCutBackendStub,
    SleapNnBackend,
    find_existing_pose_output,
    get_backend,
    planned_slp_output_path,
)


def test_get_backend_sleap_nn() -> None:
    assert isinstance(get_backend("sleap_nn"), SleapNnBackend)
    assert isinstance(get_backend("sleap"), SleapNnBackend)


def test_get_backend_dlc_stub() -> None:
    assert isinstance(get_backend("deeplabcut_stub"), DeepLabCutBackendStub)


def test_get_backend_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown inference backend"):
        get_backend("not_a_backend")


def test_planned_slp_output_path_with_output_dir(tmp_path: Path) -> None:
    video = tmp_path / "sub" / "42_S01_T01.mp4"
    out_dir = tmp_path / "poses"
    planned = planned_slp_output_path(video, out_dir)
    assert planned == out_dir / "42_S01_T01.predictions.slp"


def test_planned_slp_output_path_beside_video(tmp_path: Path) -> None:
    video = tmp_path / "42_S01_T01.mp4"
    assert planned_slp_output_path(video, None) == video.with_suffix(".predictions.slp")


def test_find_existing_pose_output_priority(tmp_path: Path) -> None:
    video = tmp_path / "42_S01_T01.mp4"
    planned = video.with_suffix(".predictions.slp")
    manifest = tmp_path / "other.slp"
    manifest.touch()
    found = find_existing_pose_output(
        video_path=video,
        manifest_sleap=manifest,
        planned_out=planned,
    )
    assert found == manifest


def test_find_existing_pose_output_planned(tmp_path: Path) -> None:
    video = tmp_path / "42_S01_T01.mp4"
    planned = video.with_suffix(".predictions.slp")
    planned.touch()
    found = find_existing_pose_output(
        video_path=video,
        manifest_sleap=None,
        planned_out=planned,
    )
    assert found == planned


def test_deeplabcut_stub_run_raises() -> None:
    stub = DeepLabCutBackendStub()
    with pytest.raises(RuntimeError, match="not implemented"):
        stub.run(
            video_path=Path("v.mp4"),
            model_path=Path("m"),
            output_path=Path("o.slp"),
            device="cpu",
            batch_size=1,
        )


def test_get_backend_default_kind() -> None:
    assert get_backend("").name == BACKEND_KIND_SLEAP_NN
