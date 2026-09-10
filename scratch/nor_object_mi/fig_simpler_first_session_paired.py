"""Publication figures for between-phase paired contrasts (condition held).

Reads only CSVs listed in INFO_session_paired.md. Pairing axis is phase, not
condition — not the presence-step figures.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_session_paired.py
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
    CONDITION_COLOR,
    CONDITION_ORDER,
    apply_style,
    fig_footnote,
    fig_legend_and_footnote,
    p_text,
    save_pdf_png,
    save_png,
    set_wrapped_title,
    text_on_cmap,
    condition_sex_legend_handles,
    type_scale,
)
from nor_object_mi.fig_simpler_first_presence import (  # noqa: E402
    WILCOXON_NOSD,
    WILCOXON_POOLED,
    _attach_iqr,
    _draw_condition_violins,
)
from nor_object_mi.simpler_first_presence import (  # noqa: E402
    CONTROL_CONDITION,
    across_model_dispersion,
    across_model_dispersion_summary,
    wilcoxon_paired,
)
from nor_object_mi.fig_simpler_first_da import (  # noqa: E402
    Y_CLIP,
    _shared_volcano_xlim,
    _stratified_xlim,
    _volcano_xy,
    attach_cluster_ids_to_tests,
    fig_volcano_ladder_model_phase,
    fig_volcano_ladder_overlay_phase,
    load_cluster_lookup,
    write_volcano_ladder_overlay_legend,
)
from nor_object_mi.simpler_first_da import da_tests_condition_sex_from_animal_deltas  # noqa: E402
from nor_object_mi.simpler_first_session_paired import (  # noqa: E402
    PAIRED_FOOT_LEAD,
    PHASE_STEP_NAMES as PHASE_STEPS,
    STEP_LAB,
    footnote_paired_n,
    overlay_step_suptitle_parts,
    paired_n_by_step,
    step_axis_label,
    step_axis_labels,
)
from nor_object_mi.simpler_first_q1 import kruskal_within_sex  # noqa: E402

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_session_paired"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
TRIALS = ("no_obj", "id_obj", "nvl_obj")
COND_LAB = {
    "no_obj": "no_obj",
    "id_obj": "id_obj",
    "nvl_obj": "nvl_obj",
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
    PAIRED_FOOT_LEAD
    + "Companion hit rule: sex=all Wilcoxon p < 0.05, txs pooled — not a treatment claim. "
    "Evolution I primary is Wilcoxon on Δ, condition=noSD, within sex (see agreement_noSD_by_sex). "
    "Near window 0.10 m on spot. 21 kpMS models. Not the presence-step design "
    "(that pairs conditions inside one phase). On no_obj, dist_any is to historical loci."
)
FOOT_KR = (
    PAIRED_FOOT_LEAD
    + "This figure is Kruskal–Wallis by tx (noSD, GHSD, RBSD) within sex, on the paired "
    "phase Δ — a treatment claim. Color: frac of 21 kpMS models with Kruskal p < 0.05 "
    "(uncorrected). Not the Wilcoxon hit rule. Not MI; not DA; not PERMANOVA."
)
FOOT_DA = (
    PAIRED_FOOT_LEAD
    + "DA = Wilcoxon on Δp_k; primary hit BH q < 0.05 within model × condition × phase-step "
    "(hit_fdr05). Ids are within-model only — do not match syllable 7 across alphabets. "
    "Not Shannon."
)
FOOT_DA_VOLCANO = (
    PAIRED_FOOT_LEAD
    + "One point = one model × syllable × sex (Wilcoxon on paired Δp inside tx × sex). "
    "Filled = BH q < 0.05 within model × condition × phase-step × tx × sex. "
    "Not a Kruskal across tx. Ids not matched across alphabets. y = uncorrected p, clip 4."
)
TXSEX_TESTS = "session_paired_da_tests_condition_sex.csv"
DA_CELL_COLS = ("model", "trial", "session_step", "condition", "sex")
PHASE_VOLCANO_STEPS = tuple((s, STEP_LAB[s]) for s in PHASE_STEPS)
LADDER_COND_TAG = {
    "no_obj": "no_obj",
    "id_obj": "id_obj",
    "nvl_obj": "nvl_obj",
}
VOLCANO_STEM = {
    "no_obj": "fig_session_paired_da_volcano_no_obj",
    "id_obj": "fig_session_paired_da_volcano_identical",
    "nvl_obj": "fig_session_paired_da_volcano_novel",
}
LADDER_OVERLAY_STEM = "fig_session_paired_da_volcano_ladder_overlay"
LADDER_STEM_PREFIX = "fig_session_paired_da_volcano_ladder"
VIOLIN_METRICS = ("frac_near", "mean_dist_any_m")
VIOLIN_STEM = {
    "frac_near": "fig_session_paired_violin_frac_near",
    "mean_dist_any_m": "fig_session_paired_violin_mean_dist",
}
VIOLIN_DELTA_COLS = ("delta_frac_near", "delta_mean_dist_any_m")
FOOT_VIOLIN_PREFIX = (
    PAIRED_FOOT_LEAD
    + "Each point is one animal: the median of that animal's paired Δ across 21 kpMS "
    "models (nvl_obj only). Whiskers = ±½ IQR of that animal's Δ across models (salt), "
    "not SEM. Color=tx, shape=sex; violins are KDE of those medians by tx (sexes pooled "
    "in the KDE). "
)
FOOT_VIOLIN_WX_POOLED = (
    "Wilcoxon p is Δ vs 0, sex=all, txs pooled (companion; not a treatment claim). "
)
FOOT_VIOLIN_WX_NOSD = (
    "Wilcoxon p is Δ vs 0, condition=noSD, within sex (evolution I; not a treatment claim). "
)
FOOT_VIOLIN_TAIL = (
    "Kruskal p is within sex on the same medians (treatment claim). "
    "Richness and Shannon omitted (less cross-model consensus). Not MI; not DA. "
)


def _foot_violin(wilcoxon: str, n_map: dict[str, int]) -> str:
    wx = FOOT_VIOLIN_WX_POOLED if wilcoxon == WILCOXON_POOLED else FOOT_VIOLIN_WX_NOSD
    n_line = footnote_paired_n(n_map) if n_map else PAIRED_FOOT_LEAD.rstrip()
    return FOOT_VIOLIN_PREFIX + wx + n_line + " " + FOOT_VIOLIN_TAIL


def _foot_with_n(base: str, n_map: dict[str, int]) -> str:
    n_line = footnote_paired_n(n_map) if n_map else PAIRED_FOOT_LEAD.rstrip()
    return base + " " + n_line


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


def fig_frac_hit(agr: pd.DataFrame, out: Path, *, n_map: dict[str, int]) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, cond in zip(axes, TRIALS):
        sub = agr[agr["trial"] == cond]
        mat = np.full((len(PHASE_STEPS), len(METRICS)), np.nan)
        for i, st in enumerate(PHASE_STEPS):
            for j, met in enumerate(METRICS):
                row = sub[(sub["session_step"] == st) & (sub["metric"] == met)]
                if len(row) == 1:
                    mat[i, j] = float(row["frac_hit"].iloc[0])
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(len(METRICS)))
        ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right", fontsize=7)
        ax.set_yticks(range(len(PHASE_STEPS)))
        ax.set_yticklabels(step_axis_labels(n_map))
        ax.set_title(COND_LAB[cond], loc="left", fontweight="bold", color=INK)
        _annotate(ax, mat)
    fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label="frac of 21 models with Wilcoxon hit")
    fig.suptitle(
        "Within-animal paired phase Δ: does the step hit? (Wilcoxon, sex=all)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, _foot_with_n(FOOT, n_map), y=-0.10)
    save_pdf_png(fig, out / "fig_session_paired_frac_hit")


def fig_median_delta(agr: pd.DataFrame, out: Path, *, n_map: dict[str, int]) -> None:
    apply_style()
    fig, axes = plt.subplots(3, 4, figsize=(7.2, 6.6), constrained_layout=True)
    x = np.arange(len(PHASE_STEPS))
    for r, cond in enumerate(TRIALS):
        sub = agr[agr["trial"] == cond]
        for c, met in enumerate(METRICS):
            ax = axes[r, c]
            ys = []
            for st in PHASE_STEPS:
                row = sub[(sub["session_step"] == st) & (sub["metric"] == met)]
                ys.append(float(row["median_of_median_delta"].iloc[0]) if len(row) == 1 else np.nan)
            colors = ["#2f5d8a" if (np.isfinite(y) and y >= 0) else "#8a4f3d" for y in ys]
            ax.bar(x, ys, color=colors, width=0.72, edgecolor="none")
            ax.axhline(0.0, color="#bbbbbb", lw=0.7, ls="--", zorder=0)
            ax.set_xticks(x)
            ax.set_xticklabels(step_axis_labels(n_map), fontsize=6, rotation=30, ha="right")
            if c == 0:
                ax.set_ylabel(COND_LAB[cond] + "\nmedian of model median Δ", fontsize=7)
            if r == 0:
                ax.set_title(METRIC_LAB[met], loc="left", fontweight="bold", color=INK, fontsize=8)
    fig.suptitle(
        "Within-animal paired Δ: direction of phase change (median across 21 models)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(
        fig,
        _foot_with_n(
            FOOT + " Descriptive companion to frac_hit; independent y-scales (units differ).",
            n_map,
        ),
        y=-0.04,
    )
    save_pdf_png(fig, out / "fig_session_paired_median_delta")


def fig_condition_kruskal(tests: pd.DataFrame, out: Path, *, n_map: dict[str, int]) -> None:
    apply_style()
    kr = tests[tests["test"] == "kruskal"].copy()
    kr["hit"] = _as_bool(kr["hit_p05"])
    fig, axes = plt.subplots(3, 2, figsize=(7.2, 7.4), constrained_layout=True)
    im = None
    for r, cond in enumerate(TRIALS):
        for c, sex in enumerate(SEX_ORDER):
            ax = axes[r, c]
            sub = kr[(kr["trial"] == cond) & (kr["sex"] == sex)]
            mat = np.full((len(PHASE_STEPS), len(METRICS)), np.nan)
            for i, st in enumerate(PHASE_STEPS):
                for j, met in enumerate(METRICS):
                    cell = sub[(sub["session_step"] == st) & (sub["metric"] == f"delta_{met}")]
                    if cell.empty:
                        cell = sub[(sub["session_step"] == st) & (sub["metric"] == met)]
                    if not cell.empty:
                        mat[i, j] = float(cell["hit"].mean())
            im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")
            ax.set_xticks(range(len(METRICS)))
            ax.set_xticklabels([METRIC_LAB[m] for m in METRICS], rotation=35, ha="right", fontsize=6.5)
            ax.set_yticks(range(len(PHASE_STEPS)))
            ax.set_yticklabels(step_axis_labels(n_map))
            sex_lab = "female" if sex == "F" else "male"
            ax.set_title(f"{COND_LAB[cond]}  ·  {sex_lab}", loc="left", fontweight="bold", color=INK, fontsize=8)
            _annotate(ax, mat, fontsize=6)
    fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="frac of 21 models with Kruskal p < 0.05")
    fig.suptitle(
        "Within-animal paired Δ: does tx modulate the phase step? (Kruskal by tx, within sex)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, _foot_with_n(FOOT_KR, n_map), y=-0.04)
    save_pdf_png(fig, out / "fig_session_paired_condition_kruskal")


def animal_median_novel(deltas: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × phase-step on nvl_obj: median Δ across models."""
    sub = deltas[deltas["trial"] == "nvl_obj"].copy()
    keys = ["animal_id", "sex", "condition", "session_step"]
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
    n_map: dict[str, int],
    salt: pd.DataFrame | None = None,
    salt_summary: pd.DataFrame | None = None,
    wilcoxon: str = WILCOXON_POOLED,
) -> None:
    apply_style()
    dsub = animal_median_novel(deltas)
    n_models = int(dsub["n_models"].iloc[0]) if len(dsub) else 0
    salt_on = ["animal_id", "sex", "condition", "session_step"]
    for met in VIOLIN_METRICS:
        rng = np.random.default_rng(0)
        fig_w = 7.2 * max(1.0, len(PHASE_STEPS) / 4.0)
        fig, axes = plt.subplots(1, len(PHASE_STEPS), figsize=(fig_w, 3.8), sharey=True, constrained_layout=True)
        col = DELTA_COL[met]
        med = dsub
        iqr_col = None
        if salt is not None and not salt.empty:
            s = salt
            if "trial" in s.columns:
                s = s[s["trial"] == "nvl_obj"]
            med = _attach_iqr(dsub, s, metric=col, on=salt_on)
            iqr_col = "iqr_across_models"
        for c, st in enumerate(PHASE_STEPS):
            ax = axes[c]
            panel = med[med["session_step"] == st]
            ns = _draw_condition_violins(ax, panel, col, rng, iqr_col=iqr_col)
            if c == 0:
                ax.set_ylabel("Δ (right − left)", fontsize=8)
            ax.set_title(step_axis_label(st, n_map), loc="left", fontweight="bold", color=INK, fontsize=8)
            lines = [f"paired n={n_map.get(st, '?')}"]
            lines.append("n=" + "/".join(str(n) for n in ns))
            if salt_summary is not None and not salt_summary.empty:
                srow = salt_summary[
                    (salt_summary["trial"] == "nvl_obj")
                    & (salt_summary["session_step"] == st)
                    & (salt_summary["metric"] == col)
                ]
                if len(srow) == 1:
                    lines.append(f"cohort med IQR={float(srow['median_of_iqr'].iloc[0]):.3g}")
            if wilcoxon == WILCOXON_POOLED:
                rec = wilcoxon_paired(panel[col].to_numpy(dtype=float))
                lines.append("Wilcoxon pooled " + p_text(float(rec["p"])))
            else:
                for sex in SEX_ORDER:
                    ctrl = panel[(panel["sex"] == sex) & (panel["condition"] == CONTROL_CONDITION)]
                    rec = wilcoxon_paired(ctrl[col].to_numpy(dtype=float))
                    lines.append(f"Wilcoxon noSD {sex} " + p_text(float(rec["p"])))
            k = kruskal_within_sex(
                pd.DataFrame(
                    {
                        "sex": panel["sex"].to_numpy(),
                        "condition": panel["condition"].to_numpy(),
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
            Line2D([0], [0], marker="o", color="none", markerfacecolor=CONDITION_COLOR[t], markersize=6, label=t)
            for t in CONDITION_ORDER
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
            f"nvl_obj · within-animal paired Δ of {METRIC_LAB[met]} · median across {n_models} models",
            fontsize=10,
            fontweight="bold",
            color=INK,
            y=1.16,
        )
        fig_footnote(fig, _foot_violin(wilcoxon, n_map), y=-0.12)
        save_pdf_png(fig, out / VIOLIN_STEM[met])


def fig_da_n_hit(tests: pd.DataFrame, out: Path, *, n_map: dict[str, int]) -> None:
    apply_style()
    t = tests.copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    counts = t.groupby(["model", "trial", "session_step"], as_index=False)["hit"].sum()
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, sharey=True, constrained_layout=True)
    x = np.arange(len(PHASE_STEPS))
    for ax, cond in zip(axes, TRIALS):
        ax.set_title(COND_LAB[cond], loc="left", fontweight="bold", color=INK)
        for i, st in enumerate(PHASE_STEPS):
            ys = counts[(counts["trial"] == cond) & (counts["session_step"] == st)]["hit"].to_numpy(
                dtype=float
            )
            jitter = rng.normal(0, 0.08, size=ys.size)
            ax.scatter(np.full(ys.shape, i) + jitter, ys, s=12, c="#2f5d8a", alpha=0.75, edgecolors="none")
            if ys.size:
                ax.plot([i - 0.22, i + 0.22], [np.median(ys)] * 2, color=INK, lw=1.8, zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels(step_axis_labels(n_map), fontsize=7, rotation=25, ha="right")
        ax.axhline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
        if ax is axes[0]:
            ax.set_ylabel("n FDR-hit syllables per model")
    fig.suptitle(
        "Within-animal paired DA: syllables FDR-hitting each phase step (21 models)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, _foot_with_n(FOOT_DA, n_map), y=-0.12)
    save_pdf_png(fig, out / "fig_session_paired_da_n_hit_fdr05")


def fig_da_jaccard(cons: pd.DataFrame, out: Path, *, n_map: dict[str, int]) -> None:
    apply_style()
    n_steps = len(PHASE_STEPS)
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, constrained_layout=True)
    im = None
    for ax, cond in zip(axes, TRIALS):
        sub = cons[cons["trial"] == cond]
        mat = np.full((n_steps, n_steps), np.nan)
        for i, sa in enumerate(PHASE_STEPS):
            for j, sb in enumerate(PHASE_STEPS):
                if i == j:
                    continue
                a, b = _lex_pair(sa, sb)
                rows = sub[(sub["session_step_a"] == a) & (sub["session_step_b"] == b)]
                if rows.empty:
                    continue
                mat[i, j] = float(pd.to_numeric(rows["jaccard"], errors="coerce").median())
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="equal")
        ax.set_xticks(range(n_steps))
        ax.set_xticklabels(step_axis_labels(n_map), fontsize=6.5, rotation=30, ha="right")
        ax.set_yticks(range(n_steps))
        ax.set_yticklabels(step_axis_labels(n_map), fontsize=6.5)
        ax.set_title(COND_LAB[cond], loc="left", fontweight="bold", color=INK)
        for i in range(n_steps):
            for j in range(n_steps):
                v = mat[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6, color=text_on_cmap(v))
    fig.colorbar(im, ax=axes, fraction=0.03, pad=0.02, label="median Jaccard across 21 models")
    fig.suptitle(
        "Within-animal paired DA: overlap of FDR-hit ids across phase steps (within model)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(
        fig,
        _foot_with_n(
            FOOT_DA + " CSV session_step_a/b are lexicographic; heatmaps are protocol order.",
            n_map,
        ),
        y=-0.12,
    )
    save_pdf_png(fig, out / "fig_session_paired_da_jaccard")


def fig_da_persistence(pers: pd.DataFrame, out: Path, *, model: str, n_map: dict[str, int]) -> None:
    apply_style()
    n_steps = len(PHASE_STEPS)
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, sharey=True, constrained_layout=True)
    bins = np.arange(-0.5, n_steps + 0.5, 1.0)
    for ax, cond in zip(axes, TRIALS):
        sub = pers[(pers["model"] == model) & (pers["trial"] == cond)]
        ax.hist(sub["n_hit_fdr05"].to_numpy(dtype=float), bins=bins, color="#2f5d8a", edgecolor="white", lw=0.4)
        ax.set_xticks(range(n_steps + 1))
        ax.set_title(COND_LAB[cond], loc="left", fontweight="bold", color=INK)
        ax.set_xlabel(f"n phase-steps FDR-hit (of {n_steps})")
        if ax is axes[0]:
            ax.set_ylabel("n syllables (this model)")
        n_all = int((sub["n_hit_fdr05"] == n_steps).sum())
        ax.text(
            0.96,
            0.96,
            f"n_id={len(sub)}\nn_hit={n_steps}: {n_all}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=7,
            color=MUTE,
        )
    fig.suptitle(
        f"Pilot {model}: within-animal paired DA persistence across phase steps",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.06,
    )
    fig_footnote(fig, _foot_with_n(FOOT_DA, n_map), y=-0.12)
    save_pdf_png(fig, out / "fig_session_paired_da_persistence_pilot")


