"""Litmus for protocol prologue mean/interval helpers."""

from __future__ import annotations

import numpy as np

from nor_object_mi.simpler_first_protocol_prologue import pearson_pair, ttest_one_sample


def test_pearson_identity() -> None:
    x = np.array([0.1, 0.2, -0.3, 0.4, 0.0])
    rec = pearson_pair(x, x)
    assert rec["n"] == 5
    assert abs(rec["pearson_r"] - 1.0) < 1e-12
    assert rec["p"] < 0.05


def test_ttest_anti_identity_near_zero() -> None:
    """Symmetric noise around 0 should not hit at α=0.05 (high p)."""
    rng = np.random.default_rng(0)
    d = rng.normal(0.0, 1.0, size=40)
    d = d - d.mean()
    rec = ttest_one_sample(d)
    assert rec["n"] == 40
    assert abs(float(rec["mean_delta"])) < 1e-12
    assert float(rec["p"]) > 0.99


def test_ttest_known_shift() -> None:
    d = np.linspace(0.4, 0.6, 30)
    rec = ttest_one_sample(d)
    assert float(rec["p"]) < 1e-4
    assert abs(float(rec["mean_delta"]) - 0.5) < 1e-12
