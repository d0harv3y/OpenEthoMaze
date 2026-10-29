"""Litmus tests for ngram_structure math (toy streams, no data peeking)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.ngram_structure import (  # noqa: E402
    FAMILY_B_SIZE,
    NGRAMSEQ_B_GRAINS,
    bigram_richness_from_counts,
    pair_mi_from_counts,
    resample_pairs,
)


def test_ngramseq_b_family_size() -> None:
    assert len(NGRAMSEQ_B_GRAINS) == 6
    assert FAMILY_B_SIZE == 24


def test_ngramseq_c_family_size() -> None:
    from nor_object_mi.ngram_structure import FAMILY_C_SIZE, NGRAMSEQ_C_GRAINS

    assert len(NGRAMSEQ_C_GRAINS) == 12
    assert FAMILY_C_SIZE == 48


def test_independent_stream_near_zero_mi() -> None:
    rng = np.random.default_rng(0)
    z = rng.integers(0, 4, size=2000)
    C = resample_pairs(z, [0, 1, 2, 3], 1500, np.random.default_rng(1))
    assert pair_mi_from_counts(C) < 0.05


def test_deterministic_cycle_high_mi() -> None:
    z = np.tile([0, 1, 2, 3], 500)
    C = resample_pairs(z, [0, 1, 2, 3], 1500, np.random.default_rng(1))
    assert pair_mi_from_counts(C) > 1.5


def test_richness_bounds() -> None:
    z = np.tile([0, 1], 100)  # only pairs (0,1),(1,0)
    C = resample_pairs(z, [0, 1], 100, np.random.default_rng(1))
    assert bigram_richness_from_counts(C) == 2
    z2 = np.random.default_rng(2).integers(0, 6, size=500)
    C2 = resample_pairs(z2, list(range(6)), 400, np.random.default_rng(3))
    assert bigram_richness_from_counts(C2) > 20


def test_budget_determinism() -> None:
    z = np.random.default_rng(4).integers(0, 5, size=300)
    C1 = resample_pairs(z, list(range(5)), 200, np.random.default_rng(7))
    C2 = resample_pairs(z, list(range(5)), 200, np.random.default_rng(7))
    assert np.array_equal(C1, C2)
    assert C1.sum() == 200


def test_overbudget_raises() -> None:
    import pytest

    z = np.arange(10)
    with pytest.raises(ValueError):
        resample_pairs(z, list(range(10)), 10, np.random.default_rng(0))
