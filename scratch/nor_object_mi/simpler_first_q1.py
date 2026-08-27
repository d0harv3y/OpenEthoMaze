"""Q1: within-sex Kruskal on novelty proximity (Δ_prox) for one locked cell.

Grain: animal × NOR_TX × novel_obj; frame-weighted bout-mean distances.
Not a composition-ladder operation (no COUNT / UNCERTAINTY / INFO).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

TX_ORDER = ("noSD", "GHSD", "RBSD")
SEX_ORDER = ("F", "M")
TX_COLORS = {"noSD": "#4c78a8", "GHSD": "#f58518", "RBSD": "#54a24b"}

LOCKED = {
    "phase_layer": "NOR_TX",
    "condition_layer": "novel_obj",
    "model": "paramscan_s1-1e8_s2-1e5_ss-50",
    "cleanup": "raw",
    "question": "q1_delta_prox_tx",
}


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    v = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
    if not np.any(ok):
        return float("nan")
    return float(np.sum(v[ok] * w[ok]) / np.sum(w[ok]))


def animal_delta_prox(
    bouts: pd.DataFrame,
    *,
    phase_layer: str | None = None,
    condition_layer: str | None = None,
) -> pd.DataFrame:
    """One row per animal: frame-weighted d_fam, d_nvl, Δ_prox, pref."""
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

    phase = phase_layer or str(LOCKED["phase_layer"])
    cond = condition_layer or str(LOCKED["condition_layer"])
    sub = bouts[(bouts["phase_layer"] == phase) & (bouts["condition_layer"] == cond)].copy()
    rows: list[dict[str, object]] = []
    for aid, g in sub.groupby("animal_id", sort=True):
        w = g["bout_frames"].to_numpy(dtype=np.float64)
        d_fam = g["bout_mean_dist_fam_m"].to_numpy(dtype=np.float64)
        d_nvl = g["bout_mean_dist_nvl_m"].to_numpy(dtype=np.float64)
        d_fam_w = weighted_mean(d_fam, w)
        d_nvl_w = weighted_mean(d_nvl, w)
        ok = np.isfinite(d_fam) & np.isfinite(d_nvl) & np.isfinite(w) & (w > 0)
        pref = (
            float(np.sum((d_nvl[ok] < d_fam[ok]) * w[ok]) / np.sum(w[ok])) if np.any(ok) else float("nan")
        )
        sex = str(g["sex"].iloc[0])
        tx = str(g["tx"].iloc[0])
        rows.append(
            {
                "animal_id": str(aid),
                "sex": sex,
                "tx": tx,
                "phase_layer": phase,
                "n_bouts": int(len(g)),
                "n_frames": int(np.nansum(w)),
                "d_fam_m": d_fam_w,
                "d_nvl_m": d_nvl_w,
                "delta_prox": d_fam_w - d_nvl_w,
                "pref_nvl_closer": pref,
            }
        )
    return pd.DataFrame(rows)


def _tx_samples_within_sex(
    animals: pd.DataFrame, *, metric: str, sex: str
) -> dict[str, np.ndarray]:
    by_tx: dict[str, np.ndarray] = {}
    for tx in TX_ORDER:
        vals = animals.loc[
            (animals["sex"] == sex) & (animals["tx"] == tx), metric
        ].to_numpy(dtype=np.float64)
        by_tx[tx] = vals[np.isfinite(vals)]
    return by_tx


def kruskal_within_sex(animals: pd.DataFrame, *, metric: str = "delta_prox") -> pd.DataFrame:
    """Within-sex k-group rank test (Kruskal–Wallis) across tx."""
    out: list[dict[str, object]] = []
    for sex in SEX_ORDER:
        by_tx = _tx_samples_within_sex(animals, metric=metric, sex=sex)
        samples = [by_tx[t] for t in TX_ORDER]
        n_ok = all(s.size >= 2 for s in samples)
        if n_ok:
            stat, p = stats.kruskal(*samples)
            stat_f, p_f = float(stat), float(p)
        else:
            stat_f, p_f = float("nan"), float("nan")
        row: dict[str, object] = {
            "sex": sex,
            "metric": metric,
            "test": "kruskal",
            "stat": stat_f,
            "p": p_f,
            "n": int(sum(s.size for s in samples)),
        }
        for tx in TX_ORDER:
            v = by_tx[tx]
            row[f"n_{tx}"] = int(v.size)
            row[f"median_{tx}"] = float(np.median(v)) if v.size else float("nan")
            row[f"mean_{tx}"] = float(np.mean(v)) if v.size else float("nan")
        out.append(row)
    return pd.DataFrame(out)


def anova_within_sex(animals: pd.DataFrame, *, metric: str = "delta_prox") -> pd.DataFrame:
    """Within-sex Welch-style ANOVA (mean-scale twin of Kruskal) across tx.

    Uses ``scipy.stats.alexandergovern`` (Alexander–Govern approximation for
    equality of k means under heterogeneous variances — the usual Welch ANOVA
    cousin for k ≥ 2). Companion location summaries are means; medians are still
    emitted for D comparison. ``test`` column is ``welch_anova``.

    If any tx arm has zero within-group variance, Alexander–Govern is undefined
    (common for rare syllables with identical animal Δp): emit ``stat``/``p`` as NaN
    so the cell does not become a hard hit under BH.
    """
    out: list[dict[str, object]] = []
    for sex in SEX_ORDER:
        by_tx = _tx_samples_within_sex(animals, metric=metric, sex=sex)
        samples = [by_tx[t] for t in TX_ORDER]
        n_ok = all(s.size >= 2 for s in samples)
        if n_ok:
            vars_ = [float(np.var(s, ddof=1)) for s in samples]
            if any(v <= 0.0 for v in vars_):
                # AG needs positive within-arm variance in every group.
                stat_f, p_f = float("nan"), float("nan")
            else:
                res = stats.alexandergovern(*samples)
                stat_f, p_f = float(res.statistic), float(res.pvalue)
                if not np.isfinite(stat_f) or not np.isfinite(p_f):
                    stat_f, p_f = float("nan"), float("nan")
        else:
            stat_f, p_f = float("nan"), float("nan")
        row: dict[str, object] = {
            "sex": sex,
            "metric": metric,
            "test": "welch_anova",
            "stat": stat_f,
            "p": p_f,
            "n": int(sum(s.size for s in samples)),
        }
        for tx in TX_ORDER:
            v = by_tx[tx]
            row[f"n_{tx}"] = int(v.size)
            row[f"median_{tx}"] = float(np.median(v)) if v.size else float("nan")
            row[f"mean_{tx}"] = float(np.mean(v)) if v.size else float("nan")
        out.append(row)
    return pd.DataFrame(out)


def judge_q1(tests: pd.DataFrame) -> dict[str, object]:
    """Tx hit = Kruskal p<0.05 in ≥1 sex with n≥2 per tx and readable medians."""
    hits: list[str] = []
    for _, r in tests.iterrows():
        p = float(r["p"]) if pd.notna(r["p"]) else float("nan")
        ns = [int(r[f"n_{t}"]) for t in TX_ORDER]
        meds = [float(r[f"median_{t}"]) for t in TX_ORDER]
        readable = all(n >= 2 for n in ns) and all(np.isfinite(meds))
        if readable and np.isfinite(p) and p < 0.05:
            hits.append(str(r["sex"]))
    med_sign = {
        str(r["sex"]): (
            int(np.sign(float(r["median_noSD"])))
            if pd.notna(r["median_noSD"])
            else None
        )
        for _, r in tests.iterrows()
    }
    return {
        "q1": "hit" if hits else "miss",
        "q1_hit_sexes": hits,
        "q1_rule": "kruskal_p<0.05 within-sex, n>=2 per tx",
        "median_delta_prox_sign_by_sex": med_sign,
        "note": (
            "Same-sign median Δ_prox across sexes is a preference direction, "
            "not a tx hit; tx claim uses Kruskal only."
        ),
    }


def fig_delta_prox(animals: pd.DataFrame, tests: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.6), sharey=True)
    p_map = {str(r["sex"]): r["p"] for _, r in tests.iterrows()}
    for ax, sex in zip(axes, SEX_ORDER):
        sub = animals[animals["sex"] == sex]
        for i, tx in enumerate(TX_ORDER):
            y = sub.loc[sub["tx"] == tx, "delta_prox"].to_numpy(dtype=np.float64)
            y = y[np.isfinite(y)]
            jitter = (np.arange(y.size) - (y.size - 1) / 2) * 0.02
            ax.scatter(
                np.full(y.size, i) + jitter,
                y,
                s=22,
                color=TX_COLORS[tx],
                edgecolors="white",
                linewidths=0.4,
                zorder=2,
            )
            if y.size:
                ax.plot([i - 0.22, i + 0.22], [np.median(y)] * 2, color="#222", lw=1.8, zorder=3)
        ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
        ax.set_xticks(range(len(TX_ORDER)))
        ax.set_xticklabels(list(TX_ORDER))
        p = p_map.get(sex, float("nan"))
        ptxt = "n/a" if p != p else f"p={p:.3g}"
        ax.set_title(f"{sex}  Kruskal {ptxt}")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    axes[0].set_ylabel("Δ_prox (m)  d_fam − d_nvl")
    fig.suptitle("Q1 novelty proximity · NOR_TX · novel_obj · raw · pilot model", fontsize=10)
    fig.text(
        0.01,
        0.01,
        "Grain: animal × novel_obj window · frame-weighted bout-mean spot distances · >0 closer to novel",
        fontsize=7,
        color="#555",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(out.with_suffix(".png"), dpi=150)
    fig.savefig(out.with_suffix(".pdf"))
    plt.close(fig)


def run_q1(bout_csv: Path, out_dir: Path) -> dict[str, object]:
    bouts = pd.read_csv(bout_csv)
    animals = animal_delta_prox(bouts)
    tests = kruskal_within_sex(animals, metric="delta_prox")
    verdict = judge_q1(tests)
    out_dir.mkdir(parents=True, exist_ok=True)
    animals.to_csv(out_dir / "q1_animal_delta_prox.csv", index=False)
    tests.to_csv(out_dir / "q1_within_sex_tx_kruskal.csv", index=False)
    fig_delta_prox(animals, tests, out_dir / "fig_q1_delta_prox")
    summary = {
        "status": "ok",
        **LOCKED,
        "bout_csv": str(bout_csv),
        "n_animals": int(len(animals)),
        "n_finite_delta_prox": int(animals["delta_prox"].notna().sum()),
        **verdict,
        "q2": "parked",
        "q3": "parked",
        "kruskal": tests.to_dict(orient="records"),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017")
    ap.add_argument(
        "--bout-csv",
        type=Path,
        default=root
        / "_nor_object_mi"
        / LOCKED["model"]
        / "condition_ladder"
        / "ladder_bout_features.csv",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=root / "_nor_object_mi" / "simpler_first_NOR_TX_novel_obj",
    )
    args = ap.parse_args(argv)
    summary = run_q1(args.bout_csv, args.out_dir)
    print(json.dumps(summary, indent=2))
    return 0


SEX_ORDER = SEX_ORDER
kruskal_within_sex = kruskal_within_sex


if __name__ == "__main__":
    raise SystemExit(main())
