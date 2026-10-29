"""Cluster-13 pause syllable: absolute frame share (level), not Δp.

Reconstructs per-trial ``p_k`` from the DA (differential abundance) paired
table (``p_left`` / ``p_right`` on presence + novelty steps), keeps **all**
HDBSCAN cluster-13 syllable ids per kpMS (keypoint-MoSeq) model (median when
>1), then medians across alphabets so one consensus point is one animal ×
session × trial.

Also builds complementary paired Δ tables:
- **trial_step** (prose phase-step): Δp across trials within a session
- **session_step** (prose stage-step): Δp across sessions within a trial
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from nor_object_mi._pub_style import CONDITION_ORDER, SESSIONS, SEX_ORDER
from nor_object_mi.cluster13_condition_delta import STEPS as TRIAL_STEP_NAMES
from nor_object_mi.cluster13_condition_delta import STEP_LAB as TRIAL_STEP_LAB  # noqa: F401 — re-export for fig
from nor_object_mi.cluster13_condition_delta import _iqr, kruskal_condition
from nor_object_mi.cluster_condition_kruskal import animal_delta_p_by_model
from nor_object_mi.simpler_first_da import apply_bh, apply_bh_grouped
from nor_object_mi.simpler_first_presence import TRIALS
from nor_object_mi.simpler_first_session_paired import (
    PHASE_STEPS as SESSION_STEP_DEFS,
)
from nor_object_mi.simpler_first_session_paired import (
    PHASE_STEP_NAMES as SESSION_STEP_NAMES,
)
from nor_object_mi.simpler_first_session_paired import (
    STEP_LAB as SESSION_STEP_LAB,  # noqa: F401 — re-export for fig
)

_MODEL_LABEL_RE = re.compile(r"s1-([^_]+)_s2-([^_]+)_ss-(\d+)")


def short_model_label(model: str) -> str:
    """Compact unique y-label: ``1e8/1e5/ss50`` from paramscan tokens."""
    m = _MODEL_LABEL_RE.search(str(model))
    if m:
        return f"{m.group(1)}/{m.group(2)}/ss{m.group(3)}"
    return str(model).split("_")[-1][:16]


TRIAL_LAB = {
    "no_obj": "acclimation",
    "id_obj": "familiarization",
    "nvl_obj": "recognition",
}

# (step_name, left_trial, right_trial) — prose "phase-step"
TRIAL_STEPS: tuple[tuple[str, str, str], ...] = (
    ("no_obj->id_obj", "no_obj", "id_obj"),
    ("id_obj->nvl_obj", "id_obj", "nvl_obj"),
    ("no_obj->nvl_obj", "no_obj", "nvl_obj"),
)

DELTA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "step",
    "session",
    "raw_syllable_id",
    "p_left",
    "p_right",
    "delta_p",
)


def mapped_id_table(cluster_map: pd.DataFrame, *, cluster_id: int = 13) -> pd.DataFrame:
    """All (model, raw_syllable_id[, ss]) rows for one HDBSCAN ``cluster_id``.

    May be >1 syllable per model (median-merged downstream). Accepts a full
    prototypes table, a prior ``cluster{N}_syllable_map.csv``, or a
    duration-band table with a boolean ``cluster13`` column (legacy; only for
    ``cluster_id == 13``).
    """
    if "cluster_id" in cluster_map.columns:
        sub = cluster_map.loc[pd.to_numeric(cluster_map["cluster_id"], errors="coerce") == int(cluster_id)]
    elif int(cluster_id) == 13 and "cluster13" in cluster_map.columns:
        sub = cluster_map.loc[cluster_map["cluster13"].astype(bool)]
    else:
        sub = cluster_map
    cols = ["model", "raw_syllable_id"]
    if "ss" in sub.columns:
        cols.append("ss")
    if "n_bouts" in sub.columns:
        cols.append("n_bouts")
    if "cluster_id" in sub.columns:
        cols.append("cluster_id")
    keys = sub[cols].drop_duplicates()
    if keys.empty:
        raise ValueError(f"mapped_id_table: no cluster-{cluster_id} rows")
    return keys.reset_index(drop=True)


def filter_mapped_levels(deltas: pd.DataFrame, id_map: pd.DataFrame) -> pd.DataFrame:
    """Keep DA rows for mapped cluster-13 id(s) on presence + novelty steps."""
    keys = id_map[["model", "raw_syllable_id"]].drop_duplicates()
    out = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
    return out[out["step"].isin(("no_obj->id_obj", "id_obj->nvl_obj"))].copy()


def levels_long_from_paired(mapped: pd.DataFrame) -> pd.DataFrame:
    """Stack absolute frame shares for no_obj / id_obj / nvl_obj.

    Presence step supplies ``p(no_obj)`` and ``p(id_obj)``; novelty step
    supplies ``p(nvl_obj)``. ``p(id_obj)`` must match across steps (litmus).
    Join includes ``raw_syllable_id`` so multi-syllable models stay one row
    per syllable.
    """
    need = {
        "model",
        "animal_id",
        "sex",
        "condition",
        "session",
        "step",
        "p_left",
        "p_right",
        "raw_syllable_id",
    }
    missing = need - set(mapped.columns)
    if missing:
        raise ValueError(f"levels_long_from_paired missing columns: {sorted(missing)}")

    pres = mapped[mapped["step"] == "no_obj->id_obj"]
    nov = mapped[mapped["step"] == "id_obj->nvl_obj"]
    join_keys = ["model", "animal_id", "sex", "condition", "session", "raw_syllable_id"]
    j = pres.merge(nov, on=join_keys, how="inner", suffixes=("_pres", "_nov"))
    if j.empty:
        return pd.DataFrame(columns=[*join_keys, "trial", "p"])

    id_diff = (pd.to_numeric(j["p_right_pres"], errors="coerce") - pd.to_numeric(j["p_left_nov"], errors="coerce")).abs()
    if float(np.nanmax(id_diff.to_numpy(dtype=np.float64))) > 1e-12:
        raise ValueError("id_obj frame share disagrees between presence and novelty steps")

    base = j[join_keys].copy()
    parts = [
        base.assign(trial="no_obj", p=pd.to_numeric(j["p_left_pres"], errors="coerce")),
        base.assign(trial="id_obj", p=pd.to_numeric(j["p_right_pres"], errors="coerce")),
        base.assign(trial="nvl_obj", p=pd.to_numeric(j["p_right_nov"], errors="coerce")),
    ]
    out = pd.concat(parts, ignore_index=True)
    out["trial"] = pd.Categorical(out["trial"], categories=list(TRIALS), ordered=True)
    return out


def collapse_syllables_within_model(levels: pd.DataFrame) -> pd.DataFrame:
    """Median frame share across cluster-13 syllables within model × animal × cell."""
    if levels.empty:
        return levels.copy()
    if "raw_syllable_id" not in levels.columns:
        return levels.copy()
    keys = ["model", "animal_id", "sex", "condition", "session", "trial"]
    rows: list[dict[str, object]] = []
    for key_vals, g in levels.groupby(keys, sort=True, observed=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["p"], errors="coerce").to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                "p": float(np.median(v)) if v.size else float("nan"),
                "n_syllables": int(g["raw_syllable_id"].nunique()),
                "n_finite": int(v.size),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["trial"] = pd.Categorical(out["trial"], categories=list(TRIALS), ordered=True)
    return out.sort_values(keys).reset_index(drop=True)

def animal_median_frame_share(levels: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × session × trial: median p across models + IQR salt."""
    keys = ["animal_id", "sex", "condition", "session", "trial"]
    rows: list[dict[str, object]] = []
    for key_vals, g in levels.groupby(keys, sort=True, observed=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["p"], errors="coerce").to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                "p": float(np.median(v)) if v.size else float("nan"),
                "iqr_across_models": _iqr(v),
                "n_models": int(g["model"].nunique()) if "model" in g.columns else int(v.size),
                "n_finite": int(v.size),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["session"] = pd.Categorical(out["session"], categories=list(SESSIONS), ordered=True)
    out["trial"] = pd.Categorical(out["trial"], categories=list(TRIALS), ordered=True)
    out["condition"] = pd.Categorical(out["condition"], categories=list(CONDITION_ORDER), ordered=True)
    out["sex"] = pd.Categorical(out["sex"], categories=list(SEX_ORDER), ordered=True)
    return out.sort_values(keys).reset_index(drop=True)


