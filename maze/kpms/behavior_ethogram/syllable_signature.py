"""Syllable kinematic signature embedding (ADR-0005: never raw syllable id)."""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from .bout_feature_contract import SYLLABLE_SIGNATURE_FEATURE_NAMES
from .bout_scalars import BoutScalarFeatures

SYLLABLE_SIGNATURE_NAMES = SYLLABLE_SIGNATURE_FEATURE_NAMES


def build_syllable_kinematic_signatures(
    rows: Sequence[BoutScalarFeatures],
) -> dict[int, np.ndarray]:
    """Pool bout scalars by ``raw_syllable_id`` into a fixed 3-D kinematic signature."""
    by_id: dict[int, list[BoutScalarFeatures]] = {}
    for row in rows:
        by_id.setdefault(int(row.raw_syllable_id), []).append(row)
    out: dict[int, np.ndarray] = {}
    for sid, group in by_id.items():
        speeds = [r.bout_mean_speed_mps for r in group]
        dheads = [r.bout_mean_abs_dheading for r in group]
        areas = [r.bout_mean_blob_area_px2 for r in group]
        out[sid] = np.array(
            [
                float(np.nanmean(speeds)),
                float(np.nanmean(dheads)),
                float(np.nanmean(areas)),
            ],
            dtype=np.float64,
        )
    return out


def syllable_signature_row(
    feat: BoutScalarFeatures,
    signatures: Mapping[int, np.ndarray],
) -> np.ndarray:
    sig = signatures.get(int(feat.raw_syllable_id))
    if sig is None:
        return np.zeros(len(SYLLABLE_SIGNATURE_NAMES), dtype=np.float64)
    return np.asarray(sig, dtype=np.float64)


def max_scalar_correlation_with_signature(
    mat: np.ndarray,
    feature_names: Sequence[str],
) -> float:
    """Max |Pearson r| between any syllable_sig_* column and any other feature."""
    names = list(feature_names)
    sig_idx = [i for i, n in enumerate(names) if n.startswith("syllable_sig_")]
    other_idx = [i for i, n in enumerate(names) if not n.startswith("syllable_sig_")]
    if not sig_idx or not other_idx:
        return 0.0
    max_r = 0.0
    for si in sig_idx:
        for oi in other_idx:
            a = mat[:, si]
            b = mat[:, oi]
            if np.std(a) < 1e-12 or np.std(b) < 1e-12:
                continue
            r = float(np.corrcoef(a, b)[0, 1])
            max_r = max(max_r, abs(r))
    return max_r
