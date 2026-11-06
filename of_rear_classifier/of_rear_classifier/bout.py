"""Post-class bout smooth (Sturman ``avgbool``) and simple counts."""

from __future__ import annotations

import numpy as np

DEFAULT_AVGBOOL_WINDOW = 10


def avgbool(mask: np.ndarray, window: int = DEFAULT_AVGBOOL_WINDOW) -> np.ndarray:
    """Majority over ±window frames (Sturman ``avgbool``)."""
    x = np.asarray(mask, dtype=np.float64).reshape(-1)
    w = int(window)
    out = np.zeros(x.shape[0], dtype=bool)
    for i in range(x.shape[0]):
        lo = max(0, i - w)
        hi = min(x.shape[0], i + w + 1)
        out[i] = np.nanmean(x[lo:hi]) > 0.5
    return out


def bout_count(mask: np.ndarray) -> int:
    """Count 0→1 onsets on a boolean stream."""
    m = np.asarray(mask, dtype=bool).reshape(-1)
    if m.size == 0:
        return 0
    prev = np.concatenate([[False], m[:-1]])
    return int(np.sum(m & ~prev))


def bout_time_s(mask: np.ndarray, fps: float) -> float:
    return float(np.sum(np.asarray(mask, dtype=bool))) / float(fps)
