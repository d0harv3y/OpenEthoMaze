"""Tests for syllable-bout n-gram mining (Option A discovery)."""

from __future__ import annotations

import json

from maze.kpms.behavior_ethogram.grammar_mine import (
    bout_syllable_ids,
    mine_ngram_candidates,
    read_candidate_sequences_csv,
    write_candidate_sequences_csv,
)


def test_bout_syllable_ids_collapses_runs() -> None:
    z = [3, 3, 3, 7, 7, 1]
    assert bout_syllable_ids(z) == [3, 7, 1]


def test_mine_ngram_candidates_counts_across_trials() -> None:
    trials = {
        "t1": [1, 1, 2, 2, 3],
        "t2": [1, 1, 2, 4],
    }
    mined = mine_ngram_candidates(trials, min_count=2, max_n=2)
    patterns = {m.pattern: m.count for m in mined}
    assert patterns[(1, 2)] == 2
    assert patterns[(1,)] == 2


def test_write_and_read_candidate_sequences_csv_round_trip(tmp_path) -> None:
    mined = mine_ngram_candidates({"t": [1, 1, 2, 2]}, min_count=1, max_n=2)
    path = tmp_path / "candidates.csv"
    write_candidate_sequences_csv(path, mined)
    rows = read_candidate_sequences_csv(path)
    assert rows
    assert json.loads(rows[0]["pattern_json"]) == list(mined[0].pattern)
