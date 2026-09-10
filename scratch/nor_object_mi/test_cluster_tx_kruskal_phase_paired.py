"""Litmus for phase-paired cluster Kruskal overview."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster_tx_kruskal_phase_paired import (  # noqa: E402
    PHASE_STEPS,
    animal_median_delta_p_by_cluster,
    attach_cluster_ids,
    kruskal_by_cluster_trial_session_step_sex,
)


def test_kruskal_grid_shape() -> None:
    mapped = pd.DataFrame(
        {
            "cluster_id": [0, 0, 0, 0],
            "animal_id": [1, 1, 2, 2],
            "sex": ["F", "F", "F", "F"],
            "condition": ["noSD", "GHSD", "noSD", "GHSD"],
            "trial": ["nvl_obj"] * 4,
            "session_step": ["BL->TX"] * 4,
            "delta_p": [0.01, 0.02, 0.5, 0.6],
            "model": ["m1", "m1", "m1", "m1"],
        }
    )
    med = animal_median_delta_p_by_cluster(mapped)
    kr = kruskal_by_cluster_trial_session_step_sex(med)
    assert len(kr) == 1 * 3 * len(PHASE_STEPS) * 2
    assert "q_bh" in kr.columns
    assert "hit_fdr05_col" in kr.columns


def test_syllable_pp_kruskal_panel_bh() -> None:
    from nor_object_mi.cluster_tx_kruskal_phase_paired import (
        PHASE_STEPS,
        kruskal_by_syllable_trial_session_step_sex,
    )

    rows = []
    for sid, base in ((3, 0.01), (7, 0.0)):
        for step in PHASE_STEPS[:1]:
            for condition, bump in (("noSD", 0.0), ("GHSD", 0.5)):
                for animal in (1, 2):
                    rows.append(
                        {
                            "raw_syllable_id": sid,
                            "animal_id": animal,
                            "sex": "F",
                            "condition": condition,
                            "trial": "nvl_obj",
                            "session_step": step,
                            "delta_p": base + bump + 0.01 * animal,
                        }
                    )
    kr = kruskal_by_syllable_trial_session_step_sex(pd.DataFrame(rows))
    assert "locus" in kr.columns
    assert "q_bh" in kr.columns


def test_attach_cluster_ids_keeps_session_steps() -> None:
    rep = pd.DataFrame(
        {"model": ["m1"], "raw_syllable_id": [7], "cluster_id": [13], "n_bouts": [10]}
    )
    deltas = pd.DataFrame(
        {
            "model": ["m1", "m1"],
            "raw_syllable_id": [7, 7],
            "session_step": ["BL->TX", "TX->REC3hr"],
            "trial": ["nvl_obj", "nvl_obj"],
            "delta_p": [0.1, 0.2],
            "animal_id": ["a", "a"],
            "sex": ["F", "F"],
            "condition": ["noSD", "noSD"],
        }
    )
    out = attach_cluster_ids(deltas, rep)
    assert len(out) == 2
    assert set(out["session_step"]) == {"BL->TX", "TX->REC3hr"}
