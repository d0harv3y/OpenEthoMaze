"""Litmus for session-grain segmenter Pearson (not lagged CCF)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.segmenter_pearson import (
    FEATURES,
    LITMUS_A,
    LITMUS_B,
    block_edges,
    join_session_features,
    pearson_matrix,
    session_bout_summary,
    shannon_bits,
)
from nor_object_mi.simpler_first_protocol_prologue import pearson_pair


def test_shannon_one_class_is_zero() -> None:
    assert shannon_bits(np.array([3, 3, 3, 3])) == 0.0


def test_shannon_two_equal_is_one_bit() -> None:
    np.testing.assert_allclose(shannon_bits(np.array([0, 0, 1, 1])), 1.0)


def test_pearson_identity() -> None:
    x = np.array([0.2, -0.1, 0.4, 0.0, 0.3])
    rec = pearson_pair(x, x)
    assert rec["n"] == 5
    np.testing.assert_allclose(rec["pearson_r"], 1.0, atol=1e-12)


def test_weighted_speed_unequal_bouts() -> None:
    bouts = pd.DataFrame(
        {
            "animal_id": ["a", "a"],
            "raw_session": ["s", "s"],
            "phase_layer": ["NOR_BL", "NOR_BL"],
            "bout_mean_speed_mps": [0.0, 1.0],
            "bout_duration_s": [1.0, 3.0],
            "bout_frames": [10, 30],
        }
    )
    rec = session_bout_summary(
        bouts,
        speed_col="bout_mean_speed_mps",
        duration_col="bout_duration_s",
        frames_col="bout_frames",
    )
    np.testing.assert_allclose(float(rec["speed_mps"].iloc[0]), 0.75)
    assert int(rec["n_bouts"].iloc[0]) == 2


def test_speed_litmus_is_identity_when_speeds_copied() -> None:
    keys = {"animal_id": ["a", "b", "c", "d"], "raw_session": ["s"] * 4, "phase_layer": ["NOR_BL"] * 4}
    speed = np.array([0.05, 0.10, 0.20, 0.08])
    overlap = pd.DataFrame(
        {
            **keys,
            "p_session_move": [0.4, 0.5, 0.6, 0.55],
            "n_syll_bouts": [10, 12, 8, 11],
            "n_syllable_ids": [4, 5, 4, 6],
            "i_syllable_locomotor_bits": [0.2, 0.3, 0.25, 0.22],
            "cramers_v": [0.4, 0.5, 0.45, 0.42],
            "enrich_unweighted_move": [0.05, 0.04, 0.06, 0.03],
            "delta_median_duration_s_move_minus_still": [-0.1, -0.2, -0.15, -0.12],
        }
    )
    syll = pd.DataFrame(
        {
            "animal_id": np.repeat(["a", "b", "c", "d"], 2),
            "raw_session": ["s"] * 8,
            "phase_layer": ["NOR_BL"] * 8,
            "raw_syllable_id": [0, 1] * 4,
            "bout_mean_speed_mps": np.repeat(speed, 2),
            "bout_duration_s": [1.0] * 8,
            "bout_frames": [10] * 8,
        }
    )
    move = syll.drop(columns=["raw_syllable_id"]).copy()
    still = move.copy()
    still["bout_mean_speed_mps"] = 0.01
    sess = join_session_features(overlap, syll, move, still)
    r, _p, n = pearson_matrix(sess)
    ia = FEATURES.index(LITMUS_A)
    ib = FEATURES.index(LITMUS_B)
    np.testing.assert_allclose(r[ia, ib], 1.0, atol=1e-12)
    np.testing.assert_allclose(r[ia, ia], 1.0, atol=1e-12)
    np.testing.assert_allclose(r[ib, ib], 1.0, atol=1e-12)
    assert int(n[ia, ib]) == 4


def test_block_edges_split_four_blocks() -> None:
    edges = block_edges()
    assert edges == [4.5, 8.5, 12.5]
