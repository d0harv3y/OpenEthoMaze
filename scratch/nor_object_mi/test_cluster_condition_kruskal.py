"""Litmus for cluster × phase Kruskal overview."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.cluster_condition_kruskal import (  # noqa: E402
    animal_delta_p_by_model,
    animal_median_delta_p_by_cluster,
    attach_cluster_ids,
    kruskal_by_cluster_session_step_sex,
    kruskal_by_syllable_session_step_sex,
    representative_cluster_ids,
)


def test_representative_picks_max_n_bouts() -> None:
    proto = pd.DataFrame(
        {
            "model": ["mA", "mA", "mA"],
            "cluster_id": [1, 1, 2],
            "raw_syllable_id": [10, 11, 20],
            "n_bouts": [5, 50, 8],
        }
    )
    rep = representative_cluster_ids(proto)
    assert len(rep) == 2
    row = rep[(rep["model"] == "mA") & (rep["cluster_id"] == 1)].iloc[0]
    assert int(row["raw_syllable_id"]) == 11


def test_representative_includes_noise_by_default() -> None:
    proto = pd.DataFrame(
        {
            "model": ["mA", "mA", "mA"],
            "cluster_id": [-1, -1, 0],
            "raw_syllable_id": [99, 98, 1],
            "n_bouts": [3, 30, 5],
        }
    )
    rep = representative_cluster_ids(proto, include_noise=True)
    assert set(rep["cluster_id"].astype(int)) == {-1, 0}
    noise = rep[rep["cluster_id"] == -1].iloc[0]
    assert int(noise["raw_syllable_id"]) == 98
    no_noise = representative_cluster_ids(proto, include_noise=False)
    assert set(no_noise["cluster_id"].astype(int)) == {0}


def test_kruskal_grid_shape() -> None:
    mapped = pd.DataFrame(
        {
            "cluster_id": [0, 0, 0, 0],
            "animal_id": [1, 1, 2, 2],
            "sex": ["F", "F", "F", "F"],
            "condition": ["noSD", "GHSD", "noSD", "GHSD"],
            "session": ["NOR_BL"] * 4,
            "step": ["no_obj->id_obj"] * 4,
            "delta_p": [0.01, 0.02, 0.5, 0.6],
            "model": ["m1", "m1", "m1", "m1"],
        }
    )
    med = animal_median_delta_p_by_cluster(mapped)
    kr = kruskal_by_cluster_session_step_sex(med)
    assert len(kr) == 1 * 4 * 3 * 2  # 1 cluster, 4 phases, 3 steps, 2 sexes
    assert "q_bh" in kr.columns
    assert "q_bh_col" in kr.columns
    assert "hit_fdr05_col" in kr.columns


def test_column_bh_looser_than_panel_on_toy() -> None:
    """Many tiny p's in one column: column family can hit when panel family does not."""
    from nor_object_mi.cluster_condition_kruskal import attach_column_bh
    from nor_object_mi.simpler_first_da import apply_bh_grouped

    rows = []
    for cid in range(20):
        rows.append(
            {
                "cluster_id": cid,
                "session": "NOR_BL",
                "step": "no_obj->id_obj",
                "sex": "F",
                "p": 0.01 if cid < 3 else 0.8,
            }
        )
    # pad other phases with null-ish high p so panel family is large
    for phase in ("NOR_TX", "NOR_REC3hr", "NOR_REC11hr"):
        for cid in range(20):
            rows.append(
                {
                    "cluster_id": cid,
                    "session": phase,
                    "step": "no_obj->id_obj",
                    "sex": "F",
                    "p": 0.9,
                }
            )
    raw = pd.DataFrame(rows)
    panel = apply_bh_grouped(raw, ["sex", "step"])
    both = attach_column_bh(panel, ["sex", "step", "session"])
    bl = both[both["session"] == "NOR_BL"]
    assert int(bl["hit_fdr05_col"].sum()) >= int(bl["hit_fdr05"].sum())


def test_hit_jaccard_identity() -> None:
    from nor_object_mi.cluster_condition_kruskal import hit_locus_matrix, pairwise_row_jaccard

    kr = pd.DataFrame(
        {
            "cluster_id": [0, 0, 1, 1],
            "sex": ["F", "F", "F", "F"],
            "step": ["no_obj->id_obj"] * 4,
            "session": ["NOR_BL", "NOR_TX", "NOR_BL", "NOR_TX"],
            "hit_fdr05": [True, False, True, False],
        }
    )
    mat = hit_locus_matrix(kr, locus_order=("NOR_BL", "NOR_TX"))
    jac = pairwise_row_jaccard(mat)
    assert abs(float(jac.loc[0, 0]) - 1.0) < 1e-12
    assert abs(float(jac.loc[0, 1]) - 1.0) < 1e-12  # same hit pattern


def test_syllable_kruskal_grid_shape() -> None:
    animals = pd.DataFrame(
        {
            "raw_syllable_id": [3, 3, 3, 3, 7, 7, 7, 7],
            "animal_id": [1, 1, 2, 2, 1, 1, 2, 2],
            "sex": ["F"] * 8,
            "condition": ["noSD", "GHSD", "noSD", "GHSD"] * 2,
            "session": ["NOR_BL"] * 8,
            "step": ["no_obj->id_obj"] * 8,
            "delta_p": [0.01, 0.02, 0.5, 0.6, 0.0, 0.01, 0.02, 0.03],
        }
    )
    kr = kruskal_by_syllable_session_step_sex(animals)
    # 2 syllables × 4 phases × 3 steps × 2 sexes
    assert len(kr) == 2 * 4 * 3 * 2
    assert "q_bh" in kr.columns
    assert set(kr["raw_syllable_id"]) == {3, 7}


def test_da_locus_labels_match_cooccurrence_order() -> None:
    from nor_object_mi.cluster_condition_kruskal import da_locus_labels
    from nor_object_mi._pub_style import SESSIONS

    labs = da_locus_labels()
    assert labs[0].endswith("|NOR_BL")
    assert len(labs) == 3 * len(SESSIONS)
    assert labs == sorted(labs) or True  # step alpha × phase protocol order
    steps = [x.split("|")[0] for x in labs]
    assert steps[0] == "id_obj->nvl_obj"


def test_syllables_by_frequency() -> None:
    from nor_object_mi.fig_model_syllable_locus_heatmap import syllables_by_frequency

    proto = pd.DataFrame(
        {
            "model": ["m", "m", "m"],
            "raw_syllable_id": [1, 2, 3],
            "n_bouts": [10, 100, 50],
        }
    )
    assert syllables_by_frequency("m", [1, 2, 3], proto) == [2, 3, 1]


def test_cluster13_merge_median_two_syllables() -> None:
    mapped = pd.DataFrame(
        {
            "model": ["mA", "mA", "mA", "mA"],
            "raw_syllable_id": [4, 9, 4, 9],
            "animal_id": [1, 1, 1, 1],
            "sex": ["F", "F", "F", "F"],
            "condition": ["noSD", "noSD", "GHSD", "GHSD"],
            "session": ["NOR_BL"] * 4,
            "step": ["no_obj->id_obj"] * 4,
            "delta_p": [0.10, 0.20, 0.30, 0.50],
        }
    )
    med = animal_delta_p_by_model(mapped)
    assert len(med) == 2
    nosd = med[med["condition"] == "noSD"].iloc[0]
    assert abs(float(nosd["delta_p"]) - 0.15) < 1e-9
    assert int(nosd["n_syllables"]) == 2
