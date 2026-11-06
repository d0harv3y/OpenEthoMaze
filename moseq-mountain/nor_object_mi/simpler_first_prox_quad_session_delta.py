"""Session-paired Δ for QuadComp / ProxComp DR cousins + time twins.

Litmus C: within-animal session steps on nvl_obj for DR cousins, time twins,
and constituents (fam_* / nvl_* shannon + richness).

D: median Δ / frac>0. I companions: Wilcoxon vs 0 (sex=all + within sex);
optional Kruskal on Δ by condition within sex as separate BH family per
metric board (SessDelta-Quad / SessDelta-Prox), not folded into Family A.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.simpler_first_da import apply_bh  # noqa: E402
from nor_object_mi.simpler_first_presence import wilcoxon_paired  # noqa: E402
from nor_object_mi.simpler_first_q1 import SEX_ORDER, kruskal_within_sex  # noqa: E402
from nor_object_mi.simpler_first_session_paired import PHASE_STEPS  # noqa: E402

QUAD_METRICS: tuple[str, ...] = (
    "dr_shannon_quad",
    "dr_richness_quad",
    "dr_time_quad",
    "fam_shannon_quad",
    "nvl_shannon_quad",
    "fam_richness_quad",
    "nvl_richness_quad",
)
PROX_METRICS: tuple[str, ...] = (
    "dr_shannon_prox",
    "dr_richness_prox",
    "dr_time_prox",
    "fam_shannon_prox",
    "nvl_shannon_prox",
    "fam_richness_prox",
    "nvl_richness_prox",
)
ELIG_COL = {
    "dr_shannon_quad": "contrast_eligible",
    "dr_richness_quad": "contrast_eligible",
    "dr_time_quad": "time_contrast_eligible",
    "fam_shannon_quad": "contrast_eligible",
    "nvl_shannon_quad": "contrast_eligible",
    "fam_richness_quad": "contrast_eligible",
    "nvl_richness_quad": "contrast_eligible",
    "dr_shannon_prox": "contrast_eligible",
    "dr_richness_prox": "contrast_eligible",
    "dr_time_prox": "time_contrast_eligible",
    "fam_shannon_prox": "contrast_eligible",
    "nvl_shannon_prox": "contrast_eligible",
    "fam_richness_prox": "contrast_eligible",
    "nvl_richness_prox": "contrast_eligible",
}

DEFAULT_QUAD = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_quad_comp\quad_comp_per_animal.csv"
)
DEFAULT_PROX = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_comp\prox_comp_per_animal.csv"
)
DEFAULT_OUT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_prox_quad_session_delta"
)


def _eligible_rows(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    col = ELIG_COL[metric]
    if col not in df.columns:
        return df[pd.to_numeric(df[metric], errors="coerce").notna()].copy()
    return df[df[col].astype(bool)].copy()


def paired_deltas(df: pd.DataFrame, metrics: tuple[str, ...]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for step, left, right in PHASE_STEPS:
        for metric in metrics:
            sub = _eligible_rows(df, metric)
            L = sub[sub["session"] == left][
                ["animal_id", "sex", "condition", metric]
            ].rename(columns={metric: "left"})
            R = sub[sub["session"] == right][
                ["animal_id", metric]
            ].rename(columns={metric: "right"})
            m = L.merge(R, on="animal_id", how="inner")
            if m.empty:
                continue
            m["delta"] = pd.to_numeric(m["right"], errors="coerce") - pd.to_numeric(
                m["left"], errors="coerce"
            )
            m = m[np.isfinite(m["delta"].to_numpy(dtype=np.float64))]
            for _, r in m.iterrows():
                rows.append(
                    {
                        "animal_id": r["animal_id"],
                        "sex": r["sex"],
                        "condition": r["condition"],
                        "session_step": step,
                        "session_left": left,
                        "session_right": right,
                        "metric": metric,
                        "delta": float(r["delta"]),
                        "left": float(r["left"]),
                        "right": float(r["right"]),
                        "trial": "nvl_obj",
                    }
                )
    return pd.DataFrame(rows)


def wilcoxon_table(deltas: pd.DataFrame, *, board: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if deltas.empty:
        return pd.DataFrame()
    for step in deltas["session_step"].unique():
        for metric in deltas["metric"].unique():
            for sex in list(SEX_ORDER) + ["all"]:
                chunk = deltas[
                    (deltas["session_step"] == step) & (deltas["metric"] == metric)
                ]
                if sex != "all":
                    chunk = chunk[chunk["sex"] == sex]
                rec = wilcoxon_paired(chunk["delta"].to_numpy(dtype=np.float64))
                rows.append(
                    {
                        "board": board,
                        "session_step": step,
                        "metric": metric,
                        "sex": sex,
                        "litmus": "sessΔ_session_paired",
                        "family": f"{board}-SessWilcoxon",
                        "question": "q4_session_delta_vs0",
                        **rec,
                        "hit_p05": bool(
                            np.isfinite(rec["p"]) and float(rec["p"]) < 0.05
                        ),
                    }
                )
    return pd.DataFrame(rows)


def kruskal_on_delta(deltas: pd.DataFrame, *, board: str) -> pd.DataFrame:
    """Kruskal on Δ by condition within sex; BH within board×step family."""
    if deltas.empty:
        return pd.DataFrame()
    parts: list[pd.DataFrame] = []
    for step in sorted(deltas["session_step"].unique()):
        for metric in sorted(deltas["metric"].unique()):
            sub = deltas[
                (deltas["session_step"] == step) & (deltas["metric"] == metric)
            ].copy()
            # kruskal_within_sex expects metric column name on animals table
            sub = sub.rename(columns={"delta": "_delta_val"})
            # Build fake animals frame with metric column
            tmp = sub.rename(columns={"_delta_val": metric})
            k = kruskal_within_sex(tmp, metric=metric).copy()
            k["session_step"] = step
            k["board"] = board
            k["family"] = f"{board}-SessDelta"
            k["question"] = "q5_session_delta_condition"
            k["litmus"] = "sessΔ_condition_on_delta"
            parts.append(k)
    if not parts:
        return pd.DataFrame()
    tests = pd.concat(parts, ignore_index=True)
    tests = tests[tests["sex"].isin(SEX_ORDER)].reset_index(drop=True)
    # BH within each session_step separately (per-grain style)
    out_parts = []
    for step, g in tests.groupby("session_step", sort=True):
        out_parts.append(apply_bh(g))
    return pd.concat(out_parts, ignore_index=True)


def run(quad_csv: Path, prox_csv: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    quad = pd.read_csv(quad_csv)
    prox = pd.read_csv(prox_csv)
    d_quad = paired_deltas(quad, QUAD_METRICS)
    d_prox = paired_deltas(prox, PROX_METRICS)
    d_quad.to_csv(out_dir / "quad_session_delta_per_animal.csv", index=False)
    d_prox.to_csv(out_dir / "prox_session_delta_per_animal.csv", index=False)

    w_quad = wilcoxon_table(d_quad, board="Quad")
    w_prox = wilcoxon_table(d_prox, board="Prox")
    w_all = pd.concat([w_quad, w_prox], ignore_index=True)
    w_all.to_csv(out_dir / "session_delta_wilcoxon_long.csv", index=False)

    k_quad = kruskal_on_delta(d_quad, board="Quad")
    k_prox = kruskal_on_delta(d_prox, board="Prox")
    k_all = pd.concat([k_quad, k_prox], ignore_index=True)
    k_all.to_csv(out_dir / "session_delta_kruskal_long.csv", index=False)

    summary = {
        "status": "ok",
        "n_quad_delta_rows": int(len(d_quad)),
        "n_prox_delta_rows": int(len(d_prox)),
        "wilcoxon_n_hit_p05": int(w_all["hit_p05"].astype(bool).sum())
        if not w_all.empty
        else 0,
        "kruskal_n_hit_fdr05": int(k_all["hit_fdr05"].astype(bool).sum())
        if not k_all.empty and "hit_fdr05" in k_all.columns
        else 0,
        "elapsed_s": float(time.time() - t0),
    }
    (out_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quad-csv", type=Path, default=DEFAULT_QUAD)
    ap.add_argument("--prox-csv", type=Path, default=DEFAULT_PROX)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    run(args.quad_csv, args.prox_csv, args.out_dir)


if __name__ == "__main__":
    main()