def _normalize_da_axes(tests: pd.DataFrame) -> pd.DataFrame:
    """Map phase-paired columns to the ladder/volcano helpers' facet/step names."""
    t = tests.copy()
    if "session_step" in t.columns:
        t["step"] = t["session_step"]
    if "trial" in t.columns:
        t["session"] = t["trial"]
    return t


def load_or_build_condition_sex_tests(run: Path, *, rebuild: bool) -> pd.DataFrame:
    dest = run / TXSEX_TESTS
    if dest.exists() and not rebuild:
        return pd.read_csv(dest)
    delta_path = run / "session_paired_da_deltas_per_animal.csv"
    if not delta_path.exists():
        raise FileNotFoundError(
            f"Need {delta_path.name} to build tx x sex DA tests "
            "(runner: simpler_first_session_paired.py --write-da-deltas)"
        )
    print("building tx x sex Wilcoxon from per-animal delta_p (between-phase paired) ...", flush=True)
    usecols = [
        "model",
        "trial",
        "session_step",
        "animal_id",
        "sex",
        "condition",
        "raw_syllable_id",
        "p_left",
        "p_right",
        "delta_p",
        "bc_contrib_frac",
        "left",
        "right",
    ]
    dtab = pd.read_csv(delta_path, usecols=usecols)
    tests = da_tests_condition_sex_from_animal_deltas(dtab, cell_cols=DA_CELL_COLS, progress=True)
    tests.to_csv(dest, index=False)
    print(f"wrote {dest}  rows={len(tests)}", flush=True)
    return tests


