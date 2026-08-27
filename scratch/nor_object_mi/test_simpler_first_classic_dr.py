"""Litmus for classic investigation DR vs object-prox occupancy DR."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.simpler_first_classic_dr import (
    spearman_pair,
    wide_novel_investigation,
)
from nor_object_mi.simpler_first_object_prox import discrimination_ratio


def test_spearman_identity() -> None:
    x = np.array([0.1, 0.2, -0.3, 0.4, 0.0])
    rec = spearman_pair(x, x)
    assert rec["n"] == 5
    assert abs(rec["spearman_rho"] - 1.0) < 1e-12
    assert rec["p"] < 0.05


def test_wide_reconstructs_stored_dr() -> None:
    rows = []
    for obj, t in (("fam", 2.0), ("nvl", 8.0)):
        rows.append(
            {
                "ID": 1,
                "sex": "F",
                "treatment group": "noSD",
                "phase layer": "NOR_TX",
                "condition layer": "novel_obj",
                "duration_s": 180,
                "object_id": obj,
                "metric": "total_investigation_time_s",
                "value": t,
            }
        )
    rows.append(
        {
            "ID": 1,
            "sex": "F",
            "treatment group": "noSD",
            "phase layer": "NOR_TX",
            "condition layer": "novel_obj",
            "duration_s": 180,
            "object_id": np.nan,
            "metric": "discrimination_ratio",
            "value": discrimination_ratio(8.0, 2.0),
        }
    )
    wide = wide_novel_investigation(pd.DataFrame(rows))
    assert len(wide) == 1
    assert abs(float(wide["dr_classic"].iloc[0]) - 0.6) < 1e-12
    assert abs(float(wide["dr_recomputed"].iloc[0]) - 0.6) < 1e-12
