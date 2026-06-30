"""Tests for Option D producer → S0 BehaviorLabeling export."""

from __future__ import annotations

import numpy as np

from maze.kpms.behavior_ethogram.labeling import UNLABELED, read_behavior_labeling
from maze.kpms.behavior_ethogram.producer_option_d import trial_frame_labels_from_bout_rows


def test_trial_frame_labels_from_bout_rows_maps_tokens_to_frame_ranges() -> None:
    sfi = np.array([10, 11, 12, 13, 14], dtype=np.int64)
    bout_rows = [
        {
            "bout_index": "0",
            "row_start": "0",
            "row_end_exclusive": "2",
            "behavior_token": "3",
        },
        {
            "bout_index": "1",
            "row_start": "2",
            "row_end_exclusive": "5",
            "behavior_token": "7",
        },
    ]
    trial = trial_frame_labels_from_bout_rows("1-S01-T01", sfi, bout_rows)
    np.testing.assert_array_equal(trial.source_frame_index, sfi)
    assert list(trial.behavior_id) == [3, 3, 7, 7, 7]


def test_trial_frame_labels_leaves_gaps_unlabeled() -> None:
    sfi = np.array([0, 1, 2], dtype=np.int64)
    bout_rows = [
        {"bout_index": "0", "row_start": "0", "row_end_exclusive": "1", "behavior_token": "1"},
    ]
    trial = trial_frame_labels_from_bout_rows("t", sfi, bout_rows)
    assert trial.behavior_id[0] == 1
    assert trial.behavior_id[1] == UNLABELED


def test_read_exported_labeling_round_trip(tmp_path) -> None:
    from maze.kpms.behavior_ethogram.labeling import BehaviorLabeling, TrialFrameLabels, write_behavior_labeling

    art = tmp_path / "prod"
    write_behavior_labeling(
        art,
        BehaviorLabeling(
            producer="bout_arhmm",
            fit_id="seed_042",
            fps=30.0,
            trials=(
                TrialFrameLabels(
                    trial_key="1-S01-T01",
                    source_frame_index=np.array([0, 1], dtype=np.int64),
                    behavior_id=np.array([2, 2], dtype=np.int32),
                ),
            ),
            behavior_names={2: "token_2"},
        ),
    )
    loaded = read_behavior_labeling(art)
    assert loaded.producer == "bout_arhmm"
    assert loaded.behavior_names[2] == "token_2"
