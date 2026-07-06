"""Tests for behavior-token exemplar selection and grid composition."""

from __future__ import annotations

import cv2
import numpy as np

from maze.kpms.behavior_ethogram.paths import resolve_stage_iii_dir
from maze.kpms.behavior_ethogram.token_exemplars import (
    overlay_clip_fits_usable_frames,
    pattern_match_from_bout_row,
    select_token_bout_exemplars,
    unique_behavior_tokens,
)
from maze.kpms.behavior_ethogram.token_grid_compose import compose_grid_video, grid_layout


def _bout_row(
    *,
    trial_key: str = "t1",
    bout_index: int,
    behavior_token: int,
    row_start: int,
    row_end_exclusive: int,
    speed: float = 0.2,
    ambiguous: int = 0,
    seed: str = "042",
) -> dict[str, str]:
    return {
        "stream": "anatomical",
        "seed": seed,
        "trial_key": trial_key,
        "bout_index": str(bout_index),
        "raw_syllable_id": "3",
        "row_start": str(row_start),
        "row_end_exclusive": str(row_end_exclusive),
        "bout_frames": str(row_end_exclusive - row_start),
        "bout_duration_s": "0.1",
        "bout_mean_speed_mps": str(speed),
        "bout_mean_abs_dheading": "0.1",
        "bout_mean_blob_area_px2": "100",
        "bout_iqr_speed_mps": "0.02",
        "bout_iqr_abs_dheading": "0.02",
        "bout_iqr_blob_area_px2": "10",
        "bout_net_dheading_rad": "0.0",
        "bout_straightness": "0.8",
        "bout_primary_state": "run",
        "ambiguous": str(ambiguous),
        "behavior_token": str(behavior_token),
    }


def test_pattern_match_from_bout_row_source_bounds() -> None:
    row = _bout_row(bout_index=0, behavior_token=7, row_start=1, row_end_exclusive=4)
    match = pattern_match_from_bout_row("t1", row, [100, 110, 120, 130, 140])
    assert match is not None
    assert match.source_start_frame == 110
    assert match.source_end_frame == 130


def test_select_token_bout_exemplars_prefers_non_ambiguous() -> None:
    rows = [
        _bout_row(
            trial_key="t1",
            bout_index=0,
            behavior_token=7,
            row_start=0,
            row_end_exclusive=3,
            ambiguous=1,
        ),
        _bout_row(
            trial_key="t2",
            bout_index=0,
            behavior_token=7,
            row_start=0,
            row_end_exclusive=3,
            speed=0.21,
        ),
    ]
    src = {"t1": [10, 11, 12], "t2": [20, 21, 22]}
    matches = select_token_bout_exemplars(
        rows,
        behavior_token=7,
        trial_source_frames=src,
        seed="042",
        max_exemplars=2,
    )
    assert matches[0].trial_key == "t2"


def test_overlay_clip_fits_usable_frames_rejects_past_video_end() -> None:
    row = _bout_row(bout_index=0, behavior_token=6, row_start=0, row_end_exclusive=3)
    src = np.array([3340, 3345, 3350], dtype=np.int64)
    match = pattern_match_from_bout_row("t1", row, src)
    assert match is not None
    # 1s pad @ 30fps => clip_start=3310; usable end 3295 rejects
    assert not overlay_clip_fits_usable_frames(
        match,
        fps=30.0,
        padding_s=1.0,
        usable_frame_end_exclusive=3295,
    )
    assert overlay_clip_fits_usable_frames(
        match,
        fps=30.0,
        padding_s=1.0,
        usable_frame_end_exclusive=3400,
    )


def test_select_token_bout_exemplars_skips_nonfitting_overlay_clips() -> None:
    rows = [
        _bout_row(
            trial_key="bad",
            bout_index=0,
            behavior_token=6,
            row_start=0,
            row_end_exclusive=3,
        ),
        _bout_row(
            trial_key="good",
            bout_index=0,
            behavior_token=6,
            row_start=0,
            row_end_exclusive=3,
        ),
    ]
    src = {
        "bad": [3340, 3345, 3350],
        "good": [100, 105, 110],
    }
    matches = select_token_bout_exemplars(
        rows,
        behavior_token=6,
        trial_source_frames=src,
        seed="042",
        max_exemplars=2,
        padding_s=1.0,
        trial_fps={"bad": 30.0, "good": 30.0},
        trial_usable_overlay_frame_end={"bad": 3295, "good": 500},
        require_overlay_clip_fit=True,
    )
    assert [m.trial_key for m in matches] == ["good"]


def test_exemplar_seed_is_reproducible_and_changes_selection() -> None:
    rows = [
        _bout_row(trial_key=f"t{i}", bout_index=0, behavior_token=6, row_start=0, row_end_exclusive=3)
        for i in range(6)
    ]
    src = {f"t{i}": [10 + i, 11 + i, 12 + i] for i in range(6)}
    kwargs = dict(
        bout_rows=rows,
        behavior_token=6,
        trial_source_frames=src,
        seed="042",
        max_exemplars=3,
    )
    a = select_token_bout_exemplars(**kwargs, exemplar_seed=7)
    b = select_token_bout_exemplars(**kwargs, exemplar_seed=7)
    c = select_token_bout_exemplars(**kwargs, exemplar_seed=99)
    assert [m.trial_key for m in a] == [m.trial_key for m in b]
    assert len({m.trial_key for m in a}) == 3
    assert [m.trial_key for m in a] != [m.trial_key for m in c]


def test_unique_behavior_tokens_filters_seed() -> None:
    rows = [
        _bout_row(bout_index=0, behavior_token=3, row_start=0, row_end_exclusive=2, seed="042"),
        _bout_row(bout_index=1, behavior_token=9, row_start=2, row_end_exclusive=4, seed="067"),
    ]
    assert unique_behavior_tokens(rows, seed="042") == (3,)


def test_resolve_stage_iii_dir_prefers_pooled_when_seed_fit(tmp_path) -> None:
    root = tmp_path / "kpms"
    pooled = root / "behavior_ethogram" / "stage_iii"
    pooled.mkdir(parents=True)
    (pooled / "bout_behavior_tokens.csv").write_text("behavior_token\n", encoding="utf-8")
    resolved = resolve_stage_iii_dir(root, seed="fit")
    assert resolved == pooled


def test_token_grid_clips_dir_under_grid_movies(tmp_path) -> None:
    from maze.kpms.behavior_ethogram.paths import token_grid_clips_dir

    stage = tmp_path / "behavior_ethogram" / "stage_iii" / "seed_fit"
    clips = token_grid_clips_dir(stage, 10)
    assert clips == stage / "grid_movies" / "clips" / "token_10"


def test_grid_layout_square() -> None:
    assert grid_layout(9) == (3, 3)
    assert grid_layout(10) == (3, 4)


def test_compose_grid_video_writes_mp4(tmp_path) -> None:
    clips = []
    for color in ((0, 0, 255), (0, 255, 0), (255, 0, 0)):
        path = tmp_path / f"clip_{len(clips)}.mp4"
        writer = cv2.VideoWriter(
            str(path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            10.0,
            (80, 60),
        )
        frame = np.zeros((60, 80, 3), dtype=np.uint8)
        frame[:, :] = color
        for _ in range(3):
            writer.write(frame)
        writer.release()
        clips.append(path)

    out = compose_grid_video(clips, tmp_path / "grid.mp4", cell_labels=["a", "b", "c"])
    assert out.is_file()
    cap = cv2.VideoCapture(str(out))
    assert cap.isOpened()
    ok, frame = cap.read()
    cap.release()
    assert ok
    assert frame.shape[0] > 0
