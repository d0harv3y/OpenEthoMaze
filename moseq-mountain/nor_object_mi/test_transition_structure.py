"""Litmus tests for transition_structure math (toy P, no data peeking)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.transition_structure import (  # noqa: E402
    FAMILY_B_SIZE,
    TRANSSTRUCT_B_GRAINS,
    conditional_entropy_next_given_current,
    count_transitions,
    pooled_reference_P,
    row_stochastic_with_laplace,
    total_variation,
    transition_matrix,
)


def test_identity_zero_distance() -> None:
    P = np.array([[0.7, 0.3], [0.2, 0.8]])
    assert total_variation(P, P) == 0.0


def test_anti_identity_max_distance() -> None:
    P = np.array([[1.0, 0.0], [0.0, 1.0]])
    Q = np.array([[0.0, 1.0], [1.0, 0.0]])
    assert total_variation(P, Q) == 2.0


def test_laplace_rows_sum_to_one() -> None:
    C = np.array([[5.0, 0.0], [0.0, 0.0]])
    P = row_stochastic_with_laplace(C, alpha=1.0)
    assert np.allclose(P.sum(axis=1), 1.0)
    # Empty row -> uniform
    assert np.allclose(P[1], [0.5, 0.5])


def test_deterministic_chain_zero_entropy() -> None:
    labels = np.array([0, 1, 0, 1, 0, 1])
    P, C = transition_matrix(labels, [0, 1], alpha=1e-9)
    H = conditional_entropy_next_given_current(P, C)
    assert H < 1e-6


def test_uniform_next_max_entropy() -> None:
    # Alternating coverage of all 2x2 edges -> near-uniform rows -> H near 1 bit.
    labels = np.array([0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1])
    P, C = transition_matrix(labels, [0, 1], alpha=1e-9)
    H = conditional_entropy_next_given_current(P, C)
    assert 0.5 < H <= 1.0


def test_count_transitions_shape() -> None:
    C = count_transitions(np.array([2, 0, 2, 1]), [0, 1, 2])
    assert C.shape == (3, 3)
    assert C.sum() == 3.0


def test_transstruct_b_family_size() -> None:
    assert len(TRANSSTRUCT_B_GRAINS) == 6
    assert FAMILY_B_SIZE == 24


def test_transstruct_c_family_size() -> None:
    from nor_object_mi.transition_structure import FAMILY_C_SIZE, TRANSSTRUCT_C_GRAINS

    assert len(TRANSSTRUCT_C_GRAINS) == 12
    assert FAMILY_C_SIZE == 48


def test_pooled_reference_matches_manual() -> None:
    seqs = [np.array([0, 1, 0]), np.array([1, 1, 0])]
    P, C = pooled_reference_P(seqs, [0, 1], alpha=1.0)
    assert np.allclose(P.sum(axis=1), 1.0)
    assert C.sum() == 4.0
