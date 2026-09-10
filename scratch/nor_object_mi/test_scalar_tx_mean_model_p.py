"""Litmus for scalar mean-model Kruskal aggregation."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.scalar_tx_mean_model_p import (  # noqa: E402
    aggregate_scalar_da,
    kruskal_per_model_scalar_da,
)


def test_scalar_da_grid_shape() -> None:
    rows = []
    for model in ("m1", "m2"):
        for phase in ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr"):
            for step in ("no_obj->id_obj", "id_obj->nvl_obj", "no_obj->nvl_obj"):
                for sex in ("F", "M"):
                    for condition, bump in (("noSD", 0.0), ("GHSD", 0.2), ("RBSD", 0.25)):
                        for animal in (1, 2, 3):
                            rows.append(
                                {
                                    "model": model,
                                    "animal_id": animal,
                                    "sex": sex,
                                    "condition": condition,
                                    "session": phase,
                                    "step": step,
                                    "delta_frac_near": bump + 0.01 * animal,
                                    "delta_mean_dist_any_m": -bump,
                                    "delta_richness": bump,
                                    "delta_shannon_bits": bump * 0.5,
                                }
                            )
    per = kruskal_per_model_scalar_da(pd.DataFrame(rows))
    # 2 models × 4 metrics × 4 phases × 3 steps × 2 sexes
    assert len(per) == 2 * 4 * 4 * 3 * 2
    agg = aggregate_scalar_da(per, star="majority")
    assert len(agg) == 4 * 4 * 3 * 2
    assert "hit_fdr05" in agg.columns
