"""Publication figures for between-phase paired contrasts (condition held).

Reads only CSVs listed in INFO_phase_paired.md. Pairing axis is phase, not
condition — not the presence-step figures.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_phase_paired.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    MUTE,
    PILOT_MODEL,
    SEX_MARKER,
    SEX_ORDER,
    TX_COLOR,
    TX_ORDER,
    apply_style,
    fig_footnote,
    p_text,
    save_pdf_png,
    text_on_cmap,
)
from nor_object_mi.fig_simpler_first_presence import (  # noqa: E402
    WILCOXON_NOSD,
    WILCOXON_POOLED,
    _attach_iqr,
    _draw_tx_violins,
)
from nor_object_mi.simpler_first_presence import (  # noqa: E402
    CONTROL_TX,
    across_model_dispersion,
    across_model_dispersion_summary,
    wilcoxon_paired,
)
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_phase_paired"
)
CONDS = ("no_obj", "identical_obj", "novel_obj")
COND_LAB = {
    "no_obj": "no_obj",
    "identical_obj": "identical_obj",
    "novel_obj": "novel_obj",
}
PHASE_STEPS = ("BL->TX", "TX->REC3hr", "REC3hr->REC11hr", "BL->REC11hr")
STEP_LAB = {
    "BL->TX": "BL–TX",
    "TX->REC3hr": "TX–R3",
    "REC3hr->REC11hr": "R3–R11",
    "BL->REC11hr": "BL–R11",
}
METRICS = ("frac_near", "mean_dist_any_m", "richness", "shannon_bits")
METRIC_LAB = {
    "frac_near": "frac_near",
    "mean_dist_any_m": "mean dist (m)",
    "richness": "richness",
    "shannon_bits": "Shannon (bits)",
}
DELTA_COL = {
    "frac_near": "delta_frac_near",
    "mean_dist_any_m": "delta_mean_dist_any_m",
    "richness": "delta_richness",
    "shannon_bits": "delta_shannon_bits",
}
FOOT = (
    "Grain: animal × condition (full session). Pairing axis = phase, condition held. "
    "Companion hit rule: sex=all Wilcoxon p < 0.05, txs pooled — not a treatment claim. "
    "Evolution I primary is Wilcoxon on Δ, tx=noSD, within sex (see agreement_noSD_by_sex). "
    "Near window 0.10 m on spot. 21 kpMS models. Not the presence-step design "
    "(that pairs conditions inside one phase). On no_obj, dist_any is to historical loci."
)
FOOT_KR = (
    "Grain: animal × condition (full session). This figure is Kruskal–Wallis by tx "
    "(noSD, GHSD, RBSD) within sex, on the paired phase Δ — a treatment claim. "
    "Color: frac of 21 kpMS models with Kruskal p < 0.05 (uncorrected). Not the "
    "Wilcoxon hit rule. Not MI; not DA; not PERMANOVA."
)
FOOT_DA = (
    "Grain: animal × condition (full session). DA = Wilcoxon on Δp_k; primary hit "
    "BH q < 0.05 within model × condition × phase-step (hit_fdr05). Ids are "
    "within-model only — do not match syllable 7 across alphabets. Not Shannon."
)
VIOLIN_METRICS = ("frac_near", "mean_dist_any_m")
VIOLIN_STEM = {
    "frac_near": "fig_phase_paired_violin_frac_near",
    "mean_dist_any_m": "fig_phase_paired_violin_mean_dist",
}
VIOLIN_DELTA_COLS = ("delta_frac_near", "delta_mean_dist_any_m")
FOOT_VIOLIN_PREFIX = (
    "Grain: animal × novel_obj (full session). Pairing axis = phase, condition held. "
    "Each point is one animal: the median of that animal's paired Δ across 21 kpMS "
    "models. Whiskers = ±½ IQR of that animal's Δ across models (salt), not SEM. "
    "Color=tx, shape=sex; violins are KDE of those medians by tx (sexes pooled in the KDE). "
)
FOOT_VIOLIN_WX_POOLED = (
    "Wilcoxon p is Δ vs 0, sex=all, txs pooled (companion; not a treatment claim). "
)
FOOT_VIOLIN_WX_NOSD = (
    "Wilcoxon p is Δ vs 0, tx=noSD, within sex (evolution I; not a treatment claim). "
)
FOOT_VIOLIN_TAIL = (
    "Kruskal p is within sex on the same medians (treatment claim). BL–TX n≈48 per tx arm; "
    "pairs that include REC n≈24. Richness and Shannon omitted (less cross-model consensus). "
    "Not MI; not DA. "
)


def _foot_violin(wilcoxon: str) -> str:
    wx = FOOT_VIOLIN_WX_POOLED if wilcoxon == WILCOXON_POOLED else FOOT_VIOLIN_WX_NOSD
    return FOOT_VIOLIN_PREFIX + wx + FOOT_VIOLIN_TAIL


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def _lex_pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _annotate(ax, mat: np.ndarray, *, fmt: str = "{:.2f}", fontsize: float = 6.5) -> None:
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            v = mat[i, j]
            if np.isfinite(v):
                ax.text(
                    j,
                    i,
                    fmt.format(v),
                    ha="center",
                    va="center",
                    fontsize=fontsize,
                    color=text_on_cmap(v),
                )


def fig_frac_hit(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, cond in zip(axes, CONDS):
        sub = agr[agr["condition_layer"] == cond]
        mat = np.full((len(PHASE_STEPS), len(METRICS)), np.nan)
        for i, st in enumerate(PHASE_STEPS):
            for j, met in enumerate(METRICS):
                row = sub[(sub["phase_step"] == st) & (sub["metric"] == met)]
                if len(row) == 1:
                    mat[i, j] = float(row["frac_hit"].iloc[0])
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(METRICS)))
        ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right", fontsize=7)
        ax.set_yticks(range(len(PHASE_STEPS)))
        ax.set_yticklabels([STEP_LAB[s] for s in PHASE_STEPS])
        ax.set_title(COND_LAB[cond], loc="left", fontweight="bold", color=INK)
        _annotate(ax, mat)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="frac of 21 models with Wilcoxon hit")
    fig.suptitle(
        "Between-phase, same condition: does the paired phase step hit? (Wilcoxon, sex=all)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, FOOT, y=-0.10)
    save_pdf_png(fig, out / "fig_phase_paired_frac_hit")


def fig_median_delta(agr: pd.DataFrame, out: Path) -> None:
    apply_style()
    fig, axes = plt.subplots(3, 4, figsize=(7.2, 6.6), constrained_layout=True)
    x = np.arange(len(PHASE_STEPS))
    for r, cond in enumerate(CONDS):
        sub = agr[agr["condition_layer"] == cond]
        for c, met in enumerate(METRICS):
            ax = axes[r, c]
            ys = []
            for st in PHASE_STEPS:
                row = sub[(sub["phase_step"] == st) & (sub["metric"] == met)]
                ys.append(float(row["median_of_median_delta"].iloc[0]) if len(row) == 1 else np.nan)
            colors = ["#2f5d8a" if (np.isfinite(y) and y >= 0) else "#8a4f3d" for y in ys]
            ax.bar(x, ys, color=colors, width=0.72, edgecolor="none")
            ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
            ax.set_xticks(x)
            ax.set_xticklabels([STEP_LAB[s] for s in PHASE_STEPS], fontsize=6, rotation=30, ha="right")
            if c == 0:
                ax.set_ylabel(COND_LAB[cond] + "\nmedian of model median Δ", fontsize=7)
            if r == 0:
                ax.set_title(METRIC_LAB[met], loc="left", fontweight="bold", color=INK, fontsize=8)
    fig.suptitle(
        "Direction of between-phase change (median across 21 models of each model's median Δ)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(
        fig,
        FOOT + " Descriptive companion to frac_hit; independent y-scales (units differ).",
        y=-0.04,
    )
    save_pdf_png(fig, out / "fig_phase_paired_median_delta")


def fig_tx_kruskal(tests: pd.DataFrame, out: Path) -> None:
    apply_style()
    kr = tests[tests["test"] == "kruskal"].copy()
    kr["hit"] = _as_bool(kr["hit_p05"])
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.4), constrained_layout=True)
    im = None
    for r, cond in enumerate(CONDS):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = kr[(kr["condition_layer"] == cond) & (kr["sex"] == sex)]
            mat = np.full((len(PHASE_STEPS), len(METRICS)), np.nan)
            for i, st in enumerate(PHASE_STEPS):
                for j, met in enumerate(METRICS):
                    cell = sub[(sub["phase_step"] == st) & (sub["metric"] == f"delta_{met}")]
                    if cell.empty:
                        cell = sub[(sub["phase_step"] == st) & (sub["metric"] == met)]
                    if not cell.empty:
                        mat[i, j] = float(cell["hit"].mean())
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(METRICS)))
            ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right", fontsize=6.5)
            ax.set_yticks(range(len(PHASE_STEPS)))
            ax.set_yticklabels([STEP_LAB[s] for s in PHASE_STEPS])
            sex_lab = "female" if sex == "F" else "male"
            ax.set_title(f"{COND_LAB[cond]}  ·  {sex_lab}", loc="left", fontweight="bold", color=INK, fontsize=8)
            _annotate(ax, mat, fontsize=6)
    fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="frac of 21 models with Kruskal p < 0.05")
    fig.suptitle(
        "Does treatment modulate the between-phase Δ? (Kruskal by tx, within sex)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FOOT_KR, y=-0.04)
    save_pdf_png(fig, out / "fig_phase_paired_tx_kruskal")


def animal_median_novel(deltas: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × phase-step on novel_obj: median Δ across models."""
    sub = deltas[deltas["condition_layer"] == "novel_obj"].copy()
    keys = ["animal_id", "sex", "tx", "phase_step"]
    out = sub.groupby(keys, as_index=False)[list(VIOLIN_DELTA_COLS)].median()
    n_mod = sub.groupby(keys)["model"].nunique()
    if int(n_mod.min()) != int(n_mod.max()):
        raise AssertionError(f"uneven model coverage per animal: {n_mod.min()}–{n_mod.max()}")
    out["n_models"] = int(n_mod.min())
    return out


