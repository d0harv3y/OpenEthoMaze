"""Litmus checks for paired Bray–Curtis slides pack (step lattices only)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from nor_object_mi.braycurtis_slides_pack import (
    build_bc_pack,
    remap_session_step,
)


def test_remap_session_step_condition_to_tx() -> None:
    s = pd.Series(
        [
            "BL->condition",
            "condition->REC3hr",
            "condition->REC11hr",
            "BL->TX",
            "REC3hr->REC11hr",
        ]
    )
    out = remap_session_step(s)
    assert list(out) == [
        "BL->TX",
        "TX->REC3hr",
        "TX->REC11hr",
        "BL->TX",
        "REC3hr->REC11hr",
    ]


def _toy_presence(path: Path) -> Path:
    rows = []
    for model, bump in (("m_a", 0.0), ("m_b", 0.1)):
        for aid, sex, tx, base in (
            ("a", "F", "noSD", 0.2),
            ("b", "F", "GHSD", 0.4),
            ("c", "M", "RBSD", 0.3),
        ):
            for session in ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr"):
                for step in ("no_obj->id_obj", "id_obj->nvl_obj", "no_obj->nvl_obj"):
                    bc = base + bump + (0.05 if session == "NOR_TX" else 0.0)
                    rows.append(
                        {
                            "model": model,
                            "animal_id": aid,
                            "sex": sex,
                            "condition": tx,
                            "session": session,
                            "step": step,
                            "braycurtis": bc,
                            "left": step.split("->")[0],
                            "right": step.split("->")[1],
                        }
                    )
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def _toy_session(path: Path) -> Path:
    rows = []
    for model, bump in (("m_a", 0.0), ("m_b", 0.1)):
        for aid, sex, tx, base in (
            ("a", "F", "noSD", 0.15),
            ("b", "F", "GHSD", 0.35),
            ("c", "M", "RBSD", 0.25),
        ):
            for trial in ("no_obj", "id_obj", "nvl_obj"):
                for step_legacy, bc_add in (
                    ("BL->condition", 0.0),
                    ("condition->REC3hr", 0.02),
                    ("REC3hr->REC11hr", 0.04),
                    ("BL->REC11hr", 0.06),
                    ("BL->REC3hr", 0.03),
                    ("condition->REC11hr", 0.05),
                ):
                    rows.append(
                        {
                            "model": model,
                            "animal_id": aid,
                            "sex": sex,
                            "condition": tx,
                            "trial": trial,
                            "session_step": step_legacy,
                            "braycurtis": base + bump + bc_add,
                            "step": step_legacy,
                            "left": "L",
                            "right": "R",
                        }
                    )
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def test_build_pack_shapes_and_median(tmp_path: Path) -> None:
    pres = _toy_presence(tmp_path / "pres.csv")
    sess = _toy_session(tmp_path / "sess.csv")
    pack = build_bc_pack(presence_csv=pres, session_csv=sess)
    assert len(pack["kruskal_trial_step"]) == 24
    assert len(pack["kruskal_session_step"]) == 36
    assert set(pack["session_step_delta"]["session_step"].astype(str)) == {
        "BL->TX",
        "TX->REC3hr",
        "REC3hr->REC11hr",
        "BL->REC11hr",
        "BL->REC3hr",
        "TX->REC11hr",
    }
    # animal a, BL, presence step: median(0.2, 0.3) = 0.25
    trial = pack["trial_step_delta"]
    a = trial[
        (trial["animal_id"] == "a")
        & (trial["session"] == "NOR_BL")
        & (trial["trial_step"] == "no_obj->id_obj")
    ]
    assert abs(float(a["bc"].iloc[0]) - 0.25) < 1e-12
    assert np.isfinite(pack["session_step_delta"]["bc"]).all()
