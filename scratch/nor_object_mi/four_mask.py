"""Four bout-masks: still∩near, move∩near, move∩far, still∩far.

Near is gate A: bout-mean spot→nearest-target < 0.10 m (same as presence).
Locomotor is majority overlap with hysteresis move vs still (exclusive ends).
Grain: animal × phase × condition. Locked kpMS. Not per-syllable DA.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.simpler_first_da import apply_bh
from nor_object_mi.simpler_first_presence import CONDS, NEAR_R_M
from nor_object_mi.simpler_first_protocol_prologue import ttest_one_sample
from nor_object_mi.simpler_first_q1 import SEX_ORDER, anova_within_sex
from nor_object_mi.simpler_first_q2 import shannon_bits
from nor_object_mi.syll_ambulation_overlap import (
    bout_occupancy_on_raster,
    locomotor_raster,
)

MASKS = ("still_near", "move_near", "move_far", "still_far")
METRICS = ("frac_mask", "shannon_bits")
PHASE_PAIR = ("NOR_BL", "NOR_TX")


def locomotor_majority(n_move: np.ndarray, n_still: np.ndarray) -> np.ndarray:
    """'move' / 'still' / '' (tie or unlabeled)."""
    m = np.asarray(n_move, dtype=np.int64)
    s = np.asarray(n_still, dtype=np.int64)
    out = np.full(m.shape, "", dtype=object)
    out[m > s] = "move"
    out[s > m] = "still"
    return out


def near_flag(dist_m: np.ndarray, *, r_m: float = NEAR_R_M) -> np.ndarray:
    d = np.asarray(dist_m, dtype=np.float64)
    out = np.full(d.shape, "", dtype=object)
    ok = np.isfinite(d)
    out[ok & (d < float(r_m))] = "near"
    out[ok & (d >= float(r_m))] = "far"
    return out


def mask_name(loco: np.ndarray, near: np.ndarray) -> np.ndarray:
    out = np.full(loco.shape, "", dtype=object)
    for loc in ("move", "still"):
        for nz in ("near", "far"):
            out[(loco == loc) & (near == nz)] = f"{loc}_{nz}"
    return out


def session_rasters(
    move: pd.DataFrame,
    still: pd.DataFrame,
) -> dict[tuple[str, object], np.ndarray]:
    """Locomotor raster per animal × raw_session (all conditions)."""
    n_map: dict[tuple[str, object], int] = {}
    for df in (move, still):
        if df.empty:
            continue
        ends = pd.to_numeric(df["row_end_exclusive"], errors="coerce")
        tmp = df.assign(_end=ends)
        tmp["animal_id"] = tmp["animal_id"].astype(str)
        for (aid, sess), g in tmp.groupby(["animal_id", "raw_session"], sort=False):
            n = int(np.nanmax(g["_end"].to_numpy())) if g["_end"].notna().any() else 0
            key = (str(aid), sess)
            n_map[key] = max(n_map.get(key, 0), n)
    move = move.copy()
    still = still.copy()
    move["animal_id"] = move["animal_id"].astype(str)
    still["animal_id"] = still["animal_id"].astype(str)
    move_g = move.groupby(["animal_id", "raw_session"], sort=False)
    still_g = still.groupby(["animal_id", "raw_session"], sort=False)
    empty = move.iloc[0:0]
    rasters: dict[tuple[str, object], np.ndarray] = {}
    for (aid, sess), n in n_map.items():
        try:
            mv = move_g.get_group((aid, sess))
        except KeyError:
            mv = empty
        try:
            st = still_g.get_group((aid, sess))
        except KeyError:
            st = empty
        rasters[(str(aid), sess)] = locomotor_raster(mv, st, n_frames=max(n, 1))
    return rasters


def label_syllable_bouts(
    syll: pd.DataFrame,
    rasters: dict[tuple[str, object], np.ndarray],
    *,
    r_m: float = NEAR_R_M,
) -> pd.DataFrame:
    """Add n_move/n_still frames, locomotor majority, near/far, mask."""
    if syll.empty:
        return syll.copy()
    df = syll.copy().reset_index(drop=True)
    df["animal_id"] = df["animal_id"].astype(str)
    n_move = np.zeros(len(df), dtype=np.int32)
    n_still = np.zeros(len(df), dtype=np.int32)
    starts = pd.to_numeric(df["row_start"], errors="coerce").to_numpy()
    ends = pd.to_numeric(df["row_end_exclusive"], errors="coerce").to_numpy()
    for (aid, sess), g in df.groupby(["animal_id", "raw_session"], sort=False):
        rast = rasters.get((str(aid), sess))
        if rast is None:
            continue
        ii = g.index.to_numpy()
        ok = np.isfinite(starts[ii]) & np.isfinite(ends[ii])
        if not np.any(ok):
            continue
        use = ii[ok]
        nm, ns = bout_occupancy_on_raster(
            starts[use].astype(np.int64),
            ends[use].astype(np.int64),
            rast,
        )
        n_move[use] = nm
        n_still[use] = ns
    df["n_move_frames"] = n_move
    df["n_still_frames"] = n_still
    df["locomotor"] = locomotor_majority(n_move, n_still)
    dist = pd.to_numeric(df["bout_mean_dist_any_m"], errors="coerce").to_numpy()
    df["near_far"] = near_flag(dist, r_m=r_m)
    df["mask"] = mask_name(df["locomotor"].to_numpy(), df["near_far"].to_numpy())
    return df


def session_mask_table(labeled: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × phase × condition × mask."""
    if labeled.empty:
        return pd.DataFrame()
    df = labeled.copy()
    df["animal_id"] = df["animal_id"].astype(str)
    frames = pd.to_numeric(df["bout_frames"], errors="coerce").fillna(0.0)
    df["_frames"] = frames
    sess_n = df.groupby(
        ["animal_id", "phase_layer", "condition_layer"],
        sort=False,
    )["_frames"].sum()
    rows: list[dict[str, object]] = []
    keys = ["animal_id", "phase_layer", "condition_layer", "mask"]
    meta_cols = [c for c in ("sex", "tx", "model") if c in df.columns]
    for key, g in df.groupby(keys, sort=False):
        aid, phase, cond, mask = key
        if mask not in MASKS:
            continue
        n_mask = float(g["_frames"].sum())
        n_sess = float(sess_n.loc[(aid, phase, cond)])
        counts = g.groupby("raw_syllable_id")["_frames"].sum()
        tot = float(counts.sum())
        p = (counts / tot).to_numpy(dtype=np.float64) if tot > 0 else np.array([])
        rec: dict[str, object] = {
            "animal_id": str(aid),
            "phase_layer": phase,
            "condition_layer": cond,
            "mask": mask,
            "n_mask_frames": n_mask,
            "n_session_frames": n_sess,
            "frac_mask": (n_mask / n_sess) if n_sess > 0 else float("nan"),
            "shannon_bits": shannon_bits(p) if tot > 0 else float("nan"),
            "richness": int((counts > 0).sum()),
        }
        for c in meta_cols:
            rec[c] = g[c].iloc[0]
        rows.append(rec)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # ensure every session has all four masks (zero time if absent)
    idx_cols = ["animal_id", "phase_layer", "condition_layer"]
    sessions = df.groupby(idx_cols, sort=False).agg(
        **{c: (c, "first") for c in meta_cols},
        n_session_frames=("_frames", "sum"),
    ).reset_index()
    grid = sessions.merge(pd.DataFrame({"mask": list(MASKS)}), how="cross")
    out = grid.merge(out, on=[*idx_cols, "mask"], how="left", suffixes=("", "_y"))
    for c in meta_cols:
        if f"{c}_y" in out.columns:
            out[c] = out[c].fillna(out[f"{c}_y"])
            out = out.drop(columns=[f"{c}_y"])
    if "n_session_frames_y" in out.columns:
        out["n_session_frames"] = out["n_session_frames"].fillna(out["n_session_frames_y"])
        out = out.drop(columns=["n_session_frames_y"])
    out["n_mask_frames"] = pd.to_numeric(out["n_mask_frames"], errors="coerce").fillna(0.0)
    n_sess = pd.to_numeric(out["n_session_frames"], errors="coerce")
    miss = out["frac_mask"].isna()
    out.loc[miss, "frac_mask"] = np.where(
        n_sess[miss].to_numpy() > 0,
        out.loc[miss, "n_mask_frames"].to_numpy() / n_sess[miss].to_numpy(),
        np.nan,
    )
    return out


