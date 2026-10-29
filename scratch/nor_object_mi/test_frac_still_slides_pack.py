"""Toy checks for frac_still slides pack builders."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from nor_object_mi.frac_still_slides_pack import (
    build_frac_still_pack,
    load_frac_still_levels,
    session_step_deltas,
    trial_step_deltas,
)


def _toy_ambulation(path: Path) -> Path:
    rows = []
    for aid, sex, tx in (("a", "F", "noSD"), ("b", "F", "GHSD"), ("c", "M", "RBSD")):
        for session in ("NOR_BL", "NOR_TX"):
            for cond_layer, trial_p in (
                ("no_obj", 0.2 if tx == "noSD" else 0.5),
                ("identical_obj", 0.3 if tx == "noSD" else 0.55),
                ("novel_obj", 0.4 if tx == "noSD" else 0.7),
            ):
                # bump TX for tx animals
                p = trial_p + (0.05 if session == "NOR_TX" else 0.0)
                dur = 180.0
                rows.append(
                    {
                        "ID": aid,
                        "cohort": "exp",
                        "sex": sex,
                        "treatment group": tx,
                        "session type": "NOR",
                        "phase layer": session,
                        "condition layer": cond_layer,
                        "duration_s": dur,
                        "metric": "time_immobile_s",
                        "value": p * dur,
                    }
                )
                rows.append(
                    {
                        "ID": aid,
                        "cohort": "exp",
                        "sex": sex,
                        "treatment group": tx,
                        "session type": "NOR",
                        "phase layer": session,
                        "condition layer": cond_layer,
                        "duration_s": dur,
                        "metric": "distance_m",
                        "value": 10.0,
                    }
                )
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_load_frac_still_levels(tmp_path: Path) -> None:
    csv = _toy_ambulation(tmp_path / "amb.csv")
    levels = load_frac_still_levels(csv)
    assert set(levels["trial"].astype(str)) == {"no_obj", "id_obj", "nvl_obj"}
    assert len(levels) == 3 * 2 * 3  # animals × sessions × trials
    a_bl = levels[(levels["animal_id"] == "a") & (levels["session"] == "NOR_BL")]
    assert abs(float(a_bl.loc[a_bl["trial"].astype(str) == "no_obj", "p"].iloc[0]) - 0.2) < 1e-12


def test_trial_step_delta_identity(tmp_path: Path) -> None:
    csv = _toy_ambulation(tmp_path / "amb.csv")
    levels = load_frac_still_levels(csv)
    d = trial_step_deltas(levels)
    a = d[(d["animal_id"] == "a") & (d["session"] == "NOR_BL") & (d["trial_step"] == "id_obj->nvl_obj")]
    assert abs(float(a["delta_p"].iloc[0]) - 0.1) < 1e-12


def test_session_step_and_pack(tmp_path: Path) -> None:
    csv = _toy_ambulation(tmp_path / "amb.csv")
    pack = build_frac_still_pack(csv)
    assert len(pack["kruskal_level"]) == 24
    sess = session_step_deltas(pack["animal_frac_still"])
    a = sess[(sess["animal_id"] == "a") & (sess["trial"].astype(str) == "nvl_obj") & (sess["session_step"] == "BL->TX")]
    assert abs(float(a["delta_p"].iloc[0]) - 0.05) < 1e-12
