"""Toy litmus for the inventory duration-band pick."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.duration_band import pick_duration_band  # noqa: E402


def test_pick_duration_band_is_local_duration_peak() -> None:
    counts = pd.DataFrame(
        {
            "model": ["m"] * 5,
            "syllable": [0, 1, 2, 3, 99],
            "freq_rank": [0, 1, 2, 3, 40],
            "median_bout_frames": [8.0, 28.0, 7.0, 6.0, 90.0],
            "occupancy": [0.1, 0.4, 0.1, 0.1, 0.01],
            "n_bouts": [100, 80, 70, 60, 5],
        }
    )
    p = pick_duration_band(counts, max_freq_rank=15)
    assert len(p) == 1
    assert int(p.iloc[0]["raw_syllable_id"]) == 1
    assert int(p.iloc[0]["freq_rank"]) == 1
    assert int(p.iloc[0]["occupancy_rank"]) == 0
    assert float(p.iloc[0]["neighbor_median_bout_frames"]) == 7.0
