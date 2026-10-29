"""Litmus tests for residual_litmus OLS (toy cases, no data peeking)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.residual_litmus import (  # noqa: E402
    FAMILY_A_SIZE,
    assert_family_a_size,
    ols_residuals,
    residualize_within_sex,
)


def test_family_a_size() -> None:
    assert FAMILY_A_SIZE == 6
    assert_family_a_size(6)


def test_perfect_fit_residuals_near_zero() -> None:
    rng = np.random.default_rng(0)
    n = 40
    X = rng.normal(size=(n, 3))
    beta_true = np.array([1.5, -0.7, 0.2, 0.9])
    y = beta_true[0] + X @ beta_true[1:]
    resid, beta = ols_residuals(y, X)
    assert np.allclose(resid, 0.0, atol=1e-10)
    assert np.allclose(beta, beta_true, atol=1e-10)


def test_orthogonal_noise_preserved() -> None:
    rng = np.random.default_rng(1)
    n = 80
    X = rng.normal(size=(n, 2))
    noise = rng.normal(size=n)
    # Make noise approximately orthogonal to [1, X] via residualization of noise itself
    noise0, _ = ols_residuals(noise, X)
    y = X[:, 0] + noise0
    resid, _ = ols_residuals(y, X)
    assert np.corrcoef(resid, noise0)[0, 1] > 0.99
    assert abs(np.corrcoef(resid, X[:, 0])[0, 1]) < 0.05


def test_residualize_within_sex_separates() -> None:
    rows = []
    for sex, offset in (("F", 0.0), ("M", 10.0)):
        for i in range(12):
            speed = float(i)
            still = 0.1 * i
            near = 0.05 * i
            rows.append(
                {
                    "sex": sex,
                    "shannon_bits": offset + 2.0 * speed + still + near,
                    "H_next_given_curr": offset + speed,
                    "pair_MI": offset + still,
                    "mean_speed_mps": speed,
                    "frac_still": still,
                    "frac_near_nvl": near,
                }
            )
    df = pd.DataFrame(rows)
    out, coef = residualize_within_sex(df)
    assert np.allclose(out["resid_shannon_bits"], 0.0, atol=1e-8)
    assert set(coef["sex"]) == {"F", "M"}
    assert len(coef) == 6
