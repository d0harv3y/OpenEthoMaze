"""Unit tests for n-gram table helpers (no H5)."""

from __future__ import annotations

from nor_object_mi.ngram_table import (
    assign_top_m_other,
    ngram_rows_from_bout_rows,
    pattern_json,
)


def _bout(i: int, sid: int, frames: int, dist: float) -> dict:
    return {
        "kpms_key": "k",
        "trial_key": "a/t",
        "animal_id": "a",
        "raw_session": "s",
        "phase_layer": "NOR_TX",
        "condition_layer": "novel_obj",
        "tx": "noSD",
        "sex": "F",
        "cohort": "exp1",
        "bout_index": i,
        "raw_syllable_id": sid,
        "row_start": i * 10,
        "row_end_exclusive": i * 10 + frames,
        "bout_frames": frames,
        "bout_mean_dist_fam_m": dist,
        "bout_mean_dist_nvl_m": dist + 1,
        "bout_mean_dist_obj_a_m": dist,
        "bout_mean_dist_obj_b_m": dist + 1,
        "bout_mean_dist_locus_a_m": dist,
        "bout_mean_dist_locus_b_m": dist + 1,
        "bout_mean_dist_any_m": dist,
        "obj_a_id": "object_0",
        "obj_b_id": "object_1",
        "dist_any_source": "real_objects",
        "locus_label_policy": "hist",
        "role_at_locus_a": "",
        "role_at_locus_b": "",
        "nvl_nearest_hist_locus": "a",
    }


def test_span_mean_is_frame_weighted() -> None:
    bouts = [_bout(0, 1, 1, 0.0), _bout(1, 2, 3, 10.0)]
    rows = ngram_rows_from_bout_rows(bouts, pattern_len=2)
    assert len(rows) == 1
    # (0*1 + 10*3) / 4 = 7.5
    assert abs(float(rows[0]["bout_mean_dist_fam_m"]) - 7.5) < 1e-9
    assert int(rows[0]["span_frames"]) == 4
    assert rows[0]["pattern_json"] == pattern_json([1, 2])


def test_max_span_filter() -> None:
    bouts = [_bout(0, 1, 5, 0.0), _bout(1, 2, 5, 0.0)]
    rows = ngram_rows_from_bout_rows(bouts, pattern_len=2, max_span_frames=9)
    assert rows == []
    rows2 = ngram_rows_from_bout_rows(bouts, pattern_len=2, max_span_frames=10)
    assert len(rows2) == 1


def test_top_m_other() -> None:
    rows = [
        {"pattern_json": "[0,1]", "x": 1},
        {"pattern_json": "[0,1]", "x": 2},
        {"pattern_json": "[2,3]", "x": 3},
        {"pattern_json": "[9,9]", "x": 4},
    ]
    out, meta = assign_top_m_other(rows, top_m=1)
    assert meta["n_patterns_kept"] == 1
    assert sum(1 for r in out if int(r["pattern_id"]) == -1) == 2
    assert sum(1 for r in out if int(r["pattern_id"]) == 0) == 2