def fig_volcano_condition(
    tests: pd.DataFrame,
    out: Path,
    *,
    condition: str,
    dest: str,
    xlim: tuple[float, float],
    n_map: dict[str, int],
) -> None:
    apply_style(dest=dest)
    t = _volcano_xy(tests)
    t = t[t["session"] == condition]
    fig, axes = plt.subplots(
        len(PHASE_VOLCANO_STEPS),
        3,
        figsize=(7.2, 2.6 * len(PHASE_VOLCANO_STEPS)),
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )
    miss_s = 16 if dest == "slides" else 9
    hit_s = 32 if dest == "slides" else 18
    ann = 11 if dest == "slides" else 7
    n_panels = len(PHASE_VOLCANO_STEPS) * len(CONDITION_ORDER)
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" + "abcdefghijklmnopqrstuvwxyz"
    if n_panels > len(letters):
        letters = letters + "".join(str(i) for i in range(n_panels))
    for r, (step, slab) in enumerate(PHASE_VOLCANO_STEPS):
        for c, tx in enumerate(CONDITION_ORDER):
            ax = axes[r, c]
            cell = t[(t["step"] == step) & (t["condition"] == condition)]
            n_hit = int(cell["hit"].sum())
            n_pt = int(len(cell))
            letter = letters[r * 3 + c]
            n_pair = n_map.get(step)
            n_tag = f"  n={n_pair} paired" if n_pair is not None else ""
            set_wrapped_title(
                ax,
                f"{letter}  {tx}  ·  {slab}{n_tag}",
                loc="left",
                fontweight="bold",
                color=INK,
                width=36,
            )
            color = CONDITION_COLOR[condition]
            for is_hit, s, alpha, z in (
                (False, miss_s, 0.40, 2),
                (True, hit_s, 0.90, 3),
            ):
                sub_h = cell[cell["hit"] == is_hit]
                for sex in SEX_ORDER:
                    sub = sub_h[sub_h["sex"] == sex]
                    if sub.empty:
                        continue
                    ax.scatter(
                        sub["median_delta_p"],
                        sub["neglog10_p"],
                        s=s,
                        marker=SEX_MARKER[sex],
                        facecolors=color if is_hit else "none",
                        edgecolors=color,
                        linewidths=0.6 if not is_hit else 0.4,
                        alpha=alpha,
                        zorder=z,
                    )
            ax.axvline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
            ax.set_xlim(*xlim)
            ax.set_ylim(-0.05, Y_CLIP + 0.15)
            ax.text(
                0.98,
                0.04,
                f"n={n_pt}  FDR={n_hit}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=ann,
                color=MUTE,
            )
            if r == len(PHASE_VOLCANO_STEPS) - 1:
                ax.set_xlabel("median Δp_k (frame share)")
            if c == 0:
                ax.set_ylabel("−log₁₀(p)  (clip 4)")
    ms = 8 if dest == "slides" else 6
    handles = [
        Line2D(
            [0],
            [0],
            marker=SEX_MARKER[s],
            color="none",
            markerfacecolor=INK,
            markeredgecolor=INK,
            markersize=ms,
            label=s,
        )
        for s in SEX_ORDER
    ] + [
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor="none",
            markeredgecolor=INK,
            markersize=ms,
            label="miss (open)",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=INK,
            markeredgecolor=INK,
            markersize=ms,
            label="FDR hit (filled)",
        ),
    ]
    fig.suptitle(
        f"Within-animal paired DA volcano · {COND_LAB[condition]} · tx facets · 21 alphabets overlaid",
        fontsize=16 if dest == "slides" else 11,
        fontweight="bold",
        color=INK,
    )
    foot = (
        f"{COND_LAB[condition]} only. Columns = tx; rows = phase steps (condition held). "
        + FOOT_DA_VOLCANO
    )
    if n_map:
        foot = foot + " " + footnote_paired_n(n_map)
    fig_legend_and_footnote(fig, handles, foot, dest=dest)
    save_pdf_png(fig, out / VOLCANO_STEM[condition])


