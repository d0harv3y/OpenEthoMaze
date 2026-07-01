"""Tests for harness anchor bucket inference (grammar auto + AR-HMM export)."""

from __future__ import annotations

from maze.kpms.behavior_ethogram.anchor_buckets import (
    anchor_bucket_from_locomotion_tier,
    behavior_name_from_pattern,
    bout_token_rows_from_table,
    infer_anchor_bucket_from_mean_speed,
    token_anchor_buckets_from_bout_rows,
)
from maze.kpms.behavior_ethogram.grammar_contract import CANDIDATE_SEQUENCE_FIELDS
from maze.kpms.behavior_ethogram.grammar_rules import rules_from_auto_candidates


def test_behavior_name_from_pattern() -> None:
    assert behavior_name_from_pattern((3, 7, 7)) == "pat_3_7_7"


def test_infer_anchor_bucket_from_mean_speed() -> None:
    assert infer_anchor_bucket_from_mean_speed(0.04) == "still"
    assert infer_anchor_bucket_from_mean_speed(0.20) == "moving"
    assert infer_anchor_bucket_from_mean_speed(0.10) == "ignore"
    assert infer_anchor_bucket_from_mean_speed(float("nan")) == "ignore"


def test_anchor_bucket_from_locomotion_tier() -> None:
    assert anchor_bucket_from_locomotion_tier("still") == "still"
    assert anchor_bucket_from_locomotion_tier("fast_transit") == "moving"
    assert anchor_bucket_from_locomotion_tier("ambiguous") == "ignore"


def test_token_anchor_buckets_from_slow_and_fast_bouts() -> None:
    table = [
        {
            "seed": "042",
            "trial_key": "t1",
            "bout_index": "0",
            "behavior_token": "0",
            "bout_mean_speed_mps": "0.02",
            "bout_mean_abs_dheading": "0.05",
            "ambiguous": "0",
        },
        {
            "seed": "042",
            "trial_key": "t1",
            "bout_index": "1",
            "behavior_token": "1",
            "bout_mean_speed_mps": "0.25",
            "bout_mean_abs_dheading": "0.05",
            "ambiguous": "0",
        },
    ]
    rows = bout_token_rows_from_table(table, seed="042")
    buckets = token_anchor_buckets_from_bout_rows(rows)
    assert buckets[0] == "still"
    assert buckets[1] == "moving"


def test_rules_from_auto_candidates(tmp_path) -> None:
    path = tmp_path / "c.csv"
    header = ",".join(CANDIDATE_SEQUENCE_FIELDS)
    path.write_text(
        f"{header}\n"
        '"[3, 7]",2,5,2,0.20,,,,0,,,,,\n'
        '"[12]",1,10,3,0.03,,,,0,,,,,\n'
        '"[5, 5]",2,3,2,0.10,,,,0,,,,,\n',
        encoding="utf-8",
    )
    doc = rules_from_auto_candidates(path, fit_id="seed_042")
    assert doc.rules[0].behavior_name == "pat_3_7"
    assert doc.behavior_anchor_buckets["pat_3_7"] == "moving"
    assert doc.behavior_anchor_buckets["pat_12"] == "still"
    assert doc.behavior_anchor_buckets["pat_5_5"] == "ignore"
