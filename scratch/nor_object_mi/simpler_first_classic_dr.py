"""Classic IMPRESS investigation DR vs object-prox occupancy DR.

Grain: animal × phase × novel_obj (full session).

Classic T is nose/forelimb investigation time (IMPRESS exploration export).
Object-prox T is spot occupancy in 0.10 m proximity windows (median across 21 kpMS models).
Same formula, different T:

    DR = (T_nvl − T_fam) / (T_nvl + T_fam)

This is a scalar preference, not a syllable composition. Ambulation
(speed/displacement hysteresis) is a different claim family.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_object_prox import (  # noqa: E402
    animal_median_across_models,
    discrimination_ratio,
)
from nor_object_mi.simpler_first_presence import wilcoxon_paired  # noqa: E402
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402

CONDITION = "novel_obj"
PHASES = ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr")
GRAIN = f"animal × {{phase}} × {CONDITION} (full session)"
ASSOC_Y = (
    ("dr_object_prox", "classic_vs_object_prox"),
    ("mean_speed_mps", "classic_vs_speed"),
    ("time_immobile_s", "classic_vs_immobile"),
)

DEFAULT_EXPL = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017" r"\thresholded-signal-bouts\impress_exploration.csv")
DEFAULT_AMB = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017" r"\thresholded-signal-bouts\impress_ambulation.csv")
DEFAULT_OBJECT_PROX = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017" r"\_nor_object_mi\simpler_first_object_prox_0p10\object_prox_metrics_per_animal.csv")


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().replace(" ", "_") for c in out.columns]
    rename = {"ID": "animal_id", "treatment_group": "tx", "phase_layer": "phase_layer"}
    return out.rename(columns=rename)


def spearman_pair(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Spearman ρ on finite paired observations. Litmus: identical series → ρ = 1."""
    xx = np.asarray(x, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(xx) & np.isfinite(yy)
    n = int(ok.sum())
    if n < 3:
        return {"n": float(n), "spearman_rho": float("nan"), "p": float("nan")}
    rho, p = stats.spearmanr(xx[ok], yy[ok])
    return {"n": float(n), "spearman_rho": float(rho), "p": float(p)}


def wide_novel_investigation(expl: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × phase on novel_obj: investigation times + DR."""
    df = _norm_cols(expl)
    df["animal_id"] = df["animal_id"].astype(str)
    sub = df[df["condition_layer"] == CONDITION].copy()
    if sub.empty:
        return sub.iloc[0:0].copy()

    def _metric_map(metric: str, object_id: str | None) -> pd.DataFrame:
        m = sub[sub["metric"] == metric]
        if object_id is None:
            m = m[m["object_id"].isna() | (m["object_id"].astype(str).str.lower().isin(("nan", "both", "")))]
        else:
            m = m[m["object_id"].astype(str) == object_id]
        keep = ["animal_id", "sex", "tx", "phase_layer", "duration_s", "value"]
        out = m[keep].copy()
        return out

    stored = _metric_map("discrimination_ratio", None)
    stored = stored.rename(columns={"value": "dr_stored"})
    t_fam = _metric_map("total_investigation_time_s", "fam").rename(columns={"value": "t_fam_s"})
    t_nvl = _metric_map("total_investigation_time_s", "nvl").rename(columns={"value": "t_nvl_s"})
    n_fam = _metric_map("total_investigations", "fam").rename(columns={"value": "n_fam"})
    n_nvl = _metric_map("total_investigations", "nvl").rename(columns={"value": "n_nvl"})
    t_both = _metric_map("total_investigation_time_s", None).rename(columns={"value": "t_both_s"})

    keys = ["animal_id", "sex", "tx", "phase_layer"]
    wide = t_fam[keys + ["duration_s", "t_fam_s"]].merge(t_nvl[keys + ["t_nvl_s"]], on=keys, how="outer")
    for extra, col in (
        (n_fam, "n_fam"),
        (n_nvl, "n_nvl"),
        (t_both, "t_both_s"),
        (stored, "dr_stored"),
    ):
        wide = wide.merge(extra[keys + [col]], on=keys, how="left")

    wide["t_fam_s"] = pd.to_numeric(wide["t_fam_s"], errors="coerce")
    wide["t_nvl_s"] = pd.to_numeric(wide["t_nvl_s"], errors="coerce")
    wide["dr_recomputed"] = [discrimination_ratio(nvl, fam) for nvl, fam in zip(wide["t_nvl_s"], wide["t_fam_s"])]
    wide["dr_classic"] = pd.to_numeric(wide["dr_stored"], errors="coerce")
    miss = ~np.isfinite(wide["dr_classic"].to_numpy(dtype=float))
    wide.loc[miss, "dr_classic"] = wide.loc[miss, "dr_recomputed"]
    wide["phase_layer"] = pd.Categorical(wide["phase_layer"], categories=list(PHASES), ordered=True)
    return wide.sort_values(["phase_layer", "animal_id"]).reset_index(drop=True)


def wide_novel_ambulation(amb: pd.DataFrame) -> pd.DataFrame:
    df = _norm_cols(amb)
    df["animal_id"] = df["animal_id"].astype(str)
    sub = df[df["condition_layer"] == CONDITION].copy()
    if sub.empty:
        return pd.DataFrame(columns=["animal_id", "phase_layer"])
    piv = sub.pivot_table(
        index=["animal_id", "phase_layer"],
        columns="metric",
        values="value",
        aggfunc="first",
    ).reset_index()
    piv.columns.name = None
    return piv


def pair_with_object_prox(
    classic: pd.DataFrame,
    animals_ob: pd.DataFrame,
    amb: pd.DataFrame,
) -> pd.DataFrame:
    med = animal_median_across_models(animals_ob)
    med = med.rename(columns={"dr_exclusive": "dr_object_prox"})
    med["animal_id"] = med["animal_id"].astype(str)
    keep_ob = [
        "animal_id",
        "phase_layer",
        "dr_object_prox",
        "frac_near_fam",
        "frac_near_nvl",
        "n_models",
    ]
    paired = classic.merge(med[keep_ob], on=["animal_id", "phase_layer"], how="inner")
    paired = paired.merge(amb, on=["animal_id", "phase_layer"], how="left")
    paired["dr_classic_minus_object_prox"] = paired["dr_classic"] - paired["dr_object_prox"]
    return paired


def _wx_row(phase: str, metric: str, question: str, values: np.ndarray) -> dict[str, object]:
    rec = wilcoxon_paired(values)
    return {
        "phase_layer": phase,
        "question": question,
        "metric": metric,
        "grain": GRAIN.format(phase=phase),
        "sex": "all",
        **rec,
        "hit_p05": bool(np.isfinite(rec["p"]) and float(rec["p"]) < 0.05),
        "median_noSD": "",
        "median_GHSD": "",
        "median_RBSD": "",
    }


def test_table(paired: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for phase, g in paired.groupby("phase_layer", sort=True):
        rows.append(_wx_row(str(phase), "dr_classic", "classic_dr", g["dr_classic"].to_numpy()))
        rows.append(_wx_row(str(phase), "dr_object_prox", "object_prox_dr", g["dr_object_prox"].to_numpy()))
        rows.append(
            _wx_row(
                str(phase),
                "dr_classic_minus_object_prox",
                "operationalization_shift",
                g["dr_classic_minus_object_prox"].to_numpy(),
            )
        )
        for metric, question in (("dr_classic", "classic_dr_tx"), ("dr_object_prox", "object_prox_dr_tx")):
            k = kruskal_within_sex(g, metric=metric)
            for _, r in k.iterrows():
                p = r["p"]
                rows.append(
                    {
                        "phase_layer": phase,
                        "question": question,
                        "metric": metric,
                        "grain": GRAIN.format(phase=phase),
                        "sex": r["sex"],
                        "n": r["n"],
                        "median_delta": "",
                        "frac_gt0": "",
                        "stat": r["stat"],
                        "p": p,
                        "test": "kruskal",
                        "hit_p05": bool(pd.notna(p) and float(p) < 0.05),
                        "median_noSD": r["median_noSD"],
                        "median_GHSD": r["median_GHSD"],
                        "median_RBSD": r["median_RBSD"],
                    }
                )
    return pd.DataFrame(rows)


def association_table(paired: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for phase, g in paired.groupby("phase_layer", sort=True):
        for ycol, contrast in ASSOC_Y:
            rec = spearman_pair(g["dr_classic"].to_numpy(), g[ycol].to_numpy())
            p = rec["p"]
            rows.append(
                {
                    "phase_layer": phase,
                    "contrast": contrast,
                    "x": "dr_classic",
                    "y": ycol,
                    "n": int(rec["n"]),
                    "spearman_rho": rec["spearman_rho"],
                    "p": p,
                    "hit_p05": bool(math.isfinite(p) and float(p) < 0.05),
                    "test": "spearman",
                }
            )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exploration", type=Path, default=DEFAULT_EXPL)
    ap.add_argument("--ambulation", type=Path, default=DEFAULT_AMB)
    ap.add_argument("--object-prox", type=Path, default=DEFAULT_OBJECT_PROX)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    out = args.out_dir or args.exploration.parent.parent / "_nor_object_mi" / "simpler_first_classic_dr"
    out.mkdir(parents=True, exist_ok=True)

    expl = pd.read_csv(args.exploration)
    amb_raw = pd.read_csv(args.ambulation)
    ob = pd.read_csv(args.object_prox)
    classic = wide_novel_investigation(expl)
    amb = wide_novel_ambulation(amb_raw)
    paired = pair_with_object_prox(classic, ob, amb)
    tests = test_table(paired)
    assoc = association_table(paired)

    classic.to_csv(out / "classic_dr_per_animal.csv", index=False)
    paired.to_csv(out / "classic_dr_paired.csv", index=False)
    tests.to_csv(out / "classic_dr_tests_long.csv", index=False)
    assoc.to_csv(out / "classic_dr_association.csv", index=False)

    recon = pd.to_numeric(classic["dr_stored"], errors="coerce") - pd.to_numeric(classic["dr_recomputed"], errors="coerce")
    payload = {
        "condition_layer": CONDITION,
        "classic_gate": "IMPRESS investigation (nose/forelimb + radius + angle)",
        "object_prox_gate": "spot bout-mean < 0.10 m; median across 21 kpMS models",
        "formula": "DR = (T_nvl - T_fam) / (T_nvl + T_fam)",
        "n_classic_rows": int(len(classic)),
        "n_paired_rows": int(len(paired)),
        "n_test_rows": int(len(tests)),
        "n_assoc_rows": int(len(assoc)),
        "max_abs_stored_minus_recomputed": (float(np.nanmax(np.abs(recon.to_numpy(dtype=float)))) if len(classic) else float("nan")),
        "path": str(out),
        "inputs": {
            "exploration": str(args.exploration),
            "ambulation": str(args.ambulation),
            "object_prox": str(args.object_prox),
        },
    }
    (out / "run_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(assoc.to_string(index=False), flush=True)
    print(json.dumps({k: payload[k] for k in ("path", "n_classic_rows", "n_paired_rows")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
