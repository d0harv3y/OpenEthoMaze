"""Litmus / metamorphic checks for cluster-13 absolute frame share."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster13_frame_share import (  # noqa: E402
    build_cluster13_frame_share,
    filter_mapped_levels,
    kruskal_by_session_trial_sex,
    levels_long_from_paired,
    mapped_id_table,
    session_step_deltas_from_levels,
    trial_step_deltas_from_levels,
)


def _toy_deltas() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two models, two animals, one session; known frame shares."""
    id_map = pd.DataFrame(
        {
            "model": ["m1", "m2"],
            "raw_syllable_id": [7, 9],
            "cluster13": [True, True],
        }
    )
    rows: list[dict[str, object]] = []
    # animal a: pause share 0.10 / 0.20 / 0.30 on m1; 0.12 / 0.22 / 0.32 on m2
    # animal b: 0.05 / 0.05 / 0.05 both models
    specs = {
        ("a", "F", "noSD", "m1", 7): (0.10, 0.20, 0.30),
        ("a", "F", "noSD", "m2", 9): (0.12, 0.22, 0.32),
        ("b", "F", "GHSD", "m1", 7): (0.05, 0.05, 0.05),
        ("b", "F", "GHSD", "m2", 9): (0.05, 0.05, 0.05),
        ("c", "F", "RBSD", "m1", 7): (0.40, 0.40, 0.40),
        ("c", "F", "RBSD", "m2", 9): (0.40, 0.40, 0.40),
    }
    for (aid, sex, cond, model, sid), (p0, p1, p2) in specs.items():
        rows.append(
            {
                "model": model,
                "animal_id": aid,
                "sex": sex,
                "condition": cond,
                "session": "NOR_TX",
                "raw_syllable_id": sid,
                "step": "no_obj->id_obj",
                "p_left": p0,
                "p_right": p1,
            }
        )
        rows.append(
            {
                "model": model,
                "animal_id": aid,
                "sex": sex,
                "condition": cond,
                "session": "NOR_TX",
                "raw_syllable_id": sid,
                "step": "id_obj->nvl_obj",
                "p_left": p1,
                "p_right": p2,
            }
        )
        # decoy: other syllable + span step ignored
        rows.append(
            {
                "model": model,
                "animal_id": aid,
                "sex": sex,
                "condition": cond,
                "session": "NOR_TX",
                "raw_syllable_id": 1,
                "step": "no_obj->nvl_obj",
                "p_left": 0.99,
                "p_right": 0.01,
            }
        )
    return pd.DataFrame(rows), id_map


def test_mapped_id_table_keeps_all_cluster13() -> None:
    db = pd.DataFrame(
        {
            "model": ["m1", "m1", "m2", "m2"],
            "raw_syllable_id": [7, 8, 9, 1],
            "cluster_id": [13, 13, 13, 17],
            "n_bouts": [10, 5, 12, 3],
        }
    )
    got = mapped_id_table(db, cluster_id=13)
    assert len(got) == 3
    assert set(zip(got["model"], got["raw_syllable_id"])) == {("m1", 7), ("m1", 8), ("m2", 9)}
    got17 = mapped_id_table(db, cluster_id=17)
    assert len(got17) == 1
    assert int(got17.iloc[0]["raw_syllable_id"]) == 1


def test_collapse_median_across_syllables() -> None:
    from nor_object_mi.cluster13_frame_share import collapse_syllables_within_model

    levels = pd.DataFrame(
        {
            "model": ["m1", "m1"],
            "animal_id": ["a", "a"],
            "sex": ["F", "F"],
            "condition": ["noSD", "noSD"],
            "session": ["NOR_TX", "NOR_TX"],
            "trial": ["nvl_obj", "nvl_obj"],
            "raw_syllable_id": [4, 9],
            "p": [0.10, 0.30],
        }
    )
    got = collapse_syllables_within_model(levels)
    assert len(got) == 1
    assert abs(float(got.iloc[0]["p"]) - 0.20) < 1e-12
    assert int(got.iloc[0]["n_syllables"]) == 2