def fig_novel_violins(
    deltas: pd.DataFrame,
    out: Path,
    *,
    salt: pd.DataFrame | None = None,
    salt_summary: pd.DataFrame | None = None,
    wilcoxon: str = WILCOXON_POOLED,
) -> None:
    apply_style()
    dsub = animal_median_novel(deltas)
    n_models = int(dsub["n_models"].iloc[0]) if len(dsub) else 0
    salt_on = ["animal_id", "sex", "tx", "phase_step"]
    for met in VIOLIN_METRICS:
        rng = np.random.default_rng(0)
        fig, axes = plt.subplots(1, 4, figsize=(7.2, 3.8), sharey=True, constrained_layout=True)
        col = DELTA_COL[met]
        med = dsub
        iqr_col = None
        if salt is not None and not salt.empty:
            s = salt
            if "condition_layer" in s.columns:
                s = s[s["condition_layer"] == "novel_obj"]
            med = _attach_iqr(dsub, s, metric=col, on=salt_on)
            iqr_col = "iqr_across_models"
        for c, st in enumerate(PHASE_STEPS):
            ax = axes[c]
            panel = med[med["phase_step"] == st]
            ns = _draw_tx_violins(ax, panel, col, rng, iqr_col=iqr_col)
            if c == 0:
                ax.set_ylabel("Δ (right − left)", fontsize=8)
            ax.set_title(STEP_LAB[st], loc="left", fontweight="bold", color=INK, fontsize=8)
            lines = ["n=" + "/".join(str(n) for n in ns)]
            if salt_summary is not None and not salt_summary.empty:
                srow = salt_summary[
                    (salt_summary["condition_layer"] == "novel_obj")
                    & (salt_summary["phase_step"] == st)
                    & (salt_summary["metric"] == col)
                ]
                if len(srow) == 1:
                    lines.append(f"cohort med IQR={float(srow['median_of_iqr'].iloc[0]):.3g}")
            if wilcoxon == WILCOXON_POOLED:
                rec = wilcoxon_paired(panel[col].to_numpy(dtype=float))
                lines.append("Wilcoxon pooled " + p_text(float(rec["p"])))
            else:
                for sex in SEX_ORDER:
                    ctrl = panel[(panel["sex"] == sex) & (panel["tx"] == CONTROL_TX)]
                    rec = wilcoxon_paired(ctrl[col].to_numpy(dtype=float))
                    lines.append(f"Wilcoxon noSD {sex} " + p_text(float(rec["p"])))
            k = kruskal_within_sex(
                pd.DataFrame(
                    {
                        "sex": panel["sex"].to_numpy(),
                        "tx": panel["tx"].to_numpy(),
                        col: panel[col].to_numpy(dtype=float),
                    }
                ),
                metric=col,
            )
            for sex, lab in (("F", "Kruskal F "), ("M", "Kruskal M ")):
                row = k[k["sex"] == sex]
                if len(row) == 1:
                    lines.append(lab + p_text(float(row["p"].iloc[0])))
            ax.text(
                0.03,
                0.97,
                "\n".join(lines),
                transform=ax.transAxes,
                va="top",
                ha="left",
                fontsize=5.5,
                color=INK,
                bbox=dict(
                    boxstyle="round,pad=0.15",
                    facecolor="white",
                    edgecolor="#dddddd",
                    lw=0.5,
                ),
            )
        handles = [
            Line2D([0], [0], marker="o", color="none", markerfacecolor=TX_COLOR[t], markersize=6, label=t)
            for t in TX_ORDER
        ] + [
            Line2D(
                [0],
                [0],
                marker=SEX_MARKER[s],
                color="none",
                markerfacecolor=INK,
                markersize=6,
                label=s,
            )
            for s in SEX_ORDER
        ]
        fig.legend(handles=handles, loc="upper right", frameon=False, fontsize=7, ncol=5, bbox_to_anchor=(1.0, 1.14))
        fig.suptitle(
            f"novel_obj  ·  animal-level between-phase Δ of {METRIC_LAB[met]}  ·  median across {n_models} kpMS models",
            fontsize=10,
            fontweight="bold",
            color=INK,
            y=1.16,
        )
        fig_footnote(fig, _foot_violin(wilcoxon), y=-0.12)
        save_pdf_png(fig, out / VIOLIN_STEM[met])