def _animal_median_delta(
    model_deltas: pd.DataFrame,
    *,
    group_keys: list[str],
) -> pd.DataFrame:
    """Median Δp across models within group_keys; keep IQR salt."""
    rows: list[dict[str, object]] = []
    for key_vals, g in model_deltas.groupby(group_keys, sort=True, observed=True):
        key_map = dict(zip(group_keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g["delta_p"], errors="coerce").to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        rows.append(
            {
                **key_map,
                "delta_p": float(np.median(v)) if v.size else float("nan"),
                "iqr_across_models": _iqr(v),
                "n_models": int(g["model"].nunique()) if "model" in g.columns else int(v.size),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def trial_step_deltas_model_long(levels: pd.DataFrame) -> pd.DataFrame:
    """Model-grain paired Δp across trials within session (before animal median)."""
    need = {"model", "animal_id", "sex", "condition", "session", "trial", "p"}
    missing = need - set(levels.columns)
    if missing:
        raise ValueError(f"trial_step_deltas_model_long missing: {sorted(missing)}")

    join_on = ["model", "animal_id", "sex", "condition", "session"]
    parts: list[pd.DataFrame] = []
    for step, left, right in TRIAL_STEPS:
        L = levels[levels["trial"].astype(str) == left]
        R = levels[levels["trial"].astype(str) == right]
        j = L.merge(R, on=join_on, how="inner", suffixes=("_l", "_r"))
        if j.empty:
            continue
        parts.append(
            j.assign(
                trial_step=step,
                delta_p=pd.to_numeric(j["p_r"], errors="coerce") - pd.to_numeric(j["p_l"], errors="coerce"),
            )[join_on + ["trial_step", "delta_p"]]
        )
    if not parts:
        return pd.DataFrame(columns=[*join_on, "trial_step", "delta_p"])
    return pd.concat(parts, ignore_index=True)


def trial_step_deltas_from_levels(levels: pd.DataFrame) -> pd.DataFrame:
    """Paired Δp across trials within session (prose: phase-step).

    Grain after median: animal × session × trial_step.
    """
    model_d = trial_step_deltas_model_long(levels)
    if model_d.empty:
        return pd.DataFrame(
            columns=[
                "animal_id",
                "sex",
                "condition",
                "session",
                "trial_step",
                "delta_p",
                "iqr_across_models",
                "n_models",
                "n_finite",
            ]
        )
    med = _animal_median_delta(
        model_d,
        group_keys=["animal_id", "sex", "condition", "session", "trial_step"],
    )
    med["session"] = pd.Categorical(med["session"], categories=list(SESSIONS), ordered=True)
    med["trial_step"] = pd.Categorical(med["trial_step"], categories=list(TRIAL_STEP_NAMES), ordered=True)
    return med.sort_values(["animal_id", "session", "trial_step"]).reset_index(drop=True)


def session_step_deltas_model_long(levels: pd.DataFrame) -> pd.DataFrame:
    """Model-grain paired Δp across sessions within trial (before animal median)."""
    need = {"model", "animal_id", "sex", "condition", "session", "trial", "p"}
    missing = need - set(levels.columns)
    if missing:
        raise ValueError(f"session_step_deltas_model_long missing: {sorted(missing)}")

    join_on = ["model", "animal_id", "sex", "condition", "trial"]
    parts: list[pd.DataFrame] = []
    for step, left, right in SESSION_STEP_DEFS:
        L = levels[levels["session"].astype(str) == left]
        R = levels[levels["session"].astype(str) == right]
        j = L.merge(R, on=join_on, how="inner", suffixes=("_l", "_r"))
        if j.empty:
            continue
        parts.append(
            j.assign(
                session_step=step,
                delta_p=pd.to_numeric(j["p_r"], errors="coerce") - pd.to_numeric(j["p_l"], errors="coerce"),
            )[join_on + ["session_step", "delta_p"]]
        )
    if not parts:
        return pd.DataFrame(columns=[*join_on, "session_step", "delta_p"])
    return pd.concat(parts, ignore_index=True)


def session_step_deltas_from_levels(levels: pd.DataFrame) -> pd.DataFrame:
    """Paired Δp across sessions within trial (prose: stage-step).

    Grain after median: animal × trial × session_step.
    """
    model_d = session_step_deltas_model_long(levels)
    if model_d.empty:
        return pd.DataFrame(
            columns=[
                "animal_id",
                "sex",
                "condition",
                "trial",
                "session_step",
                "delta_p",
                "iqr_across_models",
                "n_models",
                "n_finite",
            ]
        )
    med = _animal_median_delta(
        model_d,
        group_keys=["animal_id", "sex", "condition", "trial", "session_step"],
    )
    med["trial"] = pd.Categorical(med["trial"], categories=list(TRIALS), ordered=True)
    med["session_step"] = pd.Categorical(med["session_step"], categories=list(SESSION_STEP_NAMES), ordered=True)
    return med.sort_values(["animal_id", "trial", "session_step"]).reset_index(drop=True)


def kruskal_by_session_trial_sex(med: pd.DataFrame, *, col: str = "p") -> pd.DataFrame:
    """Kruskal frame share ~ condition inside each session × trial × sex.

    BH (Benjamini–Hochberg) family = those 24 cells (4 sessions × 3 trials × 2 sexes).
    """
    rows: list[dict[str, object]] = []
    for session in SESSIONS:
        for trial in TRIALS:
            for sex in SEX_ORDER:
                g = med[(med["session"] == session) & (med["trial"] == trial) & (med["sex"] == sex)]
                rec = kruskal_condition(g, col=col)
                rows.append({"session": session, "trial": trial, "sex": sex, **rec})
    return apply_bh(pd.DataFrame(rows))


def kruskal_by_session_trial_step_sex(med: pd.DataFrame, *, col: str = "delta_p") -> pd.DataFrame:
    """Kruskal Δp ~ condition inside each session × trial_step × sex (24 cells)."""
    rows: list[dict[str, object]] = []
    for session in SESSIONS:
        for step in TRIAL_STEP_NAMES:
            for sex in SEX_ORDER:
                g = med[(med["session"] == session) & (med["trial_step"] == step) & (med["sex"] == sex)]
                rec = kruskal_condition(g, col=col)
                rows.append({"session": session, "trial_step": step, "sex": sex, **rec})
    return apply_bh(pd.DataFrame(rows))


def kruskal_by_trial_session_step_sex(med: pd.DataFrame, *, col: str = "delta_p") -> pd.DataFrame:
    """Kruskal Δp ~ condition inside each trial × session_step × sex (36 cells)."""
    rows: list[dict[str, object]] = []
    for trial in TRIALS:
        for step in SESSION_STEP_NAMES:
            for sex in SEX_ORDER:
                g = med[(med["trial"] == trial) & (med["session_step"] == step) & (med["sex"] == sex)]
                rec = kruskal_condition(g, col=col)
                rows.append({"trial": trial, "session_step": step, "sex": sex, **rec})
    return apply_bh(pd.DataFrame(rows))


def kruskal_per_model_level(levels: pd.DataFrame, *, col: str = "p") -> pd.DataFrame:
    """Kruskal frame share ~ condition per model × session × trial × sex.

    BH family = model × session cells within each trial × sex panel.
    """
    models = sorted(str(x) for x in levels["model"].unique())
    rows: list[dict[str, object]] = []
    for model in models:
        sub_m = levels[levels["model"].astype(str) == model]
        for session in SESSIONS:
            for trial in TRIALS:
                for sex in SEX_ORDER:
                    g = sub_m[(sub_m["session"] == session) & (sub_m["trial"].astype(str) == trial) & (sub_m["sex"] == sex)]
                    rec = kruskal_condition(g, col=col)
                    rows.append(
                        {
                            "model": model,
                            "session": session,
                            "trial": trial,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["trial", "sex"])


def kruskal_per_model_session_step(model_deltas: pd.DataFrame, *, col: str = "delta_p") -> pd.DataFrame:
    """Kruskal Δp ~ condition per model × trial × session_step × sex.

    BH family = model × session_step cells within each trial × sex panel.
    """
    models = sorted(str(x) for x in model_deltas["model"].unique())
    rows: list[dict[str, object]] = []
    for model in models:
        sub_m = model_deltas[model_deltas["model"].astype(str) == model]
        for trial in TRIALS:
            for step in SESSION_STEP_NAMES:
                for sex in SEX_ORDER:
                    g = sub_m[(sub_m["trial"].astype(str) == trial) & (sub_m["session_step"].astype(str) == step) & (sub_m["sex"] == sex)]
                    rec = kruskal_condition(g, col=col)
                    rows.append(
                        {
                            "model": model,
                            "trial": trial,
                            "session_step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["trial", "sex"])


def kruskal_per_model_trial_step(model_deltas: pd.DataFrame, *, col: str = "delta_p") -> pd.DataFrame:
    """Kruskal Δp ~ condition per model × session × trial_step × sex.

    BH family = model × session cells within each trial_step × sex panel
    (panel rows = phase-step; heatmap x = stage).
    """
    models = sorted(str(x) for x in model_deltas["model"].unique())
    rows: list[dict[str, object]] = []
    for model in models:
        sub_m = model_deltas[model_deltas["model"].astype(str) == model]
        for session in SESSIONS:
            for step in TRIAL_STEP_NAMES:
                for sex in SEX_ORDER:
                    g = sub_m[
                        (sub_m["session"].astype(str) == session)
                        & (sub_m["trial_step"].astype(str) == step)
                        & (sub_m["sex"] == sex)
                    ]
                    rec = kruskal_condition(g, col=col)
                    rows.append(
                        {
                            "model": model,
                            "session": session,
                            "trial_step": step,
                            "sex": sex,
                            **rec,
                        }
                    )
    return apply_bh_grouped(pd.DataFrame(rows), ["trial_step", "sex"])


def build_cluster13_frame_share(
    deltas: pd.DataFrame,
    cluster_map: pd.DataFrame,
    *,
    cluster_id: int = 13,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (animal medians, Kruskal table, id map)."""
    id_map = mapped_id_table(cluster_map, cluster_id=cluster_id)
    mapped = filter_mapped_levels(deltas, id_map)
    levels = collapse_syllables_within_model(levels_long_from_paired(mapped))
    med = animal_median_frame_share(levels)
    kr = kruskal_by_session_trial_sex(med)
    return med, kr, id_map


def trial_step_deltas_from_da(mapped_with_delta: pd.DataFrame) -> pd.DataFrame:
    """Model-grain trial_step Δp: median across cluster syllables (prior path)."""
    need = {"model", "animal_id", "sex", "condition", "session", "step", "delta_p", "raw_syllable_id"}
    missing = need - set(mapped_with_delta.columns)
    if missing:
        raise ValueError(f"trial_step_deltas_from_da missing: {sorted(missing)}")
    steps = mapped_with_delta[mapped_with_delta["step"].isin(TRIAL_STEP_NAMES)].copy()
    med = animal_delta_p_by_model(steps)
    return med.rename(columns={"step": "trial_step"})


def build_cluster13_frame_share_pack(
    deltas: pd.DataFrame,
    cluster_map: pd.DataFrame,
    *,
    cluster_id: int = 13,
) -> dict[str, pd.DataFrame]:
    """Level + trial-step + session-step + per-model Kruskal tables."""
    id_map = mapped_id_table(cluster_map, cluster_id=cluster_id)
    mapped = filter_mapped_levels(deltas, id_map)
    levels_raw = levels_long_from_paired(mapped)
    levels = collapse_syllables_within_model(levels_raw)
    med = animal_median_frame_share(levels)
    kr_level = kruskal_by_session_trial_sex(med)

    if "delta_p" in deltas.columns:
        keys = id_map[["model", "raw_syllable_id"]].drop_duplicates()
        mapped_delta = deltas.merge(keys, on=["model", "raw_syllable_id"], how="inner")
        trial_model = trial_step_deltas_from_da(mapped_delta)
    else:
        trial_model = trial_step_deltas_model_long(levels)
    trial_d = (
        _animal_median_delta(
            trial_model,
            group_keys=["animal_id", "sex", "condition", "session", "trial_step"],
        )
        if not trial_model.empty
        else trial_step_deltas_from_levels(levels)
    )
    if not trial_d.empty and "session" in trial_d.columns:
        trial_d["session"] = pd.Categorical(trial_d["session"], categories=list(SESSIONS), ordered=True)
        trial_d["trial_step"] = pd.Categorical(trial_d["trial_step"], categories=list(TRIAL_STEP_NAMES), ordered=True)
    kr_trial = kruskal_by_session_trial_step_sex(trial_d)

    session_model = session_step_deltas_model_long(levels)
    session_d = (
        _animal_median_delta(
            session_model,
            group_keys=["animal_id", "sex", "condition", "trial", "session_step"],
        )
        if not session_model.empty
        else session_step_deltas_from_levels(levels)
    )
    if not session_d.empty and "trial" in session_d.columns:
        session_d["trial"] = pd.Categorical(session_d["trial"], categories=list(TRIALS), ordered=True)
        session_d["session_step"] = pd.Categorical(session_d["session_step"], categories=list(SESSION_STEP_NAMES), ordered=True)
    kr_session = kruskal_by_trial_session_step_sex(session_d)
    kr_model_level = kruskal_per_model_level(levels)
    kr_model_trial = kruskal_per_model_trial_step(trial_model)
    kr_model_session = kruskal_per_model_session_step(session_model)
    models = sorted(str(x) for x in id_map["model"].unique())
    return {
        "id_map": id_map,
        "levels_model": levels,
        "animal_frame_share": med,
        "kruskal_level": kr_level,
        "trial_step_delta": trial_d,
        "kruskal_trial_step": kr_trial,
        "session_step_delta": session_d,
        "kruskal_session_step": kr_session,
        "kruskal_per_model_level": kr_model_level,
        "kruskal_per_model_trial_step": kr_model_trial,
        "kruskal_per_model_session_step": kr_model_session,
        "model_labels": pd.DataFrame({"model": models, "label": [short_model_label(m) for m in models]}),
        "cluster_id": cluster_id,
    }