def test_levels_stack_and_id_obj_consistency() -> None:
    deltas, id_map = _toy_deltas()
    mapped = filter_mapped_levels(deltas, id_map)
    levels = levels_long_from_paired(mapped)
    assert set(levels["trial"].astype(str)) == {"no_obj", "id_obj", "nvl_obj"}
    a_m1 = levels[(levels["animal_id"] == "a") & (levels["model"] == "m1")].set_index("trial")
    assert abs(float(a_m1.loc["no_obj", "p"]) - 0.10) < 1e-12
    assert abs(float(a_m1.loc["id_obj", "p"]) - 0.20) < 1e-12
    assert abs(float(a_m1.loc["nvl_obj", "p"]) - 0.30) < 1e-12


def test_levels_reject_id_obj_mismatch() -> None:
    deltas, id_map = _toy_deltas()
    mapped = filter_mapped_levels(deltas, id_map)
    bad = mapped.copy()
    mask = (bad["step"] == "id_obj->nvl_obj") & (bad["animal_id"] == "a") & (bad["model"] == "m1")
    bad.loc[mask, "p_left"] = 0.99
    try:
        levels_long_from_paired(bad)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "id_obj" in str(exc)


def test_animal_median_across_models() -> None:
    deltas, id_map = _toy_deltas()
    med, kr, _ = build_cluster13_frame_share(deltas, id_map)
    a_nvl = med[(med["animal_id"] == "a") & (med["trial"].astype(str) == "nvl_obj")].iloc[0]
    assert abs(float(a_nvl["p"]) - 0.31) < 1e-12  # median(0.30, 0.32)
    assert int(a_nvl["n_models"]) == 2
    assert abs(float(a_nvl["iqr_across_models"]) - 0.01) < 1e-12


def test_kruskal_grid_bh_family_size_and_hit() -> None:
    from nor_object_mi._pub_style import SESSIONS, SEX_ORDER
    from nor_object_mi.simpler_first_presence import TRIALS

    rows: list[dict[str, object]] = []
    for session in SESSIONS:
        for trial in TRIALS:
            for sex in SEX_ORDER:
                # Separated only in NOR_TX × nvl_obj × F; flat elsewhere
                hit_cell = session == "NOR_TX" and trial == "nvl_obj" and sex == "F"
                for cond, base in (("noSD", 0.05), ("GHSD", 0.06), ("RBSD", 0.40)):
                    level = base if hit_cell else 0.10
                    for k in range(6):
                        rows.append(
                            {
                                "animal_id": f"{session}_{trial}_{sex}_{cond}_{k}",
                                "sex": sex,
                                "condition": cond,
                                "session": session,
                                "trial": trial,
                                "p": level + 0.001 * k,
                            }
                        )
    kr = kruskal_by_session_trial_sex(pd.DataFrame(rows))
    assert len(kr) == 24
    assert "q_bh" in kr.columns
    hit = kr[(kr["session"] == "NOR_TX") & (kr["trial"] == "nvl_obj") & (kr["sex"] == "F")].iloc[0]
    assert float(hit["p"]) < 0.01
    flat = kr[(kr["session"] == "NOR_BL") & (kr["trial"] == "no_obj") & (kr["sex"] == "M")].iloc[0]
    assert float(flat["p"]) > 0.05


def test_trial_and_session_step_deltas_from_levels() -> None:
    """Identity: novelty Δ = p(nvl)−p(id); BL→TX Δ = p(TX)−p(BL)."""
    rows: list[dict[str, object]] = []
    for model, bump in (("m1", 0.0), ("m2", 0.02)):
        for session, base in (("NOR_BL", 0.10), ("NOR_TX", 0.20)):
            for trial, add in (("no_obj", 0.0), ("id_obj", 0.05), ("nvl_obj", 0.15)):
                rows.append(
                    {
                        "model": model,
                        "animal_id": "a",
                        "sex": "F",
                        "condition": "noSD",
                        "session": session,
                        "trial": trial,
                        "p": base + add + bump,
                    }
                )
    levels = pd.DataFrame(rows)
    trial_d = trial_step_deltas_from_levels(levels)
    nov = trial_d[(trial_d["session"] == "NOR_BL") & (trial_d["trial_step"] == "id_obj->nvl_obj")].iloc[0]
    assert abs(float(nov["delta_p"]) - 0.10) < 1e-12

    sess_d = session_step_deltas_from_levels(levels)
    bltx = sess_d[(sess_d["trial"] == "nvl_obj") & (sess_d["session_step"] == "BL->TX")].iloc[0]
    assert abs(float(bltx["delta_p"]) - 0.10) < 1e-12
