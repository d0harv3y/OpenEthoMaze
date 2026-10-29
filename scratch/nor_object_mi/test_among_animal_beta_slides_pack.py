"""Litmus checks for among-animal β (PERMANOVA) slides pack."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.among_animal_beta_slides_pack import (
    animal_counts_table,
    consensus_across_models,
    mean_within_between_bc,
    permanova_cell,
)
from nor_object_mi.simpler_first_condition_extras import _counts_to_matrix


def test_mean_within_between_identity_and_separation() -> None:
    # Two tight clusters far apart → between >> within
    P = np.array(
        [
            [1.0, 0.0],
            [0.95, 0.05],
            [0.0, 1.0],
            [0.05, 0.95],
        ],
        dtype=np.float64,
    )
    groups = np.array(["noSD", "noSD", "GHSD", "GHSD"])
    w, b = mean_within_between_bc(P, groups)
    assert w < 0.2
    assert b > 0.7


def test_animal_counts_and_permanova_toy() -> None:
    rows = []
    # noSD: mostly syllable 0; GHSD/RBSD: mostly syllable 1 → condition partition
    for aid, sex, tx, syll in (
        ("a", "F", "noSD", 0),
        ("b", "F", "noSD", 0),
        ("c", "F", "GHSD", 1),
        ("d", "F", "GHSD", 1),
        ("e", "F", "RBSD", 1),
        ("f", "F", "RBSD", 1),
    ):
        rows.append(
            {
                "animal_id": aid,
                "sex": sex,
                "condition": tx,
                "session": "NOR_TX",
                "trial": "nvl_obj",
                "raw_syllable_id": syll,
                "bout_frames": 100.0,
            }
        )
        # sprinkle other syll so richness > 1
        rows.append(
            {
                "animal_id": aid,
                "sex": sex,
                "condition": tx,
                "session": "NOR_TX",
                "trial": "nvl_obj",
                "raw_syllable_id": 1 - syll,
                "bout_frames": 5.0,
            }
        )
    bouts = pd.DataFrame(rows)
    ac = animal_counts_table(bouts)
    assert len(ac) == 6
    meta, P, _ = _counts_to_matrix(ac)
    assert P.shape[0] == 6
    rec = permanova_cell(
        ac,
        session="NOR_TX",
        trial="nvl_obj",
        sex="F",
        model="m_toy",
        n_perm=99,
        seed=1,
    )
    assert rec["n"] == 6
    assert np.isfinite(rec["p"])
    assert rec["p"] < 0.05  # strong separation


def test_consensus_shapes() -> None:
    rows = []
    for model in ("m1", "m2"):
        for session in ("NOR_BL", "NOR_TX"):
            for trial in ("no_obj", "id_obj", "nvl_obj"):
                for sex in ("F", "M"):
                    rows.append(
                        {
                            "model": model,
                            "session": session,
                            "trial": trial,
                            "sex": sex,
                            "p": 0.2,
                            "F": 1.0,
                            "delta_bc_between_minus_within": 0.05,
                            "hit_fdr05": False,
                        }
                    )
    cons = consensus_across_models(pd.DataFrame(rows))
    # full SESSIONS × TRIALS × SEX from module constants → 4×3×2 = 24
    assert len(cons) == 24
    assert cons["n_models"].max() <= 2
