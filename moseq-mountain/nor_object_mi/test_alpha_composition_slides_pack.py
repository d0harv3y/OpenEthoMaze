"""Litmus / metamorphic checks for alphabet-wide richness / Shannon slides pack."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from nor_object_mi.alpha_composition_slides_pack import (
    build_metric_pack,
    levels_long_from_presence,
)


def _toy_presence() -> pd.DataFrame:
    """Two models, two animals; known richness / Shannon levels."""
    rows = []
    for model in ("m_a", "m_b"):
        bump = 2 if model == "m_b" else 0
        for aid, sex, tx, r0, r1, r2 in (
            ("a", "F", "noSD", 4 + bump, 6 + bump, 8 + bump),
            ("b", "F", "GHSD", 5 + bump, 7 + bump, 9 + bump),
            ("c", "M", "RBSD", 3 + bump, 5 + bump, 7 + bump),
        ):
            for session in ("NOR_BL", "NOR_TX"):
                # +1 richness at TX
                add = 1 if session == "NOR_TX" else 0
                rn0, rn1, rn2 = r0 + add, r1 + add, r2 + add
                # Shannon bits proportional for litmus (not true Shannon of a composition)
                h0, h1, h2 = rn0 / 4.0, rn1 / 4.0, rn2 / 4.0
                for step, left_r, right_r, left_h, right_h in (
                    ("no_obj->id_obj", rn0, rn1, h0, h1),
                    ("id_obj->nvl_obj", rn1, rn2, h1, h2),
                    ("no_obj->nvl_obj", rn0, rn2, h0, h2),
                ):
                    rows.append(
                        {
                            "model": model,
                            "animal_id": aid,
                            "sex": sex,
                            "condition": tx,
                            "session": session,
                            "step": step,
                            "richness_left": left_r,
                            "richness_right": right_r,
                            "shannon_bits_left": left_h,
                            "shannon_bits_right": right_h,
                            "frac_near_left": 0.1,
                            "frac_near_right": 0.2,
                            "delta_frac_near": 0.1,
                            "mean_dist_any_m_left": 0.2,
                            "mean_dist_any_m_right": 0.1,
                            "delta_mean_dist_any_m": -0.1,
                            "delta_richness": right_r - left_r,
                            "delta_shannon_bits": right_h - left_h,
                            "braycurtis": 0.1,
                        }
                    )
    return pd.DataFrame(rows)


def test_levels_id_obj_litmus() -> None:
    d = _toy_presence()
    levels = levels_long_from_presence(d, metric="richness")
    assert set(levels["trial"].astype(str)) == {"no_obj", "id_obj", "nvl_obj"}
    a_bl = levels[
        (levels["animal_id"] == "a")
        & (levels["session"] == "NOR_BL")
        & (levels["model"] == "m_a")
    ]
    assert float(a_bl.loc[a_bl["trial"].astype(str) == "no_obj", "p"].iloc[0]) == 4.0
    assert float(a_bl.loc[a_bl["trial"].astype(str) == "id_obj", "p"].iloc[0]) == 6.0
    assert float(a_bl.loc[a_bl["trial"].astype(str) == "nvl_obj", "p"].iloc[0]) == 8.0


def test_id_obj_mismatch_raises() -> None:
    d = _toy_presence()
    # Break novelty left richness for one row
    mask = (d["step"] == "id_obj->nvl_obj") & (d["animal_id"] == "a") & (d["model"] == "m_a")
    d.loc[mask, "richness_left"] = 99
    with pytest.raises(ValueError, match="id_obj richness disagrees"):
        levels_long_from_presence(d, metric="richness")


def test_trial_and_session_deltas() -> None:
    pack = build_metric_pack(_toy_presence(), metric="richness")
    assert len(pack["kruskal_level"]) == 24
    # animal a median across models: BL no_obj richness = median(4,6)=5
    med = pack["animal_level"]
    a_bl = med[(med["animal_id"] == "a") & (med["session"] == "NOR_BL") & (med["trial"].astype(str) == "no_obj")]
    assert float(a_bl["p"].iloc[0]) == 5.0

    trial = pack["trial_step_delta"]
    a_nov = trial[
        (trial["animal_id"] == "a")
        & (trial["session"] == "NOR_BL")
        & (trial["trial_step"] == "id_obj->nvl_obj")
    ]
    # per model Δ = 2; median across models = 2
    assert abs(float(a_nov["delta_p"].iloc[0]) - 2.0) < 1e-12

    sess = pack["session_step_delta"]
    a_tx = sess[
        (sess["animal_id"] == "a")
        & (sess["trial"].astype(str) == "nvl_obj")
        & (sess["session_step"] == "BL->TX")
    ]
    # TX − BL = +1 on richness for both models
    assert abs(float(a_tx["delta_p"].iloc[0]) - 1.0) < 1e-12


def test_shannon_pack_shapes() -> None:
    pack = build_metric_pack(_toy_presence(), metric="shannon_bits")
    assert len(pack["kruskal_level"]) == 24
    assert len(pack["kruskal_trial_step"]) == 24
    assert len(pack["kruskal_session_step"]) == 36
    assert pack["kruskal_per_model_level"]["model"].nunique() == 2
    # identity: within-model Shannon level finite
    assert np.isfinite(pack["levels_model"]["p"]).all()
