"""S3.2 grammar pattern-match exemplars and preview helper."""

from __future__ import annotations

import json

from maze.kpms.behavior_ethogram.grammar_contract import CANDIDATE_SEQUENCE_FIELDS
from maze.kpms.behavior_ethogram.grammar_matches import (
    PatternMatch,
    attach_example_matches_to_candidates,
    clip_frames_for_match,
    example_matches_to_json,
    parse_example_matches_json,
    select_example_matches,
)
from maze.kpms.behavior_ethogram.grammar_mine import MinedSequence, write_candidate_sequences_csv


def _bout_row(
    *,
    trial_key: str = "t1",
    bout_index: int,
    raw_syllable_id: int,
    row_start: int,
    row_end_exclusive: int,
    speed: float = 0.2,
    ambiguous: int = 0,
) -> dict[str, str]:
    return {
        "stream": "kpms",
        "seed": "042",
        "trial_key": trial_key,
        "bout_index": str(bout_index),
        "raw_syllable_id": str(raw_syllable_id),
        "row_start": str(row_start),
        "row_end_exclusive": str(row_end_exclusive),
        "bout_mean_speed_mps": str(speed),
        "bout_mean_abs_dheading": "0.1",
        "bout_straightness": "0.8",
        "bout_mean_blob_area_px2": "100",
        "ambiguous": str(ambiguous),
        "bout_iqr_speed_mps": "0.02",
    }


def test_select_example_matches_prefers_non_ambiguous() -> None:
    rows = [
        _bout_row(trial_key="t1", bout_index=0, raw_syllable_id=3, row_start=0, row_end_exclusive=5),
        _bout_row(
            trial_key="t2",
            bout_index=0,
            raw_syllable_id=3,
            row_start=0,
            row_end_exclusive=5,
            ambiguous=1,
        ),
    ]
    by_trial = {
        "t1": [(0, rows[0])],
        "t2": [(0, rows[1])],
    }
    src = {"t1": [100, 101, 102, 103, 104], "t2": [200, 201, 202, 203, 204]}
    matches = select_example_matches((3,), ("t1", "t2"), by_trial, src, max_matches=2)
    assert matches[0].trial_key == "t1"


def test_attach_example_matches_writes_json_column(tmp_path) -> None:
    rows = [
        _bout_row(trial_key="t1", bout_index=0, raw_syllable_id=3, row_start=0, row_end_exclusive=3),
        _bout_row(trial_key="t1", bout_index=1, raw_syllable_id=7, row_start=3, row_end_exclusive=6),
    ]
    cand = MinedSequence(
        pattern=(3, 7),
        count=2,
        n_trials=1,
        example_trial_keys=("t1",),
    )
    attached = attach_example_matches_to_candidates(
        [cand],
        rows,
        {"t1": [10, 11, 12, 13, 14, 15]},
        seed="042",
    )[0]
    assert attached.example_matches_json
    matches = parse_example_matches_json(attached.example_matches_json)
    assert len(matches) == 1
    assert matches[0].source_start_frame == 10
    assert matches[0].source_end_frame == 15


def test_candidate_csv_includes_example_matches_json(tmp_path) -> None:
    match = PatternMatch(
        trial_key="t1",
        bout_start_index=0,
        bout_end_exclusive=2,
        row_start=0,
        row_end_exclusive=6,
        source_start_frame=10,
        source_end_frame=15,
    )
    path = tmp_path / "c.csv"
    write_candidate_sequences_csv(
        path,
        [
            MinedSequence(
                pattern=(3, 7),
                count=2,
                n_trials=1,
                example_trial_keys=("t1",),
                example_matches_json=example_matches_to_json((match,)),
            )
        ],
    )
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert "example_matches_json" in header
    assert header == ",".join(CANDIDATE_SEQUENCE_FIELDS)


def test_clip_frames_for_match_adds_padding() -> None:
    match = PatternMatch(
        trial_key="t1",
        bout_start_index=0,
        bout_end_exclusive=1,
        row_start=0,
        row_end_exclusive=3,
        source_start_frame=100,
        source_end_frame=110,
    )
    start, end = clip_frames_for_match(match, fps=10.0, padding_s=1.0)
    assert start == 90
    assert end == 120


def test_example_matches_json_round_trip() -> None:
    raw = example_matches_to_json(
        (
            PatternMatch(
                trial_key="1-S01-T01",
                bout_start_index=2,
                bout_end_exclusive=4,
                row_start=20,
                row_end_exclusive=40,
                source_start_frame=500,
                source_end_frame=520,
            ),
        )
    )
    loaded = parse_example_matches_json(raw)
    assert loaded[0].trial_key == "1-S01-T01"
    assert json.loads(raw)[0]["bout_start_index"] == 2
