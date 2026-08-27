"""Occupancy (move|still | syllable) joined to DA lollipop hits.

Occupancy grain: animal × phase × condition.
DA grain: animal × phase × condition-step (same model).
Join labels a DA hit with occupancy in the step's **destination** condition
(`right`). Still not the same contrast as DA. Not a tx test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.simpler_first_da import apply_bh_grouped
from nor_object_mi.simpler_first_protocol_prologue import PHASES, ttest_one_sample

MIN_N = 8
STEPS = ("no_obj->identical", "identical->novel", "no_obj->novel")
STEP_DEST = {
    "no_obj->identical": "identical_obj",
    "identical->novel": "novel_obj",
    "no_obj->novel": "novel_obj",
}


def occupancy_tests(occ: pd.DataFrame, *, min_n: int = MIN_N) -> pd.DataFrame:
    """One-sample t of enrich_move vs 0.

    BH family: phase (× model × condition when those columns exist).
    """
    rows: list[dict[str, object]] = []
    if occ.empty:
        return pd.DataFrame()
    has_model = "model" in occ.columns
    has_cond = "condition_layer" in occ.columns
    group_keys = ["phase_layer"]
    if has_model:
        group_keys = ["model", *group_keys]
    if has_cond:
        group_keys = [*group_keys, "condition_layer"]
    enrich_col = "enrich_move" if "enrich_move" in occ.columns else "enrich_move"
    for key, g in occ.groupby(group_keys, sort=False):
        key_t = key if isinstance(key, tuple) else (key,)
        i = 0
        model = None
        if has_model:
            model = key_t[i]
            i += 1
        phase = key_t[i]
        i += 1
        cond = key_t[i] if has_cond else None
        for sid, gs in g.groupby("raw_syllable_id", sort=False):
            rec = ttest_one_sample(gs[enrich_col].to_numpy())
            n = int(rec["n"])
            if n < min_n:
                continue
            row: dict[str, object] = {
                "phase_layer": str(phase),
                "raw_syllable_id": int(sid),
                "n": n,
                "mean_enrich_move": float(rec["mean_delta"]),
                "median_enrich_move": float(rec["median_delta"]),
                "p": float(rec["p"]),
                "locomotor_class": "ns",
                "test": rec["test"],
            }
            if has_model:
                row["model"] = str(model)
            if has_cond:
                row["condition_layer"] = str(cond)
            rows.append(row)
    tests = pd.DataFrame(rows)
    if tests.empty:
        return tests
    family = ["phase_layer"]
    if has_model:
        family = ["model", *family]
    if has_cond:
        family = [*family, "condition_layer"]
    tests = apply_bh_grouped(tests, family, p_col="p", q_col="q_bh")
    tests["hit_fdr05"] = tests["hit_fdr05"]
    cls = np.full(len(tests), "ns", dtype=object)
    hit = tests["hit_fdr05"].to_numpy(dtype=bool)
    pos = tests["mean_enrich_move"].to_numpy(dtype=np.float64) > 0
    cls[hit & pos] = "move"
    cls[hit & ~pos] = "still"
    tests["locomotor_class"] = cls
    tests["phase_layer"] = pd.Categorical(tests["phase_layer"], categories=list(PHASES), ordered=True)
    sort_cols = (["model"] if has_model else []) + ["phase_layer"]
    if has_cond:
        sort_cols.append("condition_layer")
    sort_cols.append("raw_syllable_id")
    return tests.sort_values(sort_cols).reset_index(drop=True)


def _dest_condition(da: pd.DataFrame) -> pd.Series:
    if "right" in da.columns:
        return da["right"].astype(str)
    return da["step"].astype(str).map(STEP_DEST)


def join_da_occupancy(
    da: pd.DataFrame,
    occ_tests: pd.DataFrame,
    *,
    model: str,
) -> pd.DataFrame:
    """Join DA rows to occupancy class at the same phase × id × dest condition."""
    d = da[da["model"] == model].copy()
    if d.empty or occ_tests.empty:
        return pd.DataFrame()
    d["raw_syllable_id"] = pd.to_numeric(d["raw_syllable_id"], errors="coerce").astype("Int64")
    d["hit_da_fdr05"] = d["hit_fdr05"]
    if d["hit_da_fdr05"].dtype != bool:
        d["hit_da_fdr05"] = d["hit_da_fdr05"].astype(str).str.lower().isin(("true", "1"))
    occ = occ_tests.rename(
        columns={
            "p": "occupancy_p",
            "q_bh": "occupancy_q_bh",
            "hit_fdr05": "hit_occupancy_fdr05",
        }
    )
    keep_occ = [
        "phase_layer",
        "raw_syllable_id",
        "n",
        "mean_enrich_move",
        "median_enrich_move",
        "occupancy_p",
        "occupancy_q_bh",
        "hit_occupancy_fdr05",
        "locomotor_class",
    ]
    on = ["phase_layer", "raw_syllable_id"]
    if "condition_layer" in occ.columns:
        d["condition_layer"] = _dest_condition(d)
        keep_occ = ["condition_layer", *keep_occ]
        on = ["phase_layer", "condition_layer", "raw_syllable_id"]
    out = d.merge(occ[keep_occ], on=on, how="left")
    out["locomotor_class"] = out["locomotor_class"].fillna("no_occ")
    out["on_lollipop"] = out["hit_da_fdr05"]
    out["da_and_move"] = out["hit_da_fdr05"] & (out["locomotor_class"] == "move")
    out["da_and_still"] = out["hit_da_fdr05"] & (out["locomotor_class"] == "still")
    out["da_and_move"] = out["da_and_move"]
    out["da_and_still"] = out["da_and_still"]
    return out


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def _is_da_hit(df: pd.DataFrame) -> pd.Series:
    if "hit_da_fdr05" in df.columns:
        return _as_bool(df["hit_da_fdr05"])
    if "on_lollipop" in df.columns:
        return _as_bool(df["on_lollipop"])
    return _as_bool(df["hit_fdr05"])


def signed_overlap_summary(joined: pd.DataFrame) -> pd.DataFrame:
    """DA FDR hits split by sign of median Δp, then dest occupancy class.

    Gain = median_delta_p > 0 (higher share on the destination condition).
    Loss = median_delta_p < 0. Occupancy class is dest-matched, not the DA test.
    """
    rows: list[dict[str, object]] = []
    if joined.empty:
        return pd.DataFrame()
    has_model = "model" in joined.columns
    model_vals: list[object] = list(joined["model"].astype(str).unique()) if has_model else [None]
    delta = pd.to_numeric(joined["median_delta_p"], errors="coerce")
    hit = _is_da_hit(joined)
    for model in model_vals:
        in_m = pd.Series(True, index=joined.index) if model is None else joined["model"].astype(str) == str(model)
        for phase in PHASES:
            for step in STEPS:
                sel = in_m & (joined["phase_layer"] == phase) & (joined["step"] == step) & hit
                g = joined.loc[sel]
                d = delta.loc[sel]
                gain = d > 0
                loss = d < 0
                cls = g["locomotor_class"].astype(str)
                n_gain = int(gain.sum())
                n_loss = int(loss.sum())
                n_move_gain = int((gain & (cls == "move")).sum())
                n_still_gain = int((gain & (cls == "still")).sum())
                n_move_loss = int((loss & (cls == "move")).sum())
                n_still_loss = int((loss & (cls == "still")).sum())
                rec: dict[str, object] = {
                    "phase_layer": phase,
                    "step": step,
                    "n_da_fdr": int(sel.sum()),
                    "n_gain": n_gain,
                    "n_loss": n_loss,
                    "n_move_gain": n_move_gain,
                    "n_still_gain": n_still_gain,
                    "n_move_loss": n_move_loss,
                    "n_still_loss": n_still_loss,
                    "frac_gain_move": (n_move_gain / n_gain) if n_gain else float("nan"),
                    "frac_loss_move": (n_move_loss / n_loss) if n_loss else float("nan"),
                }
                if model is not None:
                    rec["model"] = str(model)
                rows.append(rec)
    return pd.DataFrame(rows)


def consensus_signed_across_models(summary: pd.DataFrame) -> pd.DataFrame:
    """Median frac-move among DA gainers vs losers, across models."""
    if summary.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for (phase, step), g in summary.groupby(["phase_layer", "step"], sort=False):
        n_models = int(g["model"].nunique()) if "model" in g.columns else int(len(g))
        n_gain = pd.to_numeric(g["n_gain"], errors="coerce")
        n_loss = pd.to_numeric(g["n_loss"], errors="coerce")
        fg = pd.to_numeric(g.loc[n_gain > 0, "frac_gain_move"], errors="coerce")
        fl = pd.to_numeric(g.loc[n_loss > 0, "frac_loss_move"], errors="coerce")
        rows.append(
            {
                "phase_layer": str(phase),
                "step": str(step),
                "n_models": n_models,
                "n_models_with_gain": int((n_gain > 0).sum()),
                "n_models_with_loss": int((n_loss > 0).sum()),
                "median_n_gain": float(np.nanmedian(n_gain.to_numpy(dtype=np.float64))),
                "median_n_loss": float(np.nanmedian(n_loss.to_numpy(dtype=np.float64))),
                "median_frac_gain_move": float(np.nanmedian(fg.to_numpy(dtype=np.float64)))
                if len(fg)
                else float("nan"),
                "median_frac_loss_move": float(np.nanmedian(fl.to_numpy(dtype=np.float64)))
                if len(fl)
                else float("nan"),
            }
        )
    out = pd.DataFrame(rows)
    out["phase_layer"] = pd.Categorical(out["phase_layer"], categories=list(PHASES), ordered=True)
    return out.sort_values(["phase_layer", "step"]).reset_index(drop=True)


def set_overlap_summary(joined: pd.DataFrame) -> pd.DataFrame:
    """Per phase × DA step (× model if present): lollipop ids that are move- vs still-enriched."""
    rows: list[dict[str, object]] = []
    if joined.empty:
        return pd.DataFrame()
    has_model = "model" in joined.columns
    model_vals: list[object] = list(joined["model"].astype(str).unique()) if has_model else [None]
    for model in model_vals:
        block = joined if model is None else joined[joined["model"].astype(str) == str(model)]
        for phase in PHASES:
            occ = block[block["phase_layer"] == phase]
            for step in STEPS:
                g = occ[(occ["step"] == step) & _is_da_hit(occ)]
                da_ids = set(g["raw_syllable_id"].dropna().astype(int))
                both_m = set(
                    g.loc[g["locomotor_class"] == "move", "raw_syllable_id"].dropna().astype(int)
                )
                both_s = set(
                    g.loc[g["locomotor_class"] == "still", "raw_syllable_id"].dropna().astype(int)
                )
                step_all = occ[occ["step"] == step]
                move_ids = set(
                    step_all.loc[step_all["locomotor_class"] == "move", "raw_syllable_id"]
                    .dropna()
                    .astype(int)
                )
                still_ids = set(
                    step_all.loc[step_all["locomotor_class"] == "still", "raw_syllable_id"]
                    .dropna()
                    .astype(int)
                )
                n_da = len(da_ids)
                rec: dict[str, object] = {
                    "phase_layer": phase,
                    "step": step,
                    "n_da_fdr": n_da,
                    "n_occ_move": len(move_ids),
                    "n_occ_still": len(still_ids),
                    "n_da_and_move": len(both_m),
                    "n_da_and_still": len(both_s),
                    "n_da_and_move": len(both_m),
                    "n_da_and_still": len(both_s),
                    "frac_da_move": (len(both_m) / n_da) if n_da else float("nan"),
                    "frac_da_still": (len(both_s) / n_da) if n_da else float("nan"),
                    "da_move_ids": ",".join(str(i) for i in sorted(both_m)),
                    "da_still_ids": ",".join(str(i) for i in sorted(both_s)),
                }
                if model is not None:
                    rec["model"] = str(model)
                rows.append(rec)
    return pd.DataFrame(rows)


def consensus_across_models(summary: pd.DataFrame) -> pd.DataFrame:
    """Pattern consensus: DA-hit locomotor mix across models (ids are not portable)."""
    if summary.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for (phase, step), g in summary.groupby(["phase_layer", "step"], sort=False):
        n_models = int(g["model"].nunique()) if "model" in g.columns else int(len(g))
        da = pd.to_numeric(g["n_da_fdr"], errors="coerce")
        with_da = g.loc[da > 0]
        fm = pd.to_numeric(with_da["frac_da_move"], errors="coerce")
        fs = pd.to_numeric(with_da["frac_da_still"], errors="coerce")
        n_da = int((da > 0).sum())
        rows.append(
            {
                "phase_layer": str(phase),
                "step": str(step),
                "n_models": n_models,
                "n_models_with_da": n_da,
                "n_models": n_models,
                "n_models_with_da": n_da,
                "median_n_da_fdr": float(np.nanmedian(da.to_numpy(dtype=np.float64))),
                "median_frac_da_move": float(np.nanmedian(fm.to_numpy(dtype=np.float64)))
                if n_da
                else float("nan"),
                "median_frac_da_move": float(np.nanmedian(fm.to_numpy(dtype=np.float64)))
                if n_da
                else float("nan"),
                "q25_frac_da_move": float(np.nanpercentile(fm.to_numpy(dtype=np.float64), 25))
                if n_da
                else float("nan"),
                "q75_frac_da_move": float(np.nanpercentile(fm.to_numpy(dtype=np.float64), 75))
                if n_da
                else float("nan"),
                "median_frac_da_still": float(np.nanmedian(fs.to_numpy(dtype=np.float64)))
                if n_da
                else float("nan"),
                "n_models_move_majority": int((fm > 0.5).sum()) if n_da else 0,
                "n_models_move_majority": int((fm > 0.5).sum()) if n_da else 0,
            }
        )
    out = pd.DataFrame(rows)
    out["phase_layer"] = pd.Categorical(out["phase_layer"], categories=list(PHASES), ordered=True)
    out["n_models_move_majority"] = out["n_models_move_majority"]
    out["n_models"] = out["n_models"]
    out["n_models_with_da"] = out["n_models_with_da"]
    out["median_frac_da_move"] = out["median_frac_da_move"]
    return out.sort_values(["phase_layer", "step"]).reset_index(drop=True)


join_da_occupancy = join_da_occupancy
set_overlap_summary = set_overlap_summary
consensus_across_models = consensus_across_models
