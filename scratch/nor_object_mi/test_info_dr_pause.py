"""Litmus checks for INFO DR ↔ pause Y helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.info_dr_pause_delta import (  # noqa: E402
    apply_quantile_edges,
    discretize_pair,
    get_y_metric_spec,
    join_dr_pause,
    load_pause_y,
    pair_mi_mm,
    perm_p_value,
    y_metric_choices,
)


def test_y_metric_registry_includes_presence_novel() -> None:
    assert "presence_novel" in y_metric_choices()
    spec = get_y_metric_spec("presence_novel")
    assert spec.binary
    assert spec.y_col == "presence_novel"


def test_pair_mi_independent_near_zero() -> None:
    rng = np.random.default_rng(0)
    x = rng.integers(0, 3, size=200)
    y = rng.integers(0, 3, size=200)
    mi_raw, mi_mm, _, _, n = pair_mi_mm(x, y)
    assert n == 200
    assert mi_raw < 0.15
    assert mi_mm < 0.20


def test_discretize_binary_y_keeps_labels() -> None:
    dr = np.linspace(-0.8, 0.8, 11)
    pres = np.array([0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0], dtype=float)
    xb, yb, nb = discretize_pair(dr, pres, n_bins=3, y_binary=True)
    assert xb.size == 11
    assert nb >= 2
    assert set(yb.tolist()) <= {0, 1}


def test_presence_novel_from_p_right(tmp_path: Path) -> None:
    da = tmp_path / "da"
    da.mkdir()
    pd.DataFrame({"model": ["m1"], "raw_syllable_id": [7]}).to_csv(
        da / "duration_band_vs_da.csv", index=False
    )
    pd.DataFrame(
        {
            "model": ["m1", "m1"],
            "animal_id": ["a1", "a2"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "step": ["identical->novel", "identical->novel"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "raw_syllable_id": [7, 7],
            "delta_p": [0.1, 0.0],
            "p_left": [0.0, 0.01],
            "p_right": [0.02, 0.0],
        }
    ).to_csv(da / "da_syllable_deltas_per_animal.csv", index=False)
    spec = get_y_metric_spec("presence_novel")
    out = load_pause_y(da, spec)
    assert len(out) == 2
    by_id = out.set_index("animal_id")[spec.y_col].to_dict()
    assert by_id["a1"] == 1.0
    assert by_id["a2"] == 0.0


def test_join_inner_on_animal_phase() -> None:
    spec = get_y_metric_spec("delta_p_novelty")
    dr = pd.DataFrame(
        {
            "animal_id": ["a1", "a2"],
            "sex": ["F", "M"],
            "tx": ["noSD", "GHSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "dr_exclusive": [0.2, -0.1],
            "n_models": [21, 21],
        }
    )
    pause = pd.DataFrame(
        {
            "animal_id": ["a1", "a3"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "step": ["identical->novel", "identical->novel"],
            spec.y_col: [0.05, 0.01],
            "n_models": [21, 21],
            "iqr_across_models": [0.01, 0.02],
        }
    )
    out = join_dr_pause(dr, pause, y_col=spec.y_col)
    assert len(out) == 1
    assert out.iloc[0]["animal_id"] == "a1"


def test_apply_quantile_edges_covers_range() -> None:
    v = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    edges = np.array([-np.inf, 1.5, 3.5, np.inf])
    b = apply_quantile_edges(v, edges)
    assert list(b.astype(int)) == [0, 0, 1, 1, 2]