def fig_da_n_hit(tests: pd.DataFrame, out: Path) -> None:
    apply_style()
    t = tests.copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    counts = t.groupby(["model", "condition_layer", "phase_step"], as_index=False)["hit"].sum()
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, sharey=True, constrained_layout=True)
    x = np.arange(len(PHASE_STEPS))
    for ax, cond in zip(axes, CONDS):
        ax.set_title(COND_LAB[cond], loc="left", fontweight="bold", color=INK)
        for i, st in enumerate(PHASE_STEPS):
            ys = counts[(counts["condition_layer"] == cond) & (counts["phase_step"] == st)]["hit"].to_numpy(
                dtype=float
            )
            jitter = rng.normal(0, 0.08, size=ys.size)
            ax.scatter(np.full(ys.shape, i) + jitter, ys, s=12, c="#2f5d8a", alpha=0.75, edgecolors="none")
            if ys.size:
                ax.plot([i - 0.22, i + 0.22], [np.median(ys)] * 2, color=INK, lw=1.8, zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels([STEP_LAB[s] for s in PHASE_STEPS], fontsize=7, rotation=25, ha="right")
        ax.axhline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
        if ax is axes[0]:
            ax.set_ylabel("n FDR-hit syllables per model")
    fig.suptitle(
        "Between-phase DA: how many syllables FDR-hit? (21 models; BH within cell)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, FOOT_DA, y=-0.12)
    save_pdf_png(fig, out / "fig_phase_paired_da_n_hit_fdr05")


def fig_da_jaccard(cons: pd.DataFrame, out: Path) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, cond in zip(axes, CONDS):
        sub = cons[cons["condition_layer"] == cond]
        mat = np.full((4, 4), np.nan)
        for i, sa in enumerate(PHASE_STEPS):
            for j, sb in enumerate(PHASE_STEPS):
                if i == j:
                    continue
                a, b = _lex_pair(sa, sb)
                rows = sub[(sub["phase_step_a"] == a) & (sub["phase_step_b"] == b)]
                if rows.empty:
                    continue
                mat[i, j] = float(pd.to_numeric(rows["jaccard"], errors="coerce").median())
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="equal")
        ax.set_xticks(range(4))
        ax.set_xticklabels([STEP_LAB[s] for s in PHASE_STEPS], fontsize=6.5, rotation=30, ha="right")
        ax.set_yticks(range(4))
        ax.set_yticklabels([STEP_LAB[s] for s in PHASE_STEPS], fontsize=6.5)
        ax.set_title(COND_LAB[cond], loc="left", fontweight="bold", color=INK)
        for i in range(4):
            for j in range(4):
                v = mat[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6, color=text_on_cmap(v))
    fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02, label="median Jaccard across 21 models")
    fig.suptitle(
        "Within-model DA overlap across phase-steps (Jaccard of FDR-hit ids; condition held)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(
        fig,
        FOOT_DA + " CSV phase_step_a/b are lexicographic; heatmaps are protocol order.",
        y=-0.12,
    )
    save_pdf_png(fig, out / "fig_phase_paired_da_jaccard")


