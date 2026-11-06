"""Residual-A litmus helpers — OLS residualization + family constants.

Family Residual-A (locked 2026-10-05): residualize syllable scalars on Layer A
covariates, then Kruskal residual by condition within sex (6 BH cells).
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

FAMILY_SESSION = "NOR_TX"
FAMILY_TRIAL = "nvl_obj"
FAMILY_SEXES: tuple[str, ...] = ("F", "M")
GRAIN = "animal × NOR_TX × nvl_obj"

RAW_Y_METRICS: tuple[str, ...] = (
    "shannon_bits",
    "H_next_given_curr",
    "pair_MI",
)
RESID_METRICS: tuple[str, ...] = (
    "resid_shannon_bits",
    "resid_H_next_given_curr",
    "resid_pair_MI",
)
X_COVARIATES: tuple[str, ...] = (
    "mean_speed_mps",
    "frac_still",
    "frac_near_nvl",
)
FAMILY_A_SIZE = len(RESID_METRICS) * len(FAMILY_SEXES)  # 6

_Y_TO_RESID = dict(zip(RAW_Y_METRICS, RESID_METRICS, strict=True))


def assert_family_a_size(n_finite: int) -> None:
    if int(n_finite) != FAMILY_A_SIZE:
        raise AssertionError(
            f"Residual-A expects {FAMILY_A_SIZE} finite-p cells, got {n_finite}"
        )


def ols_residuals(
    y: np.ndarray,
    X: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """OLS residuals with intercept. ``X`` is (n, p) covariates without intercept."""
    y = np.asarray(y, dtype=np.float64).ravel()
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2:
        raise ValueError("X must be 2-d")
    if y.shape[0] != X.shape[0]:
        raise ValueError("y/X length mismatch")
    if y.shape[0] < X.shape[1] + 1:
        raise ValueError("need n >= p+1 for OLS with intercept")
    A = np.column_stack([np.ones(y.shape[0]), X])
    beta, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    return resid, beta


def residualize_within_sex(
    df: pd.DataFrame,
    *,
    y_cols: Sequence[str] = RAW_Y_METRICS,
    x_cols: Sequence[str] = X_COVARIATES,
    sex_col: str = "sex",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add ``resid_*`` columns via OLS within sex. Returns (animals, coef table)."""
    out = df.copy()
    for y in y_cols:
        resid_name = _Y_TO_RESID[str(y)]
        out[resid_name] = np.nan
    coef_rows: list[dict[str, object]] = []
    for sex in FAMILY_SEXES:
        mask = out[sex_col].astype(str) == sex
        sub = out.loc[mask]
        if sub.empty:
            continue
        X = sub.loc[:, list(x_cols)].to_numpy(dtype=np.float64)
        for y in y_cols:
            yv = sub[y].to_numpy(dtype=np.float64)
            resid, beta = ols_residuals(yv, X)
            resid_name = _Y_TO_RESID[str(y)]
            out.loc[mask, resid_name] = resid
            row: dict[str, object] = {
                "sex": sex,
                "y": str(y),
                "resid": resid_name,
                "n": int(mask.sum()),
                "intercept": float(beta[0]),
            }
            for j, xc in enumerate(x_cols):
                row[f"beta_{xc}"] = float(beta[j + 1])
            coef_rows.append(row)
    return out, pd.DataFrame(coef_rows)
