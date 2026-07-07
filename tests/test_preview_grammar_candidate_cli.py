"""Tests for maze-preview-grammar-candidate match index selection."""

from __future__ import annotations

import random

import pytest

from maze.cli.preview_grammar_candidate import resolve_match_indices


def test_resolve_match_indices_default() -> None:
    rng = random.Random(0)
    assert resolve_match_indices(
        match_index=None, random_matches=None, n_available=5, rng=rng
    ) == [0]


def test_resolve_match_indices_comma_list() -> None:
    rng = random.Random(0)
    assert resolve_match_indices(
        match_index="2,3,4,5,6,7",
        random_matches=None,
        n_available=10,
        rng=rng,
    ) == [2, 3, 4, 5, 6, 7]


def test_resolve_match_indices_random_n() -> None:
    rng = random.Random(42)
    picked = resolve_match_indices(
        match_index=None,
        random_matches=6,
        n_available=20,
        rng=rng,
    )
    assert len(picked) == 6
    assert len(set(picked)) == 6
    assert all(0 <= i < 20 for i in picked)
    assert picked == sorted(picked)


def test_resolve_match_indices_random_capped_by_available() -> None:
    rng = random.Random(1)
    picked = resolve_match_indices(
        match_index=None,
        random_matches=10,
        n_available=3,
        rng=rng,
    )
    assert picked == [0, 1, 2]


def test_resolve_match_indices_mutually_exclusive() -> None:
    rng = random.Random(0)
    with pytest.raises(ValueError, match="not both"):
        resolve_match_indices(
            match_index="0,1",
            random_matches=2,
            n_available=5,
            rng=rng,
        )