def paired_tx_minus_bl(sessions: pd.DataFrame) -> pd.DataFrame:
    """TX − BL for each animal × condition × mask × metric."""
    bl = sessions[sessions["phase_layer"] == "NOR_BL"]
    tx = sessions[sessions["phase_layer"] == "NOR_TX"]
    keys = ["animal_id", "condition_layer", "mask"]
    cols = keys + ["sex", "tx", "frac_mask", "shannon_bits"]
    a = bl[cols].rename(columns={"frac_mask": "frac_mask_bl", "shannon_bits": "shannon_bits_bl"})
    b = tx[cols].rename(columns={"frac_mask": "frac_mask_tx", "shannon_bits": "shannon_bits_tx"})
    m = a.merge(b, on=keys, how="inner", suffixes=("", "_txmeta"))
    if "sex_txmeta" in m.columns:
        m["sex"] = m["sex"].fillna(m["sex_txmeta"])
        m = m.drop(columns=["sex_txmeta"])
    if "tx_txmeta" in m.columns:
        m["tx"] = m["tx"].fillna(m["tx_txmeta"])
        m = m.drop(columns=["tx_txmeta"])
    m["delta_frac_mask"] = m["frac_mask_tx"] - m["frac_mask_bl"]
    m["delta_shannon_bits"] = m["shannon_bits_tx"] - m["shannon_bits_bl"]
    return m


