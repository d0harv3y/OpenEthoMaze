"""Per-object 0.10 m proximity windows (object-prox) and NOR discrimination ratio (DR).

Grain: animal × phase × novel_obj (full session; spot bout-means).

Each object's prox window is gated independently:
    near_fam ⇔ bout_mean_dist_fam_m < r
    near_nvl ⇔ bout_mean_dist_nvl_m < r
    near_both ⇔ both

Windows of radius r do not overlap in the arena iff object–object distance ≥ 2r.
Dual membership of a bout-mean still flags overlap (or a bout that straddles).

DR is a scalar preference, not a composition:
    DR = (n_nvl − n_fam) / (n_nvl + n_fam)
Inclusive counts a dual-gated bout in both windows (pulls DR toward 0).
Exclusive drops dual-gated frames from both (classic disjoint-zone DR).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_presence import wilcoxon_paired  # noqa: E402
from nor_object_mi.simpler_first_q1 import LOCKED, SEX_ORDER, kruskal_within_sex  # noqa: E402

NEAR_R_M = 0.10
CONDITION = "novel_obj"
PHASES: tuple[tuple[str, str], ...] = (
    ("NOR_BL", "condition_ladder_NOR_BL"),
    ("NOR_TX", "condition_ladder"),
    ("NOR_REC3hr", "condition_ladder_NOR_REC3hr"),
    ("NOR_REC11hr", "condition_ladder_NOR_REC11hr"),
)
GRAIN = f"animal × {{phase}} × {CONDITION} × " f"spot_bout_mean_fam|nvl < {NEAR_R_M:g} m (raw)"


def discrimination_ratio(n_nvl: float, n_fam: float) -> float:
    """(T_nvl − T_fam) / (T_nvl + T_fam). NaN when the animal never entered either prox window."""
    tot = float(n_nvl) + float(n_fam)
    if tot <= 0 or not math.isfinite(tot):
        return float("nan")
    return (float(n_nvl) - float(n_fam)) / tot


def tag_object_prox(bouts: pd.DataFrame, *, r_m: float = NEAR_R_M) -> pd.DataFrame:
    """Add near_fam / near_nvl / near_both on a bout table copy."""
    out = bouts.copy()
    d_fam = out["bout_mean_dist_fam_m"].to_numpy(dtype=np.float64)
    d_nvl = out["bout_mean_dist_nvl_m"].to_numpy(dtype=np.float64)
    r = float(r_m)
    near_fam = np.isfinite(d_fam) & (d_fam < r)
    near_nvl = np.isfinite(d_nvl) & (d_nvl < r)
    out["near_fam"] = near_fam
    out["near_nvl"] = near_nvl
    out["near_both"] = near_fam & near_nvl
    return out


def animal_object_prox_metrics(
    bouts: pd.DataFrame,
    *,
    phase_layer: str,
    r_m: float = NEAR_R_M,
    condition_layer: str = CONDITION,
) -> pd.DataFrame:
    """One row per animal: per-object occupancy, overlap, inclusive/exclusive DR."""
    need = (
        "animal_id",
        "sex",
        "tx",
        "phase_layer",
        "condition_layer",
        "bout_frames",
        "bout_mean_dist_fam_m",
        "bout_mean_dist_nvl_m",
    )
    missing = [c for c in need if c not in bouts.columns]
    if missing:
        raise ValueError(f"bout table missing columns: {missing}")

    sub = bouts[(bouts["phase_layer"] == phase_layer) & (bouts["condition_layer"] == condition_layer)].copy()
    if sub.empty:
        return sub.iloc[0:0].copy()
    sub["animal_id"] = sub["animal_id"].astype(str)
    tagged = tag_object_prox(sub, r_m=r_m)
    w = tagged["bout_frames"].to_numpy(dtype=np.float64)
    tagged = tagged.assign(bout_frames=np.where(np.isfinite(w) & (w > 0), w, 0.0))

    rows: list[dict[str, object]] = []
    for aid, g in tagged.groupby("animal_id", sort=True):
        ww = g["bout_frames"].to_numpy(dtype=np.float64)
        n_sess = float(np.nansum(ww))
        n_fam = float(np.nansum(ww[g["near_fam"].to_numpy()]))
        n_nvl = float(np.nansum(ww[g["near_nvl"].to_numpy()]))
        n_both = float(np.nansum(ww[g["near_both"].to_numpy()]))
        n_fam_only = n_fam - n_both
        n_nvl_only = n_nvl - n_both
        rows.append(
            {
                "animal_id": str(aid),
                "sex": str(g["sex"].iloc[0]),
                "tx": str(g["tx"].iloc[0]),
                "phase_layer": phase_layer,
                "n_sess_frames": int(n_sess),
                "n_fam_frames": int(n_fam),
                "n_nvl_frames": int(n_nvl),
                "n_both_frames": int(n_both),
                "n_fam_only_frames": int(n_fam_only),
                "n_nvl_only_frames": int(n_nvl_only),
                "frac_near_fam": n_fam / n_sess if n_sess > 0 else float("nan"),
                "frac_near_nvl": n_nvl / n_sess if n_sess > 0 else float("nan"),
                "frac_both": n_both / n_sess if n_sess > 0 else float("nan"),
                "dr_inclusive": discrimination_ratio(n_nvl, n_fam),
                "dr_exclusive": discrimination_ratio(n_nvl_only, n_fam_only),
            }
        )
    return pd.DataFrame(rows)


def _overlap_audit(animals: pd.DataFrame) -> dict[str, object]:
    n = int(len(animals))
    n_sess = float(animals["n_sess_frames"].sum()) if n else 0.0
    n_both = float(animals["n_both_frames"].sum()) if n else 0.0
    n_hit = int((animals["n_both_frames"] > 0).sum()) if n else 0
    return {
        "n_animals": n,
        "n_animals_with_overlap": n_hit,
        "frac_animals_with_overlap": float(n_hit / n) if n else float("nan"),
        "n_both_frames": int(n_both),
        "frac_both_pooled": float(n_both / n_sess) if n_sess > 0 else float("nan"),
        "median_frac_both": (float(animals["frac_both"].median()) if n else float("nan")),
        "max_frac_both": float(animals["frac_both"].max()) if n else float("nan"),
    }


def _test_rows(
    animals: pd.DataFrame,
    *,
    phase: str,
    r_m: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    grain = GRAIN.format(phase=phase)

    def _wx(metric: str) -> None:
        d = pd.to_numeric(animals[metric], errors="coerce").to_numpy(dtype=np.float64)
        res = wilcoxon_paired(d)
        rows.append(
            {
                "phase_layer": phase,
                "question": "object_prox_dr",
                "metric": metric,
                "grain": grain,
                "r_m": r_m,
                "sex": "all",
                "test": res["test"],
                "stat": res["stat"],
                "p": res["p"],
                "n": res["n"],
                "median_delta": res["median_delta"],
                "frac_gt0": res["frac_gt0"],
                "hit_p05": bool(pd.notna(res["p"]) and float(res["p"]) < 0.05),
            }
        )

    def _kruskal(metric: str) -> None:
        tests = kruskal_within_sex(animals, metric=metric)
        for _, r in tests.iterrows():
            rows.append(
                {
                    "phase_layer": phase,
                    "question": "object_prox_dr_tx",
                    "metric": metric,
                    "grain": grain,
                    "r_m": r_m,
                    "sex": r["sex"],
                    "test": r["test"],
                    "stat": r["stat"],
                    "p": r["p"],
                    "n": r["n"],
                    "median_delta": "",
                    "frac_gt0": "",
                    "hit_p05": bool(pd.notna(r["p"]) and float(r["p"]) < 0.05),
                    "median_noSD": r["median_noSD"],
                    "median_GHSD": r["median_GHSD"],
                    "median_RBSD": r["median_RBSD"],
                }
            )

    # Wilcoxon vs 0 is a preference claim — DR only. Occupancy vs 0 is almost
    # always true and is not discrimination. Skip frac_both (overlap audit).
    for metric in ("dr_exclusive", "dr_inclusive"):
        _wx(metric)
        _kruskal(metric)
    for metric in ("frac_near_fam", "frac_near_nvl"):
        _kruskal(metric)
    return rows


def _spacing_audit(
    bouts: pd.DataFrame,
    *,
    phase_layer: str,
    condition_layer: str,
    r_m: float = NEAR_R_M,
) -> dict[str, object]:
    """Triangle inequality: d_fam + d_nvl ≥ object–object distance.

    If every bout has d_fam + d_nvl ≥ 2r, the r-windows cannot overlap.
    """
    sub = bouts[(bouts["phase_layer"] == phase_layer) & (bouts["condition_layer"] == condition_layer)]
    s = pd.to_numeric(sub["bout_mean_dist_fam_m"], errors="coerce") + pd.to_numeric(sub["bout_mean_dist_nvl_m"], errors="coerce")
    s = s[np.isfinite(s.to_numpy(dtype=np.float64))]
    if s.empty:
        return {
            "n_bouts_spacing": 0,
            "min_d_fam_plus_d_nvl": float("nan"),
            "n_bouts_sum_lt_2r": 0,
        }
    r2 = 2.0 * float(r_m)
    return {
        "n_bouts_spacing": int(len(s)),
        "min_d_fam_plus_d_nvl": float(s.min()),
        "n_bouts_sum_lt_2r": int((s < r2).sum()),
    }


def run_phase(
    bout_csv: Path,
    phase: str,
    *,
    r_m: float = NEAR_R_M,
) -> tuple[pd.DataFrame, list[dict[str, object]], dict[str, object]]:
    bouts = pd.read_csv(bout_csv)
    animals = animal_object_prox_metrics(bouts, phase_layer=phase, r_m=r_m)
    audit = _overlap_audit(animals)
    spacing = _spacing_audit(bouts, phase_layer=phase, condition_layer=CONDITION, r_m=r_m)
    tests = _test_rows(animals, phase=phase, r_m=r_m)
    wx_excl = next(r for r in tests if r["metric"] == "dr_exclusive" and r["sex"] == "all" and r["test"] == "wilcoxon_signed_rank")
    k_excl = [r for r in tests if r["metric"] == "dr_exclusive" and r["test"] == "kruskal"]
    summary = {
        "status": "ok",
        "phase_layer": phase,
        "grain": GRAIN.format(phase=phase),
        "r_m": r_m,
        "median_dr_exclusive": (float(animals["dr_exclusive"].median()) if len(animals) else float("nan")),
        "median_dr_inclusive": (float(animals["dr_inclusive"].median()) if len(animals) else float("nan")),
        "wilcoxon_dr_exclusive_p": wx_excl["p"],
        "wilcoxon_dr_exclusive_hit": wx_excl["hit_p05"],
        "kruskal_dr_exclusive_hit_sexes": [str(r["sex"]) for r in k_excl if r["hit_p05"]],
        **audit,
        **spacing,
    }
    return animals, tests, summary


METRIC_COLS = (
    "dr_exclusive",
    "dr_inclusive",
    "frac_near_fam",
    "frac_near_nvl",
    "frac_both",
)
AGREE_METRICS = ("dr_exclusive", "dr_inclusive")


def animal_median_across_models(animals: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × phase: median occupancy/DR across models."""
    keys = ["animal_id", "sex", "tx", "phase_layer"]
    out = animals.groupby(keys, as_index=False)[list(METRIC_COLS)].median()
    n_mod = animals.groupby(keys)["model"].nunique()
    if int(n_mod.min()) != int(n_mod.max()):
        raise AssertionError(f"uneven model coverage per animal: {n_mod.min()}–{n_mod.max()}")
    out["n_models"] = int(n_mod.min())
    return out


