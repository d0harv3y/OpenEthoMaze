"""Tests for grammar candidate exemplar sidecar (S3.2+)."""

from __future__ import annotations

import json

from maze.kpms.behavior_ethogram.grammar_contract import (
    CANDIDATE_SEQUENCE_FIELDS,
    GRAMMAR_CANDIDATE_EXEMPLARS_SCHEMA,
)
from maze.kpms.behavior_ethogram.grammar_exemplars import (
    load_pattern_exemplars,
    read_candidate_exemplars_json,
)
from maze.kpms.behavior_ethogram.grammar_matches import PatternMatch
from maze.kpms.behavior_ethogram.grammar_mine import (
    MinedSequence,
    write_candidate_artifacts,
    write_candidate_sequences_csv,
)


def test_candidate_csv_excludes_exemplar_columns(tmp_path) -> None:
    path = tmp_path / "c.csv"
    write_candidate_sequences_csv(
        path,
        [
            MinedSequence(
                pattern=(1, 2),
                count=3,
                n_trials=2,
                example_trial_keys=("t1",),
            )
        ],
    )
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert "example_trial_keys" not in header
    assert "example_matches_json" not in header
    assert header == ",".join(CANDIDATE_SEQUENCE_FIELDS)


def test_write_candidate_artifacts_writes_sidecar(tmp_path) -> None:
    match = PatternMatch(
        trial_key="t1",
        bout_start_index=0,
        bout_end_exclusive=2,
        row_start=0,
        row_end_exclusive=6,
        source_start_frame=10,
        source_end_frame=15,
    )
    cand = MinedSequence(
        pattern=(3, 7),
        count=2,
        n_trials=1,
        example_trial_keys=("t1",),
        example_matches_json=json.dumps([match.to_dict()]),
    )
    csv_path, ex_path = write_candidate_artifacts(tmp_path, [cand], fit_id="seed_042")
    assert csv_path.is_file()
    assert ex_path.is_file()
    doc = read_candidate_exemplars_json(ex_path)
    assert "[3, 7]" in doc
    assert doc["[3, 7]"].example_trial_keys == ("t1",)
    assert len(doc["[3, 7]"].example_matches) == 1
    raw = json.loads(ex_path.read_text(encoding="utf-8"))
    assert raw["schema"] == GRAMMAR_CANDIDATE_EXEMPLARS_SCHEMA


def test_load_pattern_exemplars_prefers_sidecar(tmp_path) -> None:
    cand = MinedSequence(
        pattern=(5,),
        count=4,
        n_trials=2,
        example_trial_keys=("t1",),
        example_matches_json="[]",
    )
    write_candidate_artifacts(tmp_path, [cand], fit_id="seed_042")
    row = {"pattern_json": "[5]", "example_trial_keys": "legacy", "example_matches_json": "[]"}
    ex = load_pattern_exemplars(tmp_path, "[5]", candidates_row=row)
    assert ex.example_trial_keys == ("t1",)
