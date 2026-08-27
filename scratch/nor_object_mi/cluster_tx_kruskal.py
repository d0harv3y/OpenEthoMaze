"""Kruskal Δp ~ tx by HDBSCAN cluster × phase (mapped id per model × cluster)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi._pub_style import PHASES, SEX_ORDER
from nor_object_mi.cluster13_tx_delta import STEPS, kruskal_tx
from nor_object_mi.simpler_first_da import apply_bh_grouped


def representative_cluster_ids(proto: pd.DataFrame) -> pd.DataFrame:
    """One raw_syllable_id per model × cluster_id (max n_bouts within cluster)."""
    need = {"model", "cluster_id", "raw_syllable_id", "n_bouts"}
    missing = need - set(proto.columns)
    if missing:
        raise ValueError(f"proto missing {sorted(missing)}")
    pos = proto[proto["cluster_id"] >= 0].copy()
    if pos.empty:
        return pd.DataFrame(columns=sorted(need))
    idx = pos.groupby(["model", "cluster_id"], sort=True)["n_bouts"].idxmax()
    return pos.loc[idx, ["model", "cluster_id", "raw_syllable_id", "n_bouts"]].reset_index(drop=True)


def attach_cluster_ids(deltas: pd.DataFrame, rep: pd.DataFrame) -> pd.DataFrame:
    """Keep presence/novelty steps with cluster_id from representative map."""
    keys = rep[["model", "raw_syllable_id", "cluster_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    return out[out["step"].isin(STEPS)].copy()


def animal_median_delta_p_by_cluster(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per cluster × animal × phase × step: median Δp across models."""
    keys = ["cluster_id", "animal_id", "sex", "tx", "phase_layer", "step"]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=float)
        v = v[v == v]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "n_models": int(g["model"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def kruskal_by_cluster_phase_step_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each cluster × phase × step × sex.

    BH (Benjamini–Hochberg false discovery rate) family = cluster × phase cells
    within each sex × step panel (220 cells per panel this run).
    """
    rows: list[dict[str, object]] = []
    clusters = sorted(int(x) for x in med["cluster_id"].unique())
    for cid in clusters:
        sub_c = med[med["cluster_id"] == cid]
        for phase in PHASES:
            for step in STEPS:
                for sex in SEX_ORDER:
                    g = sub_c[
                        (sub_c["phase_layer"] == phase)
                        & (sub_c["step"] == step)
                        & (sub_c["sex"] == sex)
                    ]
                    rec = kruskal_tx(g)
                    rows.append(
                        {
                            "cluster_id": cid,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex", "step"])


def cluster_syllable_ids(proto: pd.DataFrame, cluster_id: int = 13) -> pd.DataFrame:
    """All model × raw_syllable_id rows for one HDBSCAN cluster (may be >1 syllable/model)."""
    need = {"model", "cluster_id", "raw_syllable_id", "n_bouts"}
    missing = need - set(proto.columns)
    if missing:
        raise ValueError(f"proto missing {sorted(missing)}")
    sub = proto[proto["cluster_id"] == cluster_id].copy()
    cols = list(need)
    if "ss" in proto.columns:
        cols.append("ss")
    return sub[cols].reset_index(drop=True)


def attach_model_cluster_deltas(deltas: pd.DataFrame, cmap: pd.DataFrame) -> pd.DataFrame:
    """Keep presence/novelty steps for each model's cluster syllable id(s)."""
    keys = cmap[["model", "raw_syllable_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    return out[out["step"].isin(STEPS)].copy()


def animal_delta_p_by_model(mapped: pd.DataFrame) -> pd.DataFrame:
    """One row per model × animal × phase × step × tx; median Δp if multiple syllables."""
    keys = ["model", "animal_id", "sex", "tx", "phase_layer", "step"]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=float)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "n_syllables": int(g["raw_syllable_id"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def kruskal_by_model_phase_step_sex(med: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each model × phase × step × sex.

    BH family = model × phase cells within each sex × step panel.
    """
    rows: list[dict[str, object]] = []
    models = sorted(str(x) for x in med["model"].unique())
    for model in models:
        sub_m = med[med["model"] == model]
        for phase in PHASES:
            for step in STEPS:
                for sex in SEX_ORDER:
                    g = sub_m[
                        (sub_m["phase_layer"] == phase)
                        & (sub_m["step"] == step)
                        & (sub_m["sex"] == sex)
                    ]
                    rec = kruskal_tx(g)
                    rows.append(
                        {
                            "model": model,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex", "step"])


def model_row_labels(models: list[str], cmap: pd.DataFrame) -> list[str]:
    """Short y-axis labels: ss when present, else trailing model token."""
    ss_by_model = (
        cmap.drop_duplicates("model").set_index("model")["ss"].astype(int).to_dict()
        if "ss" in cmap.columns
        else {}
    )
    labels: list[str] = []
    for model in models:
        if model in ss_by_model:
            labels.append(f"ss-{ss_by_model[model]}")
        else:
            labels.append(str(model).split("_")[-1][:12])
    return labels


def filter_presence_novelty(deltas: pd.DataFrame) -> pd.DataFrame:
    """Keep presence/novelty condition steps only."""
    return deltas[deltas["step"].isin(STEPS)].copy()


def kruskal_by_syllable_phase_step_sex(animals: pd.DataFrame) -> pd.DataFrame:
    """Kruskal Δp ~ tx inside each raw_syllable_id × phase × step × sex.

    Caller should pass one kpMS model (ids are model-local). BH family =
    syllable × phase cells within each sex × step panel.
    """
    need = {"raw_syllable_id", "animal_id", "sex", "tx", "phase_layer", "step", "delta_p"}
    missing = need - set(animals.columns)
    if missing:
        raise ValueError(f"animals missing {sorted(missing)}")
    rows: list[dict[str, object]] = []
    sylls = sorted(int(x) for x in animals["raw_syllable_id"].unique())
    for sid in sylls:
        sub_s = animals[animals["raw_syllable_id"] == sid]
        for phase in PHASES:
            for step in STEPS:
                for sex in SEX_ORDER:
                    g = sub_s[
                        (sub_s["phase_layer"] == phase)
                        & (sub_s["step"] == step)
                        & (sub_s["sex"] == sex)
                    ]
                    rec = kruskal_tx(g)
                    rows.append(
                        {
                            "raw_syllable_id": sid,
                            "phase_layer": phase,
                            "step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    out = pd.DataFrame(rows)
    return apply_bh_grouped(out, ["sex", "step"])
