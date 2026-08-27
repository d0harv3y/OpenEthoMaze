"""Litmus for syllable signature pooling."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
    _highlight_cluster,
    build_cluster_color_lookup,
    pca_ordination,
)
from nor_object_mi.simpler_first_syllable_signatures import (  # noqa: E402
    CLUSTER_POOL_COLS,
    accumulate_chunk_sums,
    pool_syllable_prototypes,
    prototypes_from_accumulators,
)


def _toy_bouts() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "model": ["mA", "mA", "mA", "mB"],
            "ss": [50, 50, 50, 50],
            "raw_syllable_id": [1, 1, 2, 1],
            "bout_mean_speed_mps": [1.0, 3.0, 5.0, 2.0],
            "bout_mean_abs_dheading": [0.1, 0.3, 0.5, 0.2],
            "bout_mean_nose_tail_m": [0.05, 0.07, 0.09, 0.06],
            "bout_iqr_speed_mps": [0.0, 0.0, 0.0, 0.0],
            "bout_iqr_abs_dheading": [0.0, 0.0, 0.0, 0.0],
            "bout_iqr_nose_tail_m": [0.0, 0.0, 0.0, 0.0],
            "bout_duration_s": [1.0, 1.0, 2.0, 1.0],
            "bout_net_dheading_rad": [0.0, 0.0, 0.0, 0.0],
            "bout_straightness": [1.0, 1.0, 0.5, 1.0],
        }
    )


def test_highlight_prefers_full_alphabet_usage() -> None:
    s = pd.DataFrame(
        {
            "cluster_id": [13, 49],
            "n_models": [21, 14],
            "median_n_bouts": [27000.0, 37000.0],
        }
    )
    assert _highlight_cluster(s) == 13


def test_pool_mean_speed() -> None:
    proto = pool_syllable_prototypes(_toy_bouts())
    a1 = proto[(proto["model"] == "mA") & (proto["raw_syllable_id"] == 1)].iloc[0]
    assert a1["n_bouts"] == 2
    assert abs(float(a1["syllable_sig_mean_speed_mps"]) - 2.0) < 1e-9


def test_chunk_accumulator_matches_pool() -> None:
    df = _toy_bouts()
    sums: dict = {}
    counts: dict = {}
    n_bouts: dict = {}
    accumulate_chunk_sums(df.iloc[:2], sums, counts, n_bouts, CLUSTER_POOL_COLS)
    accumulate_chunk_sums(df.iloc[2:], sums, counts, n_bouts, CLUSTER_POOL_COLS)
    online = prototypes_from_accumulators(sums, counts, n_bouts, CLUSTER_POOL_COLS)
    batched = pool_syllable_prototypes(df)
    merged = online.merge(
        batched,
        on=["model", "ss", "raw_syllable_id"],
        suffixes=("_on", "_bat"),
    )
    np.testing.assert_allclose(
        merged["syllable_sig_mean_speed_mps_on"],
        merged["syllable_sig_mean_speed_mps_bat"],
        rtol=1e-9,
    )
    np.testing.assert_array_equal(merged["n_bouts_on"], merged["n_bouts_bat"])


def test_pca_ordination_variance_sums_to_one() -> None:
    rng = np.random.default_rng(0)
    z = rng.normal(size=(40, 9))
    scores, loadings, var = pca_ordination(z)
    assert scores.shape == (40, 9)
    assert loadings.shape == (9, 9)
    np.testing.assert_allclose(float(np.sum(var)), 1.0, rtol=1e-9)
    recon = scores @ loadings.T
    centered = z - np.mean(z, axis=0, keepdims=True)
    np.testing.assert_allclose(recon, centered, rtol=1e-9, atol=1e-9)


def test_cluster_colormap_unique_per_id() -> None:
    summary = pd.DataFrame({"cluster_id": [0, 1, 13, 49]})
    lookup, cluster_ids, _listed = build_cluster_color_lookup(summary)
    assert cluster_ids == [0, 1, 13, 49]
    colors = [lookup[cid] for cid in cluster_ids]
    assert len(set(colors)) == 4
    assert lookup[-1] != lookup[13]
