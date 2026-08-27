"""Litmus / metamorphic checks for Q2 composition scalars and PERMANOVA."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.simpler_first_q2 import (
    compositions_from_bouts,
    permanova_braycurtis,
    shannon_bits,
)


def test_shannon_identity_and_uniform() -> None:
    assert shannon_bits(np.array([1.0])) == 0.0
    h = shannon_bits(np.array([0.25, 0.25, 0.25, 0.25]))
    assert abs(h - 2.0) < 1e-12


def test_composition_ignores_other_conditions() -> None:
    rows = []
    for sid, frames in ((1, 10), (2, 10)):
        rows.append(
            {
                "animal_id": "a",
                "sex": "F",
                "tx": "noSD",
                "phase_layer": "NOR_TX",
                "condition_layer": "novel_obj",
                "raw_syllable_id": sid,
                "bout_frames": frames,
            }
        )
    rows.append(
        {
            "animal_id": "a",
            "sex": "F",
            "tx": "noSD",
            "phase_layer": "NOR_TX",
            "condition_layer": "identical_obj",
            "raw_syllable_id": 99,
            "bout_frames": 1000,
        }
    )
    meta, P, syll = compositions_from_bouts(pd.DataFrame(rows))
    assert list(syll) == [1, 2]
    assert abs(float(meta.loc[0, "shannon_bits"]) - 1.0) < 1e-12
    assert int(meta.loc[0, "richness"]) == 2
    assert P.shape == (1, 2)


def test_permanova_separates_two_blocks() -> None:
    # Two disjoint compositions, three animals each
    P = np.array(
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 1.0],
            [0.0, 1.0],
        ]
    )
    groups = np.array(["noSD", "noSD", "noSD", "GHSD", "GHSD", "GHSD"])
    rec = permanova_braycurtis(P, groups, n_perm=99, seed=0)
    assert rec["p"] < 0.05
    # shuffle labels: same P, identical groups → F is nan or p high if all one group skipped
    rec2 = permanova_braycurtis(P, np.array(["noSD"] * 6), n_perm=19, seed=0)
    assert rec2["F"] != rec2["F"]  # NaN: only one group
