"""S3.1 grammar curation: enrich, overlay gates, buckets, harness."""

from __future__ import annotations

import numpy as np

from maze.kpms.behavior_ethogram.anchor_store import IsMovingAnchor, TrialAnchorFrames, write_is_moving_anchor
from maze.kpms.behavior_ethogram.evaluate import evaluate_behavior_producer
from maze.kpms.behavior_ethogram.grammar_contract import CANDIDATE_SEQUENCE_FIELDS
from maze.kpms.behavior_ethogram.grammar_enrich import (
    compute_must_review_overlay,
    enrich_candidates_with_bout_scalars,
    flag_candidates_for_overlay_review,
    validate_curated_candidate_rows,
)
from maze.kpms.behavior_ethogram.grammar_mine import MinedSequence, write_candidate_sequences_csv
from maze.kpms.behavior_ethogram.grammar_rules import (
    GrammarRule,
    GrammarRules,
    read_grammar_rules_json,
    rules_from_curated_candidates,
    write_grammar_rules_json,
)
from maze.kpms.behavior_ethogram.labeling import BehaviorLabeling, TrialFrameLabels, write_behavior_labeling
from maze.kpms.behavior_ethogram.paths import anchor_dir, producer_dir


def _bout_row(
    *,
    trial_key: str = "t1",
    bout_index: int,
    raw_syllable_id: int,
    speed: float = 0.2,
    dheading: float = 0.1,
    straightness: float = 0.8,
    area: float = 100.0,
    ambiguous: int = 0,
    iqr_speed: float = 0.02,
) -> dict[str, str]:
    return {
        "stream": "kpms",
        "seed": "042",
        "trial_key": trial_key,
        "bout_index": str(bout_index),
        "raw_syllable_id": str(raw_syllable_id),
        "bout_mean_speed_mps": str(speed),
        "bout_mean_abs_dheading": str(dheading),
        "bout_straightness": str(straightness),
        "bout_mean_blob_area_px2": str(area),
        "ambiguous": str(ambiguous),
        "bout_iqr_speed_mps": str(iqr_speed),
    }


def test_enrich_candidates_pools_bout_scalars() -> None:
    cand = MinedSequence(
        pattern=(3, 7),
        count=2,
        n_trials=1,
        example_trial_keys=("t1",),
    )
    rows = [
        _bout_row(bout_index=0, raw_syllable_id=3, speed=0.1),
        _bout_row(bout_index=1, raw_syllable_id=7, speed=0.3),
    ]
    enriched = enrich_candidates_with_bout_scalars([cand], rows, seed="042")[0]
    assert enriched.mean_speed_mps == 0.2
    assert enriched.mean_abs_dheading == 0.1


def test_overlay_flag_ambiguous_bout() -> None:
    cand = MinedSequence(
        pattern=(3,),
        count=2,
        n_trials=1,
        example_trial_keys=("t1",),
        mean_speed_mps=0.2,
    )
    rows = [_bout_row(bout_index=0, raw_syllable_id=3, ambiguous=1)]
    assert compute_must_review_overlay(cand, rows, seed="042") is True


def test_overlay_flag_speed_gray_zone() -> None:
    cand = MinedSequence(
        pattern=(3,),
        count=2,
        n_trials=1,
        example_trial_keys=("t1",),
        mean_speed_mps=0.1,
        mean_abs_dheading=0.05,
    )
    assert compute_must_review_overlay(cand, [], seed="042") is True


def test_flag_candidates_sets_must_review_overlay() -> None:
    cand = MinedSequence(
        pattern=(3,),
        count=2,
        n_trials=1,
        example_trial_keys=("t1",),
        mean_speed_mps=0.1,
    )
    flagged = flag_candidates_for_overlay_review([cand], [], seed="042")[0]
    assert flagged.must_review_overlay is True


def test_validate_curated_rows_rejects_unreviewed_overlay(tmp_path) -> None:
    path = tmp_path / "c.csv"
    write_candidate_sequences_csv(
        path,
        [
            MinedSequence(
                pattern=(3, 7),
                count=5,
                n_trials=2,
                example_trial_keys=("t1",),
                must_review_overlay=True,
                behavior_name="groom",
                anchor_bucket="ignore",
            )
        ],
    )
    rows = [{"pattern_json": "[3, 7]", "behavior_name": "groom", "anchor_bucket": "ignore", "must_review_overlay": "1"}]
    try:
        validate_curated_candidate_rows(rows)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "reviewed_at" in str(exc)


def test_validate_curated_rows_rejects_bucket_conflict() -> None:
    rows = [
        {"behavior_name": "groom", "anchor_bucket": "ignore", "must_review_overlay": "0"},
        {"behavior_name": "groom", "anchor_bucket": "moving", "must_review_overlay": "0"},
    ]
    try:
        validate_curated_candidate_rows(rows)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "conflicting anchor_bucket" in str(exc)


def test_rules_from_curated_candidates_includes_buckets(tmp_path) -> None:
    path = tmp_path / "c.csv"
    header = ",".join(CANDIDATE_SEQUENCE_FIELDS)
    path.write_text(
        f"{header}\n"
        '"[3, 7]",2,5,2,t1,,,,,0,groom,ignore,2026-06-30T00:00:00+00:00,t1,\n'
        '"[12]",1,10,3,t2,,,,,0,pause,still,2026-06-30T00:00:00+00:00,t2,\n',
        encoding="utf-8",
    )
    doc = rules_from_curated_candidates(path, fit_id="seed_042")
    assert doc.behavior_anchor_buckets == {"groom": "ignore", "pause": "still"}
    assert len(doc.rules) == 2


def test_grammar_rules_json_round_trip_buckets(tmp_path) -> None:
    doc = GrammarRules(
        fit_id="seed_042",
        rules=(GrammarRule(pattern=(3, 7), behavior_name="groom", priority=20),),
        behavior_anchor_buckets={"groom": "ignore"},
    )
    path = tmp_path / "rules.json"
    write_grammar_rules_json(path, doc)
    loaded = read_grammar_rules_json(path)
    assert loaded.behavior_anchor_buckets == {"groom": "ignore"}


def test_evaluate_uses_provenance_anchor_buckets(tmp_path) -> None:
    anchor_art = anchor_dir(tmp_path, "is_moving", "cal")
    producer_art = producer_dir(tmp_path, "syllable_grammar", "seed_a")
    write_is_moving_anchor(
        anchor_art,
        IsMovingAnchor(
            calibration_id="cal",
            fps=10.0,
            trials=(
                TrialAnchorFrames(
                    trial_key="t1",
                    source_frame_index=np.array([0, 1, 2], dtype=np.int64),
                    is_moving=np.array([True, True, False]),
                ),
            ),
            params={},
        ),
    )
    write_behavior_labeling(
        producer_art,
        BehaviorLabeling(
            producer="syllable_grammar",
            fit_id="seed_a",
            fps=10.0,
            trials=(
                TrialFrameLabels(
                    trial_key="t1",
                    source_frame_index=np.array([0, 1, 2], dtype=np.int64),
                    behavior_id=np.array([0, 0, 1], dtype=np.int32),
                ),
            ),
            behavior_names={0: "groom", 1: "pause"},
            behavior_anchor_buckets={0: "ignore", 1: "still"},
        ),
    )
    report = evaluate_behavior_producer(producer_art, anchor_art)
    assert report.n_trials == 1
    # groom frames ignored; only pause frame scored against anchor
    assert report.mean_anchor_agreement == 1.0
    assert report.mean_producer_moving_fraction == 0.0
