"""Litmus checks for INFO DR ↔ pause bout mi_mm_nvl."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.info_dr_pause_bout_mi import (  # noqa: E402
    PAUSE_MI_COL,
    join_dr_pause_mi,
    load_pause_mi_nvl,
    run_info_lattice,
)


def test_load_pause_mi_nvl_from_delta(tmp_path: Path) -> None:
    df = pd.DataFrame(
        {
            "animal_id": ["1", "1"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "mi_label": ["pause_binary", "full_alphabet"],
            "mi_mm_nvl": [0.12, 0.30],
            "mi_mm_fam": [0.08, 0.20],
            "excess_nvl": [0.01, 0.02],
            "delta_excess": [0.0, 0.01],
        }
    )
    df.to_csv(tmp_path / "pause_stim_delta_excess.csv", index=False)
    out = load_pause_mi_nvl(tmp_path)
    assert len(out) == 1
    assert out.iloc[0][PAUSE_MI_COL] == pytest.approx(0.12)


def test_join_dr_pause_mi_inner() -> None:
    dr = pd.DataFrame(
        {
            "animal_id": ["1", "2"],
            "sex": ["F", "M"],
            "tx": ["noSD", "GHSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            "dr_exclusive": [0.2, -0.1],
            "n_models": [21, 21],
        }
    )
    pause = pd.DataFrame(
        {
            "animal_id": ["1", "3"],
            "sex": ["F", "F"],
            "tx": ["noSD", "noSD"],
            "phase_layer": ["NOR_TX", "NOR_TX"],
            PAUSE_MI_COL: [0.15, 0.05],
            "n_models": [1, 1],
        }
    )
    joined = join_dr_pause_mi(dr, pause)
    assert len(joined) == 1
    assert joined.iloc[0]["animal_id"] == "1"


def test_info_lattice_runs_on_toy_joined() -> None:
    rng = np.random.default_rng(0)
    rows = []
    for i in range(40):
        rows.append(
            {
                "animal_id": str(3000 + i),
                "sex": "F" if i % 2 == 0 else "M",
                "tx": "noSD" if i % 3 else "GHSD",
                "phase_layer": "NOR_TX",
                "dr_exclusive": rng.uniform(-0.5, 0.5),
                PAUSE_MI_COL: rng.uniform(0.0, 0.4),
            }
        )
    joined = pd.DataFrame(rows)
    tests = run_info_lattice(joined, n_bins=3, n_perm=50, seed=1)
    assert len(tests) == 8
    assert "mi_mm_bits" in tests.columns
