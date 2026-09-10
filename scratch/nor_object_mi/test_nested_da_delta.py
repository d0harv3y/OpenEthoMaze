"""Litmus for nested 2nd-order Δp_k composition and Kruskal grids."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster_tx_kruskal_nested import (  # noqa: E402
    animal_delta_p_by_model_nested,
    kruskal_by_model_trial_on_session_sex,
    kruskal_by_model_session_on_trial_sex,
)
from nor_object_mi.nested_da_delta import compose_nested_deltas  # noqa: E402
from nor_object_mi.simpler_first_da import DA_STEPS  # noqa: E402
from nor_object_mi.simpler_first_phase_paired import PHASE_STEP_NAMES  # noqa: E402


def _first_order_condition_step() -> pd.DataFrame:
    rows = []
    for phase in ("NOR_BL", "NOR_TX"):
        for cond_step, left, right in (
            ("no_obj->id_obj", "no_obj", "id_obj"),
            ("id_obj->nvl_obj", "id_obj", "nvl_obj"),
            ("no_obj->nvl_obj", "no_obj", "nvl_obj"),
        ):
            for aid, condition, dp in ((1, "noSD", 0.01), (2, "GHSD", 0.02)):
                rows.append(
                    {
                        "model": "m1",
                        "animal_id": aid,
                        "sex": "F",
                        "condition": condition,
                        "step": cond_step,
                        "condition_step": cond_step,
                        "session": phase,
                        "raw_syllable_id": 7,
                        "delta_p": dp if phase == "NOR_BL" else dp + 0.05,
                    }
                )
    return pd.DataFrame(rows)


def _first_order_session_step() -> pd.DataFrame:
    rows = []
    for cond in ("no_obj", "id_obj"):
        for aid, condition, dp in ((1, "noSD", 0.03), (2, "GHSD", 0.04)):
            rows.append(
                {
                    "model": "m1",
                    "animal_id": aid,
                    "sex": "F",
                    "condition": condition,
                    "session_step": "BL->TX",
                    "trial": cond,
                    "raw_syllable_id": 7,
                    "delta_p": dp if cond == "no_obj" else dp + 0.02,
                }
            )
    return pd.DataFrame(rows)


def test_nested_b_delta_is_difference_of_first_order() -> None:
    first = _first_order_condition_step()
    out = compose_nested_deltas(first, axis="session_on_trial")
    row = out[
        (out["condition_step"] == "no_obj->id_obj")
        & (out["session_step"] == "BL->TX")
        & (out["animal_id"] == 1)
    ].iloc[0]
    assert float(row["delta_p_left"]) == 0.01
    assert abs(float(row["delta_p_right"]) - 0.06) < 1e-12
    assert abs(float(row["delta_p"]) - 0.05) < 1e-12


def test_nested_c_delta_is_difference_of_first_order() -> None:
    first = _first_order_session_step()
    out = compose_nested_deltas(first, axis="trial_on_session")
    row = out[
        (out["session_step"] == "BL->TX")
        & (out["condition_step"] == "no_obj->id_obj")
        & (out["animal_id"] == 1)
    ].iloc[0]
    assert row["delta_p_left"] == 0.03
    assert row["delta_p_right"] == 0.05
    assert abs(float(row["delta_p"]) - 0.02) < 1e-12


def test_kruskal_grid_shapes() -> None:
    med_b = pd.DataFrame(
        {
            "model": ["m1"] * 4,
            "animal_id": [1, 1, 2, 2],
            "sex": ["F"] * 4,
            "condition": ["noSD", "GHSD", "noSD", "GHSD"],
            "condition_step": ["no_obj->id_obj"] * 4,
            "session_step": ["BL->TX"] * 4,
            "delta_p": [0.01, 0.02, 0.5, 0.6],
        }
    )
    kr_b = kruskal_by_model_session_on_trial_sex(med_b)
    assert len(kr_b) == 1 * len(DA_STEPS) * len(PHASE_STEP_NAMES) * 2
    assert "q_bh" in kr_b.columns

    med_c = pd.DataFrame(
        {
            "model": ["m1"] * 4,
            "animal_id": [1, 1, 2, 2],
            "sex": ["F"] * 4,
            "condition": ["noSD", "GHSD", "noSD", "GHSD"],
            "session_step": ["BL->TX"] * 4,
            "condition_step": ["no_obj->id_obj"] * 4,
            "delta_p": [0.01, 0.02, 0.5, 0.6],
        }
    )
    kr_c = kruskal_by_model_trial_on_session_sex(med_c)
    assert len(kr_c) == 1 * len(PHASE_STEP_NAMES) * len(DA_STEPS) * 2

    agg = animal_delta_p_by_model_nested(med_b, axis="session_on_trial")
    assert len(agg) == 4
