"""Litmus checks for between-phase pairing with condition held fixed."""

from __future__ import annotations

import pandas as pd
import pytest

from nor_object_mi.simpler_first_session_paired import (
    overlay_step_suptitle_parts,
    paired_n_by_step,
    run_model_session_paired,
    step_arrow_emph,
)
from nor_object_mi.simpler_first_presence import (
    _paired_delta_table,
    build_animal_condition_table,
)


def _bout(
    *,
    animal_id: str,
    phase: str,
    cond: str,
    sid: int,
    frames: int,
    dist: float,
    sex: str = "F",
    condition: str = "noSD",
) -> dict[str, object]:
    return {
        "animal_id": animal_id,
        "sex": sex,
        "condition": condition,
        "session": phase,
        "trial": cond,
        "raw_syllable_id": sid,
        "bout_frames": frames,
        "bout_mean_dist_any_m": dist,
    }


def test_paired_n_by_step_counts_animals() -> None:
    df = pd.DataFrame(
        {
            "session_step": ["BL->TX", "BL->TX", "BL->REC11hr"],
            "animal_id": ["a1", "a2", "a1"],
        }
    )
    n = paired_n_by_step(df)
    assert n["BL->TX"] == 2
    assert n["BL->REC11hr"] == 1


def test_step_arrow_emph_is_directional_not_subtraction() -> None:
    assert step_arrow_emph("BL->TX") == "(BL)→(TX)"
    assert step_arrow_emph("BL->REC11hr") == "(BL)→(REC11)"


def test_overlay_step_suptitle_states_right_minus_left() -> None:
    emph, after = overlay_step_suptitle_parts("BL->TX", {"BL->TX": 144})
    assert emph == "(BL)→(TX)"
    assert "n=144 paired" in after
    assert "Δp_k = TX − BL" in after


def test_phase_pair_drops_animal_missing_from_one_phase() -> None:
    rows = [
        _bout(animal_id="both", phase="NOR_BL", cond="id_obj", sid=1, frames=100, dist=0.20),
        _bout(animal_id="both", phase="NOR_TX", cond="id_obj", sid=1, frames=100, dist=0.05),
        _bout(animal_id="bl_only", phase="NOR_BL", cond="id_obj", sid=1, frames=100, dist=0.20),
    ]
    ac_bl = build_animal_condition_table(pd.DataFrame(rows), session="NOR_BL")
    ac_tx = build_animal_condition_table(pd.DataFrame(rows), session="NOR_TX")
    ac = pd.concat([ac_bl, ac_tx], ignore_index=True)
    sub = ac[ac["trial"] == "id_obj"]
    dtab = _paired_delta_table(
        sub,
        step="BL->TX",
        left="NOR_BL",
        right="NOR_TX",
        metrics=("frac_near", "mean_dist_any_m", "richness", "shannon_bits"),
        pair_col="session",
    )
    assert set(dtab["animal_id"]) == {"both"}
    assert float(dtab.loc[0, "delta_frac_near"]) > 0  # 0% near → 100% near


def test_unfiltered_phase_pair_rejects_duplicate_animals() -> None:
    rows = [
        _bout(animal_id="a1", phase="NOR_BL", cond="no_obj", sid=1, frames=50, dist=0.20),
        _bout(animal_id="a1", phase="NOR_BL", cond="id_obj", sid=1, frames=50, dist=0.20),
        _bout(animal_id="a1", phase="NOR_TX", cond="no_obj", sid=1, frames=50, dist=0.05),
        _bout(animal_id="a1", phase="NOR_TX", cond="id_obj", sid=1, frames=50, dist=0.05),
    ]
    ac = pd.concat(
        [
            build_animal_condition_table(pd.DataFrame(rows), session="NOR_BL"),
            build_animal_condition_table(pd.DataFrame(rows), session="NOR_TX"),
        ],
        ignore_index=True,
    )
    with pytest.raises(ValueError, match="duplicate animal_id"):
        _paired_delta_table(
            ac,
            step="BL->TX",
            left="NOR_BL",
            right="NOR_TX",
            metrics=("frac_near",),
            pair_col="session",
        )


def test_condition_held_ignores_other_condition_shares() -> None:
    """nvl_obj BL→TX must not see the id_obj syllable swap."""
    rows = []
    for phase, novel_frames, id_frames, dist in (
        ("NOR_BL", {1: 100}, {1: 10, 2: 90}, 0.20),
        ("NOR_TX", {1: 100}, {1: 90, 2: 10}, 0.20),
    ):
        for sid, fr in novel_frames.items():
            rows.append(
                _bout(
                    animal_id="a1",
                    phase=phase,
                    cond="nvl_obj",
                    sid=sid,
                    frames=fr,
                    dist=dist,
                )
            )
        for sid, fr in id_frames.items():
            rows.append(
                _bout(
                    animal_id="a1",
                    phase=phase,
                    cond="id_obj",
                    sid=sid,
                    frames=fr,
                    dist=dist,
                )
            )
    ac = pd.concat(
        [
            build_animal_condition_table(pd.DataFrame(rows), session="NOR_BL"),
            build_animal_condition_table(pd.DataFrame(rows), session="NOR_TX"),
        ],
        ignore_index=True,
    )
    scalar_tests, scalar_deltas, da_tests, _da_deltas = run_model_session_paired(ac)
    novel = scalar_deltas[
        (scalar_deltas["trial"] == "nvl_obj")
        & (scalar_deltas["step"] == "BL->TX")
    ]
    assert len(novel) == 1
    assert float(novel.iloc[0]["braycurtis"]) == 0.0
    da_novel = da_tests[
        (da_tests["trial"] == "nvl_obj") & (da_tests["session_step"] == "BL->TX")
    ]
    # only syllable 1, Δp = 0
    assert set(da_novel["raw_syllable_id"].astype(int)) == {1}
    assert float(da_novel.iloc[0]["median_delta_p"]) == 0.0
    id_da = da_tests[
        (da_tests["trial"] == "id_obj") & (da_tests["session_step"] == "BL->TX")
    ]
    assert set(id_da["raw_syllable_id"].astype(int)) == {1, 2}
    assert not scalar_tests.empty
