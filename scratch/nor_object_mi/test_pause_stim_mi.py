"""Litmus checks for pause ↔ binned-stim MI bridge."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.pause_stim_mi import (  # noqa: E402
    compute_pause_and_full_mi,
    delta_excess,
    join_pause_mi_composition,
)


def _toy_rows(*, pause_id: int = 7) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for cond, fam, nvl in (
        ("identical_obj", 0.2, 0.5),
        ("novel_obj", 0.15, 0.25),
    ):
        for bout in range(6):
            rows.append(
                {
                    "animal_id": "a1",
                    "sex": "F",
                    "tx": "noSD",
                    "phase_layer": "NOR_TX",
                    "condition_layer": cond,
                    "trial_key": "t1",
                    "bout_index": bout,
                    "raw_syllable_id": pause_id if bout % 2 == 0 else 1,
                    "bout_mean_dist_fam_m": fam + 0.02 * bout,
                    "bout_mean_dist_nvl_m": nvl + 0.01 * bout,
                }
            )
    return rows


def test_pause_mi_runs_on_toy_bouts() -> None:
    pause_df, full_df, _ = compute_pause_and_full_mi(_toy_rows(), pause_id=7, n_bins=3, n_perm=20, seed=0)
    assert len(pause_df) == 2
    assert len(full_df) == 2
    assert set(pause_df["stim_var"]) == {"dist_fam", "dist_nvl"}


def test_delta_excess_fam_nvl_pair() -> None:
    mi = pd.DataFrame(
        {
            "animal_id": ["a1", "a1"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "mi_label": ["pause_binary", "pause_binary"],
            "stim_var": ["dist_fam", "dist_nvl"],
                "excess": [0.1, 0.3],
                "mi_mm": [0.05, 0.25],
        }
    )
    out = delta_excess(mi)
    assert len(out) == 1
    assert out.iloc[0]["delta_excess"] == pytest.approx(0.2)


def test_join_pause_mi_composition_inner() -> None:
    delta = pd.DataFrame(
        {
            "animal_id": ["a1", "a2"],
            "sex": ["F", "M"],
            "tx": ["noSD", "GHSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "mi_label": ["pause_binary", "pause_binary"],
            "delta_excess": [0.05, -0.02],
        }
    )
    comp = pd.DataFrame(
        {
            "animal_id": ["a1", "a3"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "p_novel": [0.04, 0.01],
        }
    )
    joined = join_pause_mi_composition(delta, comp, y_col="p_novel")
    assert len(joined) == 1
    assert joined.iloc[0]["animal_id"] == "a1"