def fig_da_persistence(pers: pd.DataFrame, out: Path, *, model: str) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, sharey=True, constrained_layout=True)
    bins = np.arange(-0.5, 5.5, 1.0)
    for ax, cond in zip(axes, CONDS):
        sub = pers[(pers["model"] == model) & (pers["condition_layer"] == cond)]
        ax.hist(sub["n_hit_fdr05"].to_numpy(dtype=float), bins=bins, color="#2f5d8a", edgecolor="white", lw=0.4)
        ax.set_xticks([0, 1, 2, 3, 4])
        ax.set_title(COND_LAB[cond], loc="left", fontweight="bold", color=INK)
        ax.set_xlabel("n phase-steps FDR-hit (of 4)")
        if ax is axes[0]:
            ax.set_ylabel("n syllables (this model)")
        n4 = int((sub["n_hit_fdr05"] == 4).sum())
        ax.text(
            0.96,
            0.96,
            f"n_id={len(sub)}\nn_hit=4: {n4}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            color=MUTE,
        )
    fig.suptitle(
        f"Pilot {model}: does the same id keep FDR-hitting across phase-steps?",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, FOOT_DA, y=-0.12)
    save_pdf_png(fig, out / "fig_phase_paired_da_persistence_pilot")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--pilot-model", type=str, default=PILOT_MODEL)
    ap.add_argument(
        "--wilcoxon",
        choices=(WILCOXON_POOLED, WILCOXON_NOSD),
        default=WILCOXON_POOLED,
        help="Violin Wilcoxon: pooled tx+sex vs noSD within sex.",
    )
    args = ap.parse_args(argv)
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    agr = pd.read_csv(run / "phase_paired_agreement_by_model.csv")
    tests = pd.read_csv(run / "phase_paired_tests_long.csv")
    deltas = pd.read_csv(run / "phase_paired_deltas_per_animal.csv")
    da_tests = pd.read_csv(run / "phase_paired_da_tests_long.csv")
    da_cons = pd.read_csv(run / "phase_paired_da_consistency_step_pairs.csv")
    da_pers = pd.read_csv(run / "phase_paired_da_syllable_persistence.csv")
    salt_keys = ("animal_id", "sex", "tx", "phase_step", "condition_layer")
    salt = across_model_dispersion(deltas, keys=salt_keys)
    salt_sum = across_model_dispersion_summary(
        salt, group_keys=("condition_layer", "phase_step", "metric")
    )
    salt.to_csv(run / "phase_paired_across_model_dispersion.csv", index=False)
    salt_sum.to_csv(run / "phase_paired_across_model_dispersion_summary.csv", index=False)
    fig_frac_hit(agr, out)
    fig_median_delta(agr, out)
    fig_tx_kruskal(tests, out)
    fig_novel_violins(
        deltas, out, salt=salt, salt_summary=salt_sum, wilcoxon=args.wilcoxon
    )
    fig_da_n_hit(da_tests, out)
    fig_da_jaccard(da_cons, out)
    fig_da_persistence(da_pers, out, model=args.pilot_model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