def _mad(values: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan")
    med = float(np.median(v))
    return float(np.median(np.abs(v - med)))


def _iqr(values: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size < 2:
        return float("nan")
    q75, q25 = np.percentile(v, [75.0, 25.0])
    return float(q75 - q25)


def across_model_dispersion(animals: pd.DataFrame) -> pd.DataFrame:
    """Per-animal salt: IQR/MAD of each metric across kpMS models.

    One row = animal × phase × metric. ``iqr`` / ``mad`` are the primary salt
    columns; ``sd`` / ``var`` are companions. Occupancy and DR magnitudes are
    commensurate across models (same formula; ids never pooled).
    """
    need = {"animal_id", "sex", "tx", "phase_layer", "model", *METRIC_COLS}
    missing = need - set(animals.columns)
    if missing:
        raise KeyError(f"across_model_dispersion missing columns: {sorted(missing)}")
    keys = ["animal_id", "sex", "tx", "phase_layer"]
    rows: list[dict[str, object]] = []
    for key_vals, g in animals.groupby(keys, sort=False):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        n_models = int(g["model"].nunique())
        for metric in METRIC_COLS:
            v = g[metric].to_numpy(dtype=np.float64)
            v = v[np.isfinite(v)]
            med = float(np.median(v)) if v.size else float("nan")
            iqr = _iqr(v)
            mad = _mad(v)
            if v.size >= 2:
                sd = float(np.std(v, ddof=1))
                var = float(np.var(v, ddof=1))
            else:
                sd = float("nan")
                var = float("nan")
            abs_med = abs(med)
            rel = float(iqr / abs_med) if np.isfinite(iqr) and abs_med > 1e-12 else float("nan")
            rows.append(
                {
                    **key_map,
                    "metric": metric,
                    "n_models": n_models,
                    "n_finite": int(v.size),
                    "median": med,
                    "mean": float(np.mean(v)) if v.size else float("nan"),
                    "iqr": iqr,
                    "mad": mad,
                    "sd": sd,
                    "var": var,
                    "min": float(np.min(v)) if v.size else float("nan"),
                    "max": float(np.max(v)) if v.size else float("nan"),
                    "iqr_over_abs_median": rel,
                    "magnitude_commensurate_across_models": True,
                    "salt_role": "primary",
                }
            )
    return pd.DataFrame(rows)


def across_model_dispersion_summary(disp: pd.DataFrame) -> pd.DataFrame:
    """Cohort salt: median of per-animal IQR/MAD within phase × metric."""
    if disp.empty:
        return disp.copy()
    rows: list[dict[str, object]] = []
    for key_vals, g in disp.groupby(["phase_layer", "metric"], sort=True):
        key_map = dict(
            zip(("phase_layer", "metric"), key_vals if isinstance(key_vals, tuple) else (key_vals,))
        )
        rows.append(
            {
                **key_map,
                "n_animals": int(len(g)),
                "median_of_median": float(g["median"].median()),
                "median_of_iqr": float(g["iqr"].median()),
                "median_of_mad": float(g["mad"].median()),
                "median_of_sd": float(g["sd"].median()),
                "median_of_iqr_over_abs_median": float(g["iqr_over_abs_median"].median()),
                "magnitude_commensurate_across_models": True,
                "salt_role": "primary",
            }
        )
    return pd.DataFrame(rows)


def consensus_tests(med: pd.DataFrame) -> pd.DataFrame:
    """Wilcoxon vs 0 and Kruskal-by-tx on animal-level median-across-models DR."""
    rows: list[dict[str, object]] = []
    n_models = int(med["n_models"].iloc[0]) if len(med) else 0
    for phase, g in med.groupby("phase_layer", sort=True):
        for m in AGREE_METRICS:
            rec = wilcoxon_paired(g[m].to_numpy())
            rows.append(
                {
                    "phase_layer": phase,
                    "sex": "all",
                    "metric": m,
                    "question": "object_prox_dr",
                    **rec,
                    "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
                    "n_models": n_models,
                    "median_noSD": "",
                    "median_GHSD": "",
                    "median_RBSD": "",
                }
            )
            for sex in SEX_ORDER:
                rec_s = wilcoxon_paired(g.loc[g["sex"] == sex, m].to_numpy())
                rows.append(
                    {
                        "phase_layer": phase,
                        "sex": sex,
                        "metric": m,
                        "question": "object_prox_dr",
                        **rec_s,
                        "hit_p05": bool(np.isfinite(rec_s["p"]) and float(rec_s["p"]) < 0.05),
                        "n_models": n_models,
                        "median_noSD": "",
                        "median_GHSD": "",
                        "median_RBSD": "",
                    }
                )
            k = kruskal_within_sex(g, metric=m)
            for _, r in k.iterrows():
                p = r["p"]
                rows.append(
                    {
                        "phase_layer": phase,
                        "sex": r["sex"],
                        "metric": m,
                        "question": "object_prox_dr_tx",
                        "n": r["n"],
                        "median_delta": "",
                        "frac_gt0": "",
                        "stat": r["stat"],
                        "p": p,
                        "test": "kruskal",
                        "hit_p05": bool(pd.notna(p) and float(p) < 0.05),
                        "n_models": n_models,
                        "median_noSD": r["median_noSD"],
                        "median_GHSD": r["median_GHSD"],
                        "median_RBSD": r["median_RBSD"],
                    }
                )
        for m in ("frac_near_fam", "frac_near_nvl"):
            k = kruskal_within_sex(g, metric=m)
            for _, r in k.iterrows():
                p = r["p"]
                rows.append(
                    {
                        "phase_layer": phase,
                        "sex": r["sex"],
                        "metric": m,
                        "question": "object_prox_dr_tx",
                        "n": r["n"],
                        "median_delta": "",
                        "frac_gt0": "",
                        "stat": r["stat"],
                        "p": p,
                        "test": "kruskal",
                        "hit_p05": bool(pd.notna(p) and float(p) < 0.05),
                        "n_models": n_models,
                        "median_noSD": r["median_noSD"],
                        "median_GHSD": r["median_GHSD"],
                        "median_RBSD": r["median_RBSD"],
                    }
                )
    return pd.DataFrame(rows)


def agreement_table(tests: pd.DataFrame) -> pd.DataFrame:
    """Fraction of models with Wilcoxon hit (sex=all) on DR."""
    sub = tests[(tests["sex"] == "all") & (tests["test"] == "wilcoxon_signed_rank") & (tests["metric"].isin(AGREE_METRICS))].copy()
    if sub.empty:
        return pd.DataFrame()
    rows = []
    for (phase, metric), g in sub.groupby(["phase_layer", "metric"], sort=True):
        n = int(len(g))
        if g["hit_p05"].dtype == bool:
            n_hit = int(g["hit_p05"].sum())
        else:
            n_hit = int(g["hit_p05"].astype(str).str.lower().isin(("true", "1")).sum())
        med = pd.to_numeric(g["median_delta"], errors="coerce")
        signs = np.sign(med.to_numpy(dtype=float))
        signs = signs[np.isfinite(signs) & (signs != 0)]
        if signs.size:
            maj = int(np.sign(np.sum(signs)))
            n_agree_sign = int(np.sum(signs == maj))
        else:
            maj = 0
            n_agree_sign = 0
        rows.append(
            {
                "phase_layer": phase,
                "metric": metric,
                "n_models": n,
                "n_hit_p05": n_hit,
                "frac_hit": float(n_hit / n) if n else float("nan"),
                "median_of_median_dr": float(med.median()) if med.notna().any() else float("nan"),
                "sign_majority": maj,
                "n_models_agree_sign": n_agree_sign,
                "frac_sign_agree": float(n_agree_sign / signs.size) if signs.size else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument("--ensemble-root", type=Path, default=root)
    ap.add_argument(
        "--model",
        type=str,
        default=None,
        help="Single model; default = all paramscan_* with bout CSVs",
    )
    ap.add_argument("--r-m", type=float, default=NEAR_R_M)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    art_root = args.ensemble_root / "_nor_object_mi"
    out = args.out_dir or (art_root / "simpler_first_object_prox_0p10")
    out.mkdir(parents=True, exist_ok=True)

    if args.model:
        models = [args.model]
    else:
        models = sorted(p.name for p in art_root.glob("paramscan_*") if p.is_dir() and any((p / tag / "ladder_bout_features.csv").exists() for _, tag in PHASES))

    animal_parts: list[pd.DataFrame] = []
    test_parts: list[pd.DataFrame] = []
    overlap_rows: list[dict[str, object]] = []
    n_jobs = len(models) * len(PHASES)
    done = 0
    for model in models:
        art = art_root / model
        for phase, tag in PHASES:
            done += 1
            bout_csv = art / tag / "ladder_bout_features.csv"
            if not bout_csv.exists():
                print(f"[{done}/{n_jobs}] MISSING {model} {phase}", flush=True)
                continue
            print(f"[{done}/{n_jobs}] {model} {phase}", flush=True)
            animals, tests, summary = run_phase(bout_csv, phase, r_m=float(args.r_m))
            animals = animals.copy()
            animals.insert(0, "model", model)
            animal_parts.append(animals)
            tdf = pd.DataFrame(tests)
            tdf.insert(0, "model", model)
            test_parts.append(tdf)
            overlap_rows.append({"model": model, **summary})

    animals_df = pd.concat(animal_parts, ignore_index=True) if animal_parts else pd.DataFrame()
    tests_df = pd.concat(test_parts, ignore_index=True) if test_parts else pd.DataFrame()
    overlap_df = pd.DataFrame(overlap_rows)
    if not animals_df.empty:
        animals_df.to_csv(out / "object_prox_metrics_per_animal.csv", index=False)
    if not tests_df.empty:
        tests_df.to_csv(out / "object_prox_tests_long.csv", index=False)
    if not overlap_df.empty:
        overlap_df.to_csv(out / "object_prox_overlap_by_model.csv", index=False)

    agree = agreement_table(tests_df) if not tests_df.empty else pd.DataFrame()
    if not agree.empty:
        agree.to_csv(out / "object_prox_agreement_by_model.csv", index=False)
    if not animals_df.empty:
        med = animal_median_across_models(animals_df)
        cons = consensus_tests(med)
        cons.to_csv(out / "object_prox_consensus_tests.csv", index=False)
        disp = across_model_dispersion(animals_df)
        disp.to_csv(out / "object_prox_across_model_dispersion.csv", index=False)
        disp_sum = across_model_dispersion_summary(disp)
        disp_sum.to_csv(out / "object_prox_across_model_dispersion_summary.csv", index=False)

    payload = {
        "n_models": len(models),
        "models": models,
        "cleanup": "raw",
        "condition_layer": CONDITION,
        "gate": "bout_mean_dist_fam_m | bout_mean_dist_nvl_m",
        "r_m": float(args.r_m),
        "grain_template": GRAIN,
        "primary": "dr_exclusive",
        "companions": ["dr_inclusive", "frac_near_fam", "frac_near_nvl", "frac_both"],
        "n_animal_rows": int(len(animals_df)),
        "n_test_rows": int(len(tests_df)),
        "n_overlap_animals_total": (int(overlap_df["n_animals_with_overlap"].sum()) if not overlap_df.empty else 0),
        "n_bouts_sum_lt_2r_total": (int(overlap_df["n_bouts_sum_lt_2r"].sum()) if not overlap_df.empty else 0),
        "path": str(out),
        "pilot_model_note": str(LOCKED["model"]),
        "agreement": agree.to_dict(orient="records") if not agree.empty else [],
    }
    (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if not agree.empty:
        print("\n=== cross-model Wilcoxon DR (sex=all) ===", flush=True)
        show = agree.copy()
        show["frac_hit"] = show["frac_hit"].map(lambda x: f"{x:.2f}")
        print(
            show[
                [
                    "phase_layer",
                    "metric",
                    "n_hit_p05",
                    "n_models",
                    "frac_hit",
                    "median_of_median_dr",
                ]
            ].to_string(index=False),
            flush=True,
        )
    print(
        json.dumps(
            {
                "path": str(out),
                "n_models": len(models),
                "n_animal_rows": int(len(animals_df)),
                "n_overlap_animals_total": payload["n_overlap_animals_total"],
                "n_bouts_sum_lt_2r_total": payload["n_bouts_sum_lt_2r_total"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
