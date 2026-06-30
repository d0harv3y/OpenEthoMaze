"""Tests for syllable-sequence grammar application."""

from __future__ import annotations

import numpy as np

from maze.kpms.behavior_ethogram.grammar_rules import (
    GrammarRule,
    GrammarRules,
    grammar_rules_to_json_dict,
    label_bouts_with_grammar,
    read_grammar_rules_json,
    rules_from_curated_candidates,
    write_grammar_rules_json,
)
from maze.kpms.behavior_ethogram.labeling import UNLABELED
from maze.kpms.behavior_ethogram.producer_option_a import (
    SyllableBoutSpan,
    trial_frame_labels_from_grammar,
)


def test_label_bouts_longest_pattern_wins() -> None:
    rules = [
        GrammarRule(pattern=(3,), behavior_name="pause", priority=1),
        GrammarRule(pattern=(3, 7, 7), behavior_name="groom", priority=10),
    ]
    names = label_bouts_with_grammar([3, 7, 7, 3], rules)
    assert names == ["groom", "groom", "groom", "pause"]


def test_label_bouts_unmatched_stays_none() -> None:
    rules = [GrammarRule(pattern=(9, 9), behavior_name="rear", priority=1)]
    names = label_bouts_with_grammar([1, 2, 3], rules)
    assert names == [None, None, None]


def test_trial_frame_labels_from_grammar_maps_bout_spans() -> None:
    sfi = np.array([10, 11, 12, 13], dtype=np.int64)
    bouts = [
        SyllableBoutSpan(3, 0, 0, 2),
        SyllableBoutSpan(7, 1, 2, 4),
    ]
    names = ["locomote", "locomote"]
    trial = trial_frame_labels_from_grammar(
        "t1",
        sfi,
        bouts,
        names,
        {"locomote": 0},
    )
    assert list(trial.behavior_id) == [0, 0, 0, 0]
    assert trial.behavior_id[0] != UNLABELED


def test_rules_from_curated_candidates_builds_doc(tmp_path) -> None:
    path = tmp_path / "c.csv"
    header = ",".join(
        [
            "pattern_json",
            "pattern_len",
            "count",
            "n_trials",
            "example_trial_keys",
            "example_matches_json",
            "mean_speed_mps",
            "mean_abs_dheading",
            "mean_straightness",
            "mean_blob_area_px2",
            "must_review_overlay",
            "behavior_name",
            "anchor_bucket",
            "reviewed_at",
            "reviewed_trial_key",
            "notes",
        ]
    )
    path.write_text(
        f'{header}\n'
        '"[3, 7]",2,5,2,t1,,,,,,0,groom,ignore,2026-06-30T00:00:00+00:00,t1,\n',
        encoding="utf-8",
    )
    doc = rules_from_curated_candidates(path, fit_id="seed_042")
    assert doc.rules[0].behavior_name == "groom"
    assert doc.behavior_anchor_buckets["groom"] == "ignore"


def test_grammar_rules_json_round_trip(tmp_path) -> None:
    doc = GrammarRules(
        fit_id="seed_042",
        rules=(GrammarRule(pattern=(3, 7), behavior_name="groom", priority=5),),
    )
    path = tmp_path / "rules.json"
    write_grammar_rules_json(path, doc)
    loaded = read_grammar_rules_json(path)
    assert loaded.fit_id == "seed_042"
    assert loaded.rules[0].behavior_name == "groom"
    assert grammar_rules_to_json_dict(loaded)["schema"] == "grammar_rules_v1"