def hunt_tests(paired: pd.DataFrame) -> pd.DataFrame:
    """Tx hunt: Welch ANOVA of TX−BL on novel_obj.

    BH family (primary): within sex, 4 masks × 2 Δ metrics.
    Gates (uncorrected veto): same ANOVA on identical_obj and no_obj; BL level by tx.
    Companion: one-sample t of Δ vs 0 (txs pooled).
    """
    rows: list[dict[str, object]] = []
    if paired.empty:
        return pd.DataFrame()

    def _anova(sub: pd.DataFrame, *, metric: str, contrast: str, condition: str, family: str) -> None:
        if sub.empty or "mask" not in sub.columns:
            return
        tab = sub[["animal_id", "sex", "tx", metric]].copy()
        an = anova_within_sex(tab, metric=metric)
        mask = str(sub["mask"].iloc[0])
        for rec in an.to_dict("records"):
            rows.append(
                {
                    "sex": rec["sex"],
                    "p": rec["p"],
                    "stat": rec["stat"],
                    "n": rec["n"],
                    "test": rec["test"],
                    "mask": mask,
                    "condition_layer": condition,
                    "contrast": contrast,
                    "metric": metric,
                    "family": family,
                }
            )

    for mask in MASKS:
        g = paired[paired["mask"] == mask]
        for cond in CONDS:
            gc = g[g["condition_layer"] == cond]
            if gc.empty:
                continue
            fam_t = "protocol" if cond == "novel_obj" else "gate"
            fam_a = "primary" if cond == "novel_obj" else "gate"
            for metric in ("delta_frac_mask", "delta_shannon_bits"):
                for sex in SEX_ORDER:
                    gs = gc[gc["sex"] == sex]
                    rec0 = ttest_one_sample(gs[metric].to_numpy())
                    rows.append(
                        {
                            "sex": sex,
                            "p": rec0["p"],
                            "stat": rec0["stat"],
                            "n": rec0["n"],
                            "test": rec0["test"],
                            "mask": mask,
                            "condition_layer": cond,
                            "contrast": "tx_minus_bl",
                            "metric": metric,
                            "family": fam_t,
                        }
                    )
                _anova(gc, metric=metric, contrast="tx_minus_bl_by_tx", condition=cond, family=fam_a)
        gn = g[g["condition_layer"] == "novel_obj"]
        if not gn.empty:
            bl_level = gn.copy()
            bl_level["frac_mask"] = bl_level["frac_mask_bl"]
            bl_level["shannon_bits"] = bl_level["shannon_bits_bl"]
            _anova(bl_level, metric="frac_mask", contrast="bl_level_by_tx", condition="novel_obj", family="gate")
            _anova(bl_level, metric="shannon_bits", contrast="bl_level_by_tx", condition="novel_obj", family="gate")

    tests = pd.DataFrame(rows)
    if tests.empty:
        return tests
    tests["hit_p05"] = pd.to_numeric(tests["p"], errors="coerce") < 0.05
    tests["q_bh"] = np.nan
    tests["hit_fdr05"] = False
    tests = tests.reset_index(drop=True)
    prim = tests["family"].astype(str) == "primary"
    for _sex, g in tests.loc[prim].groupby("sex", sort=False):
        bh = apply_bh(g, p_col="p", q_col="q_bh")
        tests.loc[g.index, "q_bh"] = bh["q_bh"].to_numpy()
        tests.loc[g.index, "hit_fdr05"] = bh["hit_fdr05"].to_numpy()
        tests.loc[g.index, "hit_p05"] = bh["hit_p05"].to_numpy()
    return tests


