"""Litmus for BL→TX occupancy session Δ pairing."""

from __future__ import annotations

import pandas as pd

from nor_object_mi.simpler_first_occupancy_session_delta import (
    FAMILY_A_SIZE,
    paired_occupancy_delta,
)


def test_family_a_size_is_four() -> None:
    assert FAMILY_A_SIZE == 4


def test_paired_delta_identity() -> None:
    """Worked example: TX − BL on known fractions."""
    rows = []
    for sess, nvl, fam in (("NOR_BL", 0.10, 0.20), ("NOR_TX", 0.25, 0.15)):
        rows.append(
            {
                "animal_id": "a1",
                "sex": "M",
                "condition": "noSD",
                "session": sess,
                "frac_near_nvl": nvl,
                "frac_near_fam": fam,
                "n_models": 21,
            }
        )
    # second animal for merge shape
    for sess, nvl, fam in (("NOR_BL", 0.0, 0.0), ("NOR_TX", 0.0, 0.0)):
        rows.append(
            {
                "animal_id": "a2",
                "sex": "F",
                "condition": "GHSD",
                "session": sess,
                "frac_near_nvl": nvl,
                "frac_near_fam": fam,
                "n_models": 21,
            }
        )
    d = paired_occupancy_delta(pd.DataFrame(rows))
    a1 = d.loc[d["animal_id"] == "a1"].iloc[0]
    assert abs(float(a1["delta_frac_near_nvl"]) - 0.15) < 1e-12
    assert abs(float(a1["delta_frac_near_fam"]) - (-0.05)) < 1e-12
    assert a1["session_step"] == "BL->TX"