def write_session_paired_volcano_ladders(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    xlim: tuple[float, float],
    cluster_lookup: dict[int, tuple[float, float, float, float]] | None = None,
    cluster_ids: list[int] | None = None,
    listed=None,
    steps: tuple[tuple[str, str], ...] | None = None,
    step_short: dict[str, str] | None = None,
    facet_col: str = "session",
    facet_tag: dict[str, str] | None = None,
    facet_label: dict[str, str] | None = None,
    stem_prefix: str = LADDER_STEM_PREFIX,
    split_by_step: bool = True,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    steps_use = steps if steps is not None else tuple((s, STEP_LAB[s]) for s in PHASE_STEPS)
    short_map = step_short if step_short is not None else STEP_LAB
    tag_map = facet_tag if facet_tag is not None else LADDER_COND_TAG
    lab_map = facet_label if facet_label is not None else COND_LAB
    models = sorted(pooled["model"].astype(str).unique())
    n_tot = len(models) * len(TRIALS) * (len(steps_use) if split_by_step else 1)
    done = 0
    for model in models:
        for cond in TRIALS:
            if split_by_step:
                for step, step_lab in steps_use:
                    done += 1
                    print(
                        f"ladder {done}/{n_tot} {lab_map[cond]} {step_lab} {model}",
                        flush=True,
                    )
                    fig_volcano_ladder_model_phase(
                        pooled,
                        strat,
                        out,
                        model=model,
                        phase=cond,
                        dest=dest,
                        xlim=xlim,
                        cluster_lookup=cluster_lookup,
                        cluster_ids=cluster_ids,
                        listed=listed,
                        steps=((step, step_lab),),
                        step_short=short_map,
                        facet_col=facet_col,
                        facet_tag=tag_map,
                        facet_label=lab_map,
                        stem_prefix=stem_prefix,
                        split_by_step=True,
                    )
            else:
                done += 1
                print(f"ladder {done}/{n_tot} {lab_map[cond]} {model}", flush=True)
                fig_volcano_ladder_model_phase(
                    pooled,
                    strat,
                    out,
                    model=model,
                    phase=cond,
                    dest=dest,
                    xlim=xlim,
                    cluster_lookup=cluster_lookup,
                    cluster_ids=cluster_ids,
                    listed=listed,
                    steps=steps_use,
                    step_short=short_map,
                    facet_col=facet_col,
                    facet_tag=tag_map,
                    facet_label=lab_map,
                    stem_prefix=stem_prefix,
                    split_by_step=False,
                )


def _volcano_step_tuples(n_map: dict[str, int]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (s, f"{STEP_LAB[s]} (n={n_map[s]} paired)" if s in n_map else STEP_LAB[s])
        for s in PHASE_STEPS
    )


def _load_pair_n_map(run: Path) -> dict[str, int]:
    p = run / "session_paired_deltas_per_animal.csv"
    if not p.exists():
        return {}
    d = pd.read_csv(p, usecols=["session_step", "animal_id"])
    return paired_n_by_step(d)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--pilot-model", type=str, default=PILOT_MODEL)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--wilcoxon",
        choices=(WILCOXON_POOLED, WILCOXON_NOSD),
        default=WILCOXON_POOLED,
        help="Violin Wilcoxon: pooled tx+sex vs noSD within sex.",
    )
    ap.add_argument(
        "--volcano-only",
        action="store_true",
        help="Write only the 3 condition overlay DA volcanos (phase steps × condition)",
    )
    ap.add_argument(
        "--rebuild-tx-sex",
        action="store_true",
        help="Recompute session_paired_da_tests_condition_sex.csv from per-animal Δp",
    )
    ap.add_argument(
        "--ladder-only",
        action="store_true",
        help="Write 21 models × 3 conditions pooled→stratified volcano ladders",
    )
    ap.add_argument(
        "--ladder-overlay-only",
        action="store_true",
        help="Write 3 condition volcano ladders with 21 models overlaid",
    )
    ap.add_argument(
        "--da-volcano-ladder-only",
        action="store_true",
        help="Volcano + per-model ladders + overlay (skip scalar/DA summary figs)",
    )
    args = ap.parse_args(argv)
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    n_map = _load_pair_n_map(run)
    da_only = args.volcano_only or args.ladder_only or args.ladder_overlay_only or args.da_volcano_ladder_only

    if da_only:
        txsex = load_or_build_condition_sex_tests(run, rebuild=args.rebuild_condition_sex)
        pooled_raw = pd.read_csv(run / "session_paired_da_tests_long.csv")
        pooled = attach_cluster_ids_to_tests(
            _normalize_da_axes(pooled_raw), args.sig_dir
        )
        strat = _normalize_da_axes(txsex)
        cluster_lookup, cluster_ids, listed = load_cluster_lookup(args.sig_dir)
        xy = pd.concat([_volcano_xy(strat), _volcano_xy(pooled)], ignore_index=True)
        xlim = _shared_volcano_xlim(xy)
        step_tuples = _volcano_step_tuples(n_map)
        ladder_kw = dict(
            dest=args.dest,
            xlim=xlim,
            cluster_lookup=cluster_lookup,
            cluster_ids=cluster_ids,
            listed=listed,
            steps=step_tuples,
            step_short={s: lab for s, lab in step_tuples},
            facet_col="session",
            facet_label=COND_LAB,
            facet_tag=LADDER_COND_TAG,
        )
        if args.volcano_only or args.da_volcano_ladder_only:
            for cond in TRIALS:
                fig_volcano_condition(
                    strat, out, condition=cond, dest=args.dest, xlim=xlim, n_map=n_map
                )
        if args.ladder_only or args.da_volcano_ladder_only:
            write_session_paired_volcano_ladders(pooled, strat, out / "volcano_ladder", **ladder_kw)
        if args.ladder_overlay_only or args.da_volcano_ladder_only:
            for cond in TRIALS:
                fig_volcano_ladder_overlay_phase(
                    pooled,
                    strat,
                    out,
                    phase=cond,
                    stem_prefix=LADDER_OVERLAY_STEM,
                    split_by_step=True,
                    panel_titles=("pooled", "stratified"),
                    suptitle_bold_facet=True,
                    step_subtitle_builder=lambda step: overlay_step_suptitle_parts(step, n_map),
                    xlabel="median Δp_k (right − left)",
                    **ladder_kw,
                )
            write_volcano_ladder_overlay_legend(
                out,
                dest=args.dest,
                stem="fig_session_paired_da_volcano_ladder_overlay_legend",
            )
        return 0

    agr = pd.read_csv(run / "session_paired_agreement_by_model.csv")
    tests = pd.read_csv(run / "session_paired_tests_long.csv")
    deltas = pd.read_csv(run / "session_paired_deltas_per_animal.csv")
    da_tests = pd.read_csv(run / "session_paired_da_tests_long.csv")
    da_cons = pd.read_csv(run / "session_paired_da_consistency_step_pairs.csv")
    da_pers = pd.read_csv(run / "session_paired_da_syllable_persistence.csv")
    salt_keys = ("animal_id", "sex", "condition", "session_step", "trial")
    salt = across_model_dispersion(deltas, keys=salt_keys)
    salt_sum = across_model_dispersion_summary(
        salt, group_keys=("trial", "session_step", "metric")
    )
    salt.to_csv(run / "session_paired_across_model_dispersion.csv", index=False)
    salt_sum.to_csv(run / "session_paired_across_model_dispersion_summary.csv", index=False)
    fig_frac_hit(agr, out, n_map=n_map)
    fig_median_delta(agr, out, n_map=n_map)
    fig_condition_kruskal(tests, out, n_map=n_map)
    fig_novel_violins(
        deltas, out, n_map=n_map, salt=salt, salt_summary=salt_sum, wilcoxon=args.wilcoxon
    )
    fig_da_n_hit(da_tests, out, n_map=n_map)
    fig_da_jaccard(da_cons, out, n_map=n_map)
    fig_da_persistence(da_pers, out, model=args.pilot_model, n_map=n_map)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
