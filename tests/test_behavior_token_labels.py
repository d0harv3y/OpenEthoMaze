"""Tests for behavior_token_labels scaffold and merge."""

from __future__ import annotations

from maze.kpms.behavior_ethogram.anchor_buckets import bout_token_rows_from_table
from maze.kpms.behavior_ethogram.behavior_token_labels import (
    init_behavior_token_labels,
    merge_behavior_token_label_rows,
    scaffold_behavior_token_label_rows,
    token_reference_stats_by_id,
)
from maze.kpms.behavior_ethogram.behavior_token_labels_contract import (
    BEHAVIOR_TOKEN_LABEL_FIELDS,
)
from maze.kpms.behavior_ethogram.locomotion import DEFAULT_LOCOMOTION_RULES, BoutTokenRow


def _table_row(
    *,
    token: int,
    speed: float,
    dheading: float = 0.1,
    ambiguous: int = 0,
    bout_index: int = 0,
    trial_key: str = "t1",
) -> dict[str, str]:
    return {
        "seed": "fit",
        "trial_key": trial_key,
        "bout_index": str(bout_index),
        "behavior_token": str(token),
        "bout_mean_speed_mps": str(speed),
        "bout_mean_abs_dheading": str(dheading),
        "ambiguous": str(ambiguous),
    }


def test_scaffold_behavior_token_label_rows_sorted_and_filtered() -> None:
    rows = bout_token_rows_from_table(
        [
            _table_row(token=10, speed=0.02, bout_index=0),
            _table_row(token=7, speed=0.22, bout_index=1),
        ],
        seed="fit",
    )
    out = scaffold_behavior_token_label_rows(rows, rules_doc=DEFAULT_LOCOMOTION_RULES, min_token_bouts=1)
    assert [int(r["behavior_token"]) for r in out] == [7, 10]
    assert out[0]["locomotion_tier"] == "fast_transit"
    assert out[0]["anchor_bucket"] == "moving"
    assert out[0]["behavior_name"] == ""


def test_min_token_bouts_excludes_rare_tokens() -> None:
    rows = bout_token_rows_from_table([_table_row(token=3, speed=0.2)], seed="fit")
    out = scaffold_behavior_token_label_rows(rows, rules_doc=DEFAULT_LOCOMOTION_RULES, min_token_bouts=5)
    assert out == []


def test_merge_preserves_curated_fields() -> None:
    scaffolded = [
        {
            "behavior_token": "7",
            "token_n_bouts": "100",
            "token_mean_speed_mps": "0.220000",
            "token_mean_abs_dheading": "0.100000",
            "locomotion_tier": "fast_transit",
            "behavior_name": "",
            "anchor_bucket": "moving",
            "reviewed_at": "",
            "reviewed_trial_key": "",
            "notes": "",
        }
    ]
    existing = [
        {
            "behavior_token": "7",
            "token_n_bouts": "50",
            "behavior_name": "groom",
            "anchor_bucket": "ignore",
            "reviewed_at": "2026-07-06T12:00:00",
            "reviewed_trial_key": "3245_S04_T06",
            "notes": "checked grid",
        }
    ]
    merged = merge_behavior_token_label_rows(scaffolded, existing, force=False)
    assert merged[0]["behavior_name"] == "groom"
    assert merged[0]["reviewed_at"] == "2026-07-06T12:00:00"
    assert merged[0]["token_n_bouts"] == "100"


def test_init_behavior_token_labels_writes_csv(tmp_path) -> None:
    rows = bout_token_rows_from_table(
        [_table_row(token=10, speed=0.05), _table_row(token=10, speed=0.06, bout_index=1)],
        seed="fit",
    )
    out_csv = tmp_path / "behavior_token_labels.csv"
    path, written = init_behavior_token_labels(
        token_rows=rows,
        rules_doc=DEFAULT_LOCOMOTION_RULES,
        out_csv=out_csv,
    )
    assert path == out_csv
    assert len(written) == 1
    assert int(written[0]["token_n_bouts"]) == 2
    text = out_csv.read_text(encoding="utf-8")
    assert text.splitlines()[0] == ",".join(BEHAVIOR_TOKEN_LABEL_FIELDS)


def test_token_reference_stats_ambiguous_only_token() -> None:
    rows = [
        BoutTokenRow(
            seed="fit",
            trial_key="t1",
            bout_index=0,
            behavior_token=4,
            bout_mean_speed_mps=0.12,
            bout_mean_abs_dheading=0.2,
            ambiguous=True,
            tier="",
        )
    ]
    stats = token_reference_stats_by_id(rows, rules_doc=DEFAULT_LOCOMOTION_RULES)
    assert stats[4].locomotion_tier == "ambiguous"
    assert stats[4].anchor_bucket == "ignore"
