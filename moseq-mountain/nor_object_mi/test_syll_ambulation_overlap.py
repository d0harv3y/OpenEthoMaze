"""Litmus for syllable ∩ locomotor overlap."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.syll_ambulation_overlap import (
    annotate_syllable_bouts,
    bout_occupancy_on_raster,
    cramers_v_kx2,
    frames_in_spans,
    locomotor_raster,
    mutual_info_bits,
    occupancy_by_syllable,
    overlap_frames,
    session_association,
)


def test_overlap_exclusive_end() -> None:
    assert overlap_frames(0, 10, 10, 20) == 0
    assert overlap_frames(0, 10, 5, 12) == 5
    assert overlap_frames(0, 10, 0, 10) == 10


def test_frames_in_spans_sorted() -> None:
    spans = [(0, 10), (20, 30)]
    assert frames_in_spans(8, 22, spans) == 2 + 2


def test_mi_independent_is_zero() -> None:
    # two syllables, same move/still mix
    move = np.array([10.0, 10.0])
    still = np.array([10.0, 10.0])
    assert abs(mutual_info_bits(move, still)) < 1e-12
    assert abs(cramers_v_kx2(move, still)) < 1e-12


def test_mi_deterministic_is_one_bit() -> None:
    move = np.array([10.0, 0.0])
    still = np.array([0.0, 10.0])
    np.testing.assert_allclose(mutual_info_bits(move, still), 1.0, atol=1e-12)
    np.testing.assert_allclose(cramers_v_kx2(move, still), 1.0, atol=1e-12)


def test_session_frame_weighted_matches_p_move() -> None:
    syll = pd.DataFrame(
        {
            "raw_syllable_id": [0, 1],
            "row_start": [0, 10],
            "row_end_exclusive": [10, 20],
            "bout_duration_s": [1.0, 1.0],
        }
    )
    move = pd.DataFrame({"row_start": [0], "row_end_exclusive": [10]})
    still = pd.DataFrame({"row_start": [10], "row_end_exclusive": [20]})
    ann = annotate_syllable_bouts(syll, move, still)
    rec = session_association(ann)
    assert rec["p_session_move"] == 0.5
    assert rec["n_majority_move"] == 1
    assert rec["n_majority_still"] == 1
    np.testing.assert_allclose(rec["i_syllable_locomotor_bits"], 1.0)
    np.testing.assert_allclose(rec["mean_bout_move_frac"], 0.5)
    np.testing.assert_allclose(rec["enrich_unweighted_move"], 0.0)


def test_unequal_bout_length_unweighted_enrich() -> None:
    """Frame-weighted P(move)=2/3; unweighted bout mean is 0.5 → enrich ≠ 0."""
    syll = pd.DataFrame(
        {
            "raw_syllable_id": [0, 1],
            "row_start": [0, 20],
            "row_end_exclusive": [20, 30],
            "bout_duration_s": [2.0, 1.0],
        }
    )
    move = pd.DataFrame({"row_start": [0], "row_end_exclusive": [20]})
    still = pd.DataFrame({"row_start": [20], "row_end_exclusive": [30]})
    rec = session_association(annotate_syllable_bouts(syll, move, still))
    np.testing.assert_allclose(rec["p_session_move"], 20 / 30)
    np.testing.assert_allclose(rec["mean_bout_move_frac"], 0.5)
    np.testing.assert_allclose(rec["enrich_unweighted_move"], 0.5 - 20 / 30)


def test_occupancy_deterministic_syllables() -> None:
    syll = pd.DataFrame(
        {
            "raw_syllable_id": [0, 1],
            "row_start": [0, 10],
            "row_end_exclusive": [10, 20],
            "bout_duration_s": [1.0, 1.0],
        }
    )
    move = pd.DataFrame({"row_start": [0], "row_end_exclusive": [10]})
    still = pd.DataFrame({"row_start": [10], "row_end_exclusive": [20]})
    occ = occupancy_by_syllable(annotate_syllable_bouts(syll, move, still))
    z = occ.set_index("raw_syllable_id")
    np.testing.assert_allclose(z.loc[0, "p_move_given_syll"], 1.0)
    np.testing.assert_allclose(z.loc[1, "p_move_given_syll"], 0.0)
    np.testing.assert_allclose(z.loc[0, "p_session_move"], 0.5)
    np.testing.assert_allclose(z.loc[0, "enrich_move"], 0.5)
    np.testing.assert_allclose(z.loc[1, "enrich_move"], -0.5)


def test_raster_occupancy_matches_interval_join() -> None:
    syll = pd.DataFrame(
        {
            "raw_syllable_id": [0, 1],
            "row_start": [0, 10],
            "row_end_exclusive": [10, 20],
            "bout_duration_s": [1.0, 1.0],
        }
    )
    move = pd.DataFrame({"row_start": [0], "row_end_exclusive": [10]})
    still = pd.DataFrame({"row_start": [10], "row_end_exclusive": [20]})
    ann = annotate_syllable_bouts(syll, move, still)
    raster = locomotor_raster(move, still, n_frames=20)
    n_move, n_still = bout_occupancy_on_raster(
        syll["row_start"].to_numpy(),
        syll["row_end_exclusive"].to_numpy(),
        raster,
    )
    np.testing.assert_array_equal(n_move, ann["overlap_move_frames"].to_numpy())
    np.testing.assert_array_equal(n_still, ann["overlap_still_frames"].to_numpy())
