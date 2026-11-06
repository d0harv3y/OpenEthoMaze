"""Centered ±W temporal stack (Sturman integration_window intent; clean centering)."""

from __future__ import annotations

import numpy as np

from of_rear_classifier.skeleton import N_FEATURES

DEFAULT_INTEGRATION_WINDOW = 15


def stack_centered(
    features: np.ndarray,
    *,
    integration_window: int = DEFAULT_INTEGRATION_WINDOW,
    labels: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Stack frames ``[t-W, t+W]`` into one row; return ``(X, y_aligned)``.

    ``X`` shape ``(T - 2W, 22 * (2W+1))``. Labels (if given) are sliced to the
    center frames ``y[W : T-W]``.
    """
    f = np.asarray(features, dtype=np.float64)
    if f.ndim != 2 or f.shape[1] != N_FEATURES:
        raise ValueError(f"expected (T, {N_FEATURES}), got {f.shape}")
    w = int(integration_window)
    if w < 0:
        raise ValueError("integration_window must be ≥ 0")
    t = f.shape[0]
    if t < 2 * w + 1:
        raise ValueError(f"need T ≥ 2W+1 ({2 * w + 1}), got T={t}")

    n_out = t - 2 * w
    width = N_FEATURES * (2 * w + 1)
    x = np.empty((n_out, width), dtype=np.float64)
    for i, center in enumerate(range(w, t - w)):
        x[i] = f[center - w : center + w + 1].ravel()

    y_out = None
    if labels is not None:
        y = np.asarray(labels)
        if y.shape[0] != t:
            raise ValueError("labels length must match features T")
        y_out = y[w : t - w]
    return x, y_out


def window_feature_dim(integration_window: int = DEFAULT_INTEGRATION_WINDOW) -> int:
    return N_FEATURES * (2 * int(integration_window) + 1)
