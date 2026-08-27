"""Litmus for movement-bout vs syllable-bout session clocks."""

from __future__ import annotations

import pandas as pd

from nor_object_mi.simpler_first_ambulation_clocks import (
    movement_bout_session,
    syllable_bout_session,
)


def test_movement_session_sums_bout_distance() -> None:
    rows = []
    for i, (dur, dist, spd) in enumerate(((1.0, 0.5, 0.2), (2.0, 1.5, 0.4))):
        for metric, val in (("distance_m", dist), ("mean_speed_mps", spd), ("max_speed_mps", spd)):
            rows.append(
                {
                    "ID": 1,
                    "phase layer": "NOR_TX",
                    "condition layer": "novel_obj",
                    "level": "bout",
                    "index": i,
                    "duration_s": dur,
                    "metric": metric,
                    "value": val,
                }
            )
    out = movement_bout_session(pd.DataFrame(rows))
    assert len(out) == 1
    assert int(out["n_move_bouts"].iloc[0]) == 2
    assert abs(float(out["sum_move_distance_m"].iloc[0]) - 2.0) < 1e-12
    assert abs(float(out["median_move_duration_s"].iloc[0]) - 1.5) < 1e-12


def test_syllable_session_duration_from_frames() -> None:
    df = pd.DataFrame(
        [
            {"animal_id": "1", "phase_layer": "NOR_TX", "condition_layer": "novel_obj", "bout_frames": 15},
            {"animal_id": "1", "phase_layer": "NOR_TX", "condition_layer": "novel_obj", "bout_frames": 30},
        ]
    )
    out = syllable_bout_session(df, fps=30.0)
    assert int(out["n_syll_bouts"].iloc[0]) == 2
    assert abs(float(out["median_syll_duration_s"].iloc[0]) - 0.75) < 1e-12