def gate_hits(tests: pd.DataFrame) -> pd.DataFrame:
    """Novel TX−BL ANOVA hit that misses identical, no_obj, and BL-level ANOVA."""
    if tests.empty:
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    an = tests[tests["test"] == "welch_anova"]
    for sex in SEX_ORDER:
        for mask in MASKS:
            for metric in ("delta_frac_mask", "delta_shannon_bits"):
                prim = an[
                    (an["sex"] == sex)
                    & (an["mask"] == mask)
                    & (an["metric"] == metric)
                    & (an["condition_layer"] == "novel_obj")
                    & (an["contrast"] == "tx_minus_bl_by_tx")
                ]
                if len(prim) != 1:
                    continue
                p_nov = float(prim["p"].iloc[0])
                q_nov = float(prim["q_bh"].iloc[0]) if "q_bh" in prim.columns else float("nan")
                hit_nov = bool(prim["hit_fdr05"].iloc[0]) if "hit_fdr05" in prim.columns else (p_nov < 0.05)

                def _p(cond: str, contrast: str, met: str) -> float:
                    s = an[
                        (an["sex"] == sex)
                        & (an["mask"] == mask)
                        & (an["metric"] == met)
                        & (an["condition_layer"] == cond)
                        & (an["contrast"] == contrast)
                    ]
                    if len(s) != 1:
                        return float("nan")
                    return float(s["p"].iloc[0])

                bl_met = "frac_mask" if metric == "delta_frac_mask" else "shannon_bits"
                p_id = _p("identical_obj", "tx_minus_bl_by_tx", metric)
                p_no = _p("no_obj", "tx_minus_bl_by_tx", metric)
                p_bl = _p("novel_obj", "bl_level_by_tx", bl_met)
                miss_gates = (not (np.isfinite(p_id) and p_id < 0.05)) and (
                    not (np.isfinite(p_no) and p_no < 0.05)
                ) and (not (np.isfinite(p_bl) and p_bl < 0.05))
                rows.append(
                    {
                        "sex": sex,
                        "mask": mask,
                        "metric": metric,
                        "p_novel_txbl_anova": p_nov,
                        "q_novel_txbl_anova": q_nov,
                        "hit_novel_fdr": hit_nov,
                        "p_identical_txbl_anova": p_id,
                        "p_no_obj_txbl_anova": p_no,
                        "p_bl_level_anova": p_bl,
                        "gates_miss": miss_gates,
                        "tx_specific": bool(hit_nov and miss_gates),
                    }
                )
    return pd.DataFrame(rows)
