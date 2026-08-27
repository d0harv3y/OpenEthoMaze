"""Syllable × session Δp group tests (one model-local id per row)."""

from __future__ import annotations

import pandas as pd

from nor_object_mi._pub_style import SEX_ORDER
from nor_object_mi.simpler_first_da import apply_bh_grouped
from vast_moseq.cohort_meta import STRAIN_ORDER, TX_ORDER, norm_tx
from vast_moseq.vast_cluster_kruskal import (
    STX_LEVELS,
    VAST_PHASES,
    VAST_STEPS,
    _kruskal_k,
    _mann_whitney_two,
    _with_stx_label,
)

SYLLABLE_KEYS = ("model", "raw_syllable_id")


def pick_late_early_winners(
    tests: pd.DataFrame,
    *,
    phase_layer: str = "S05",
    require_positive: bool = True,
    fdr_only: bool = False,
) -> pd.DataFrame:
    """Per model: best late−early Δp syllable at ``phase_layer`` (top-right volcano)."""
    sub = tests[tests["step"] == "late_early"].copy()
    sub = sub[sub["phase_layer"] == phase_layer]
    sub["median_delta_p"] = pd.to_numeric(sub["median_delta_p"], errors="coerce")
    sub["p"] = pd.to_numeric(sub["p"], errors="coerce")
    if require_positive:
        sub = sub[sub["median_delta_p"] > 0]
    if fdr_only:
        hit = sub["hit_fdr05"].astype(str).str.lower().isin(("true", "1"))
        sub = sub[hit]
    sub = sub.sort_values(["median_delta_p", "p"], ascending=[False, True])
    winners = (
        sub.groupby("model", sort=True, as_index=False)
        .head(1)
        .loc[:, ["model", "raw_syllable_id", "phase_layer", "median_delta_p", "p", "hit_fdr05"]]
        .reset_index(drop=True)
    )
    winners["syllable_label"] = winners.apply(
        lambda r: f"{r['model']}|syl{int(r['raw_syllable_id'])}", axis=1
    )
    return winners


def filter_deltas_to_winners(deltas: pd.DataFrame, winners: pd.DataFrame) -> pd.DataFrame:
    keys = winners[["model", "raw_syllable_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    return out[out["step"].isin(VAST_STEPS)].copy()


def _iter_syllables(med: pd.DataFrame) -> list[tuple[str, int]]:
    pairs = med[list(SYLLABLE_KEYS)].drop_duplicates().sort_values(list(SYLLABLE_KEYS))
    return [(str(r.model), int(r.raw_syllable_id)) for r in pairs.itertuples(index=False)]


def kruskal_by_syllable_session_step_sex_tx_pairwise(med: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for model, sid in _iter_syllables(med):
        sub_s = med[(med["model"] == model) & (med["raw_syllable_id"] == sid)]
        for phase in VAST_PHASES:
            for step in VAST_STEPS:
                for sex in SEX_ORDER:
                    g = sub_s[
                        (sub_s["phase_layer"] == phase)
                        & (sub_s["step"] == step)
                        & (sub_s["sex"] == sex)
                    ]
                    rec = _mann_whitney_two(
                        g,
                        factor="tx",
                        level_a=TX_ORDER[0],
                        level_b=TX_ORDER[1],
                    )
                    rows.append(
                        {
                            "model": model,
                            "raw_syllable_id": sid,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["sex", "step"])


def kruskal_by_syllable_session_step_sex_strain_pairwise(med: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for model, sid in _iter_syllables(med):
        sub_s = med[(med["model"] == model) & (med["raw_syllable_id"] == sid)]
        for phase in VAST_PHASES:
            for step in VAST_STEPS:
                for sex in SEX_ORDER:
                    g = sub_s[
                        (sub_s["phase_layer"] == phase)
                        & (sub_s["step"] == step)
                        & (sub_s["sex"] == sex)
                    ]
                    rec = _mann_whitney_two(
                        g,
                        factor="strain",
                        level_a=STRAIN_ORDER[0],
                        level_b=STRAIN_ORDER[1],
                    )
                    rows.append(
                        {
                            "model": model,
                            "raw_syllable_id": sid,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["sex", "step"])


def kruskal_by_syllable_session_step_sex_stx(med: pd.DataFrame) -> pd.DataFrame:
    labeled = _with_stx_label(med)
    rows: list[dict[str, object]] = []
    for model, sid in _iter_syllables(labeled):
        sub_s = labeled[(labeled["model"] == model) & (labeled["raw_syllable_id"] == sid)]
        for phase in VAST_PHASES:
            for step in VAST_STEPS:
                for sex in SEX_ORDER:
                    g = sub_s[
                        (sub_s["phase_layer"] == phase)
                        & (sub_s["step"] == step)
                        & (sub_s["sex"] == sex)
                    ]
                    rec = _kruskal_k(g, factor="stx", levels=STX_LEVELS)
                    rows.append(
                        {
                            "model": model,
                            "raw_syllable_id": sid,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["sex", "step"])
