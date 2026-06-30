"""S0 contract tests: producer-agnostic Behavior labeling artifact.

A synthetic ``BehaviorLabeling`` stands in for a "dummy producer"; the
acceptance gate is that it writes the three-file artifact and reads back
identically, and that the derived bout CSV is a correct RLE on the
source-frame timeline (including frame gaps).
"""

from __future__ import annotations

import numpy as np
import pytest

from maze.kpms.behavior_ethogram.labeling import (
    UNLABELED,
    BehaviorLabeling,
    TrialFrameLabels,
    labeling_to_bouts,
    read_behavior_bouts_csv,
    read_behavior_labeling,
    write_behavior_labeling,
)
from maze.kpms.behavior_ethogram.paths import (
    behavior_bouts_csv,
    behavior_frames_h5,
    behavior_provenance_json,
    producer_dir,
)


def _dummy_labeling() -> BehaviorLabeling:
    # Trial A: a gap between source frames 11 and 13 (frame 12 dropped upstream).
    trial_a = TrialFrameLabels(
        trial_key="1-S01-T01",
        source_frame_index=np.array([10, 11, 13, 14, 15, 16, 17, 20], dtype=np.int64),
        behavior_id=np.array([0, 0, 2, 2, 2, UNLABELED, UNLABELED, 3], dtype=np.int32),
    )
    trial_b = TrialFrameLabels(
        trial_key="1-S01-T02",
        source_frame_index=np.array([0, 1, 2, 3], dtype=np.int64),
        behavior_id=np.array([2, 2, 0, 0], dtype=np.int32),
    )
    return BehaviorLabeling(
        producer="dummy",
        fit_id="seed_042",
        fps=20.0,
        trials=(trial_a, trial_b),
        behavior_names={0: "pause", 2: "locomote", 3: "rear"},
        params={"threshold_mps": 0.02},
        input_hashes={"results_apply.h5": "deadbeef"},
    )


def test_write_read_round_trip(tmp_path) -> None:
    art = producer_dir(tmp_path, "dummy", "seed_042")
    labeling = _dummy_labeling()
    write_behavior_labeling(art, labeling)

    assert behavior_frames_h5(art).is_file()
    assert behavior_bouts_csv(art).is_file()
    assert behavior_provenance_json(art).is_file()

    loaded = read_behavior_labeling(art)
    assert loaded.producer == "dummy"
    assert loaded.fit_id == "seed_042"
    assert loaded.fps == pytest.approx(20.0)
    assert loaded.behavior_names == {0: "pause", 2: "locomote", 3: "rear"}
    assert len(loaded.trials) == 2

    for original, got in zip(labeling.trials, loaded.trials):
        assert got.trial_key == original.trial_key
        np.testing.assert_array_equal(got.source_frame_index, original.source_frame_index)
        np.testing.assert_array_equal(got.behavior_id, original.behavior_id)


def test_rle_bouts_use_source_frame_bounds_and_skip_unlabeled() -> None:
    bouts = labeling_to_bouts(_dummy_labeling())
    trial_a = [b for b in bouts if b.trial_key == "1-S01-T01"]

    # Unlabeled run is dropped; bout_index stays contiguous per trial.
    assert [b.behavior_id for b in trial_a] == [0, 2, 3]
    assert [b.bout_index for b in trial_a] == [0, 1, 2]

    pause, loco, rear = trial_a
    # start/end are SOURCE frame indices (note the 11->13 gap inside loco).
    assert (pause.start_frame, pause.end_frame, pause.n_frames) == (10, 11, 2)
    assert (loco.start_frame, loco.end_frame, loco.n_frames) == (13, 15, 3)
    assert (rear.start_frame, rear.end_frame, rear.n_frames) == (20, 20, 1)
    # duration is labeled-row count / fps, independent of source-frame gaps.
    assert loco.duration_s == pytest.approx(3.0 / 20.0)
    assert loco.behavior_name == "locomote"


def test_include_unlabeled_bouts_flag() -> None:
    labeling = _dummy_labeling()
    with_unlabeled = labeling_to_bouts(labeling, include_unlabeled=True)
    trial_a = [b for b in with_unlabeled if b.trial_key == "1-S01-T01"]
    assert any(b.behavior_id == UNLABELED for b in trial_a)


def test_bouts_csv_matches_in_memory_rle(tmp_path) -> None:
    art = producer_dir(tmp_path, "dummy", "seed_042")
    labeling = _dummy_labeling()
    write_behavior_labeling(art, labeling)
    from_csv = read_behavior_bouts_csv(behavior_bouts_csv(art))
    in_memory = labeling_to_bouts(labeling)
    assert from_csv == in_memory


def test_provenance_counts_labeled_frames(tmp_path) -> None:
    import json

    art = producer_dir(tmp_path, "dummy", "seed_042")
    write_behavior_labeling(art, _dummy_labeling())
    prov = json.loads(behavior_provenance_json(art).read_text(encoding="utf-8"))
    # Trial A has 2 unlabeled of 8; trial B fully labeled (4). 6 + 4 = 10.
    assert prov["n_labeled_frames"] == 10
    assert prov["n_trials"] == 2
    assert prov["schema"] == "behavior_labeling_v1"


def test_source_frame_index_must_be_strictly_increasing() -> None:
    with pytest.raises(ValueError):
        TrialFrameLabels(
            trial_key="bad",
            source_frame_index=np.array([0, 2, 2, 3], dtype=np.int64),
            behavior_id=np.array([1, 1, 1, 1], dtype=np.int32),
        )


def test_length_mismatch_rejected() -> None:
    with pytest.raises(ValueError):
        TrialFrameLabels(
            trial_key="bad",
            source_frame_index=np.array([0, 1, 2], dtype=np.int64),
            behavior_id=np.array([1, 1], dtype=np.int32),
        )


def test_empty_trial_produces_no_bouts(tmp_path) -> None:
    empty = BehaviorLabeling(
        producer="dummy",
        fit_id="seed_000",
        fps=30.0,
        trials=(
            TrialFrameLabels(
                trial_key="empty",
                source_frame_index=np.array([], dtype=np.int64),
                behavior_id=np.array([], dtype=np.int32),
            ),
        ),
    )
    art = producer_dir(tmp_path, "dummy", "seed_000")
    write_behavior_labeling(art, empty)
    assert labeling_to_bouts(empty) == []
    loaded = read_behavior_labeling(art)
    assert len(loaded.trials) == 1
    assert len(loaded.trials[0]) == 0
