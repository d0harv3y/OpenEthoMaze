"""Litmus for INFO sex vs dominant cluster."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.info_sex_cluster import (
    _dominant_from_acc,
    composition_fingerprint_key,
    consensus_dominant_clusters,
    info_sex_cluster_cell,
    info_sex_composition_cell,
    perm_p_sex_cluster,
)
from nor_object_mi.info_dr_pause_delta import pair_mi_mm


def test_dominant_from_acc_tie_break_low_id() -> None:
    assert _dominant_from_acc({3: 10.0, 13: 20.0, 8: 20.0}) == 8


def test_perfect_sex_cluster_association() -> None:
    sex = np.array([0, 0, 0, 1, 1, 1], dtype=np.int64)
    cluster = np.array([10, 10, 10, 20, 20, 20], dtype=np.int64)
    _, mi_mm, h_sex, h_c, _ = pair_mi_mm(sex, cluster)
    assert h_sex <= 1.0 + 1e-9
    assert mi_mm > 0.5
    g = pd.DataFrame(
        {
            "sex": ["F", "F", "F", "M", "M", "M"],
            "dominant_cluster_id": [10, 10, 10, 20, 20, 20],
        }
    )
    rec = info_sex_cluster_cell(g, n_perm=500, rng=np.random.default_rng(0))
    assert rec["mi_mm_bits"] > 0.5
    assert rec["hit_p05"] or rec["perm_p"] < 0.15  # small-n permutation variance


def test_consensus_mode_across_models() -> None:
    per = pd.DataFrame(
        {
            "model": ["m1", "m2", "m3", "m1", "m2", "m3"],
            "animal_id": ["a1"] * 3 + ["a2"] * 3,
            "sex": ["F"] * 3 + ["M"] * 3,
            "condition": ["noSD"] * 6,
            "session": ["ALL_SESSIONS"] * 6,
            "dominant_cluster_id": [13, 13, 8, 8, 8, 8],
            "n_clusters_used": [5] * 6,
            "n_bout_frames": [100.0] * 6,
        }
    )
    cons = consensus_dominant_clusters(per)
    a1 = cons[cons.animal_id == "a1"].iloc[0]
    assert int(a1["dominant_cluster_id"]) == 13
    assert int(a1["n_models_agree_mode"]) == 2


def test_composition_fingerprint_differs_by_mass() -> None:
    a = composition_fingerprint_key({13: 80.0, -1: 20.0})
    b = composition_fingerprint_key({13: 20.0, -1: 80.0})
    assert a != b


def test_info_sex_composition_cell_runs() -> None:
    g = pd.DataFrame(
        {
            "sex": ["F", "F", "F", "M", "M", "M"],
            "composition_key": ["13:4|-1:0", "13:4|-1:0", "13:3|-1:1", "13:1|-1:4", "13:1|-1:4", "13:0|-1:4"],
        }
    )
    rec = info_sex_composition_cell(g, n_perm=100, rng=np.random.default_rng(0))
    assert rec["n_composition_types"] >= 2
    assert np.isfinite(rec["mi_mm_bits"])
