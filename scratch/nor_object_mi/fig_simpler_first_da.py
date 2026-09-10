"""Publication figures for simpler-first DA (differential abundance).

Reads only INFO_da.md artifacts except the optional per-animal deltas CSV
(298 MB; skipped). Ids are never pooled across models.

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_simpler_first_da.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.colors as mcolors
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
    SESSION_SHORT,
    SESSIONS,
    PILOT_MODEL,
    SEX_MARKER,
    SEX_ORDER,
    CONDITION_COLOR,
    CONDITION_ORDER,
    apply_style,
    fig_footnote,
    fig_legend_and_footnote,
    save_pdf_png,
    save_png,
    set_wrapped_title,
    text_on_cmap,
    condition_sex_legend_handles,
    type_scale,
    wrap_lines,
    fig_suptitle_emph,
)
from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
    NOISE_COLOR,
    add_cluster_id_colorbar,
    build_cluster_color_lookup,
    colors_for_cluster_ids,
)
from nor_object_mi.simpler_first_da import da_tests_condition_sex_from_animal_deltas  # noqa: E402

DEFAULT_RUN = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
UNMAPPED_CLUSTER = -2
UNMAPPED_COLOR = "#c8c8c8"
STEPS = (
    ("no_obj->id_obj", "presence"),
    ("id_obj->nvl_obj", "novelty"),
    ("no_obj->nvl_obj", "span"),
)
PAIR_ORDER = (
    ("NOR_BL", "NOR_TX"),
    ("NOR_TX", "NOR_REC3hr"),
    ("NOR_REC3hr", "NOR_REC11hr"),
    ("NOR_BL", "NOR_REC11hr"),
    ("NOR_BL", "NOR_REC3hr"),
    ("NOR_TX", "NOR_REC11hr"),
)
PAIR_LAB = {
    ("NOR_BL", "NOR_TX"): "BL–TX",
    ("NOR_TX", "NOR_REC3hr"): "TX–R3",
    ("NOR_REC3hr", "NOR_REC11hr"): "R3–R11",
    ("NOR_BL", "NOR_REC11hr"): "BL–R11",
    ("NOR_BL", "NOR_REC3hr"): "BL–R3",
    ("NOR_TX", "NOR_REC11hr"): "TX–R11",
}
FOOT = (
    "Grain: animal × phase × condition (full session). Primary hit: BH q < 0.05 "
    "within model × phase × step (hit_fdr05). Ids are within-model only — do not "
    "match syllable 7 across alphabets. Not Shannon. No tx-on-Δp test in this run. "
    "Per-animal Δp CSV not plotted (optional giant)."
)
MAX_LOLLIPOP = 25
VOLCANO_STEPS = (
    ("no_obj->id_obj", "A  presence  no→identical"),
    ("id_obj->nvl_obj", "B  novelty  identical→novel"),
    ("no_obj->nvl_obj", "C  span  no→novel"),
)
LADDER_STEP_SHORT = {
    "no_obj->id_obj": "presence",
    "id_obj->nvl_obj": "novelty",
    "no_obj->nvl_obj": "span",
}
VOLCANO_STEM = {
    "NOR_BL": "fig_da_volcano_bl",
    "NOR_TX": "fig_da_volcano_tx",
    "NOR_REC3hr": "fig_da_volcano_rec3",
    "NOR_REC11hr": "fig_da_volcano_rec11",
}
Y_CLIP = 4.0
TXSEX_TESTS = "da_syllable_tests_condition_sex.csv"
SEX_POOLED_TESTS = "da_syllable_tests_sex_pooled.csv"
SEX_POOLED_CELL_COLS = ("model", "session", "step", "sex")
SEX_LAB = {"F": "female", "M": "male"}
GREY_SQ = "#7a7a7a"
LADDER_PHASE_TAG = {
    "NOR_BL": "bl",
    "NOR_TX": "condition",
    "NOR_REC3hr": "rec3",
    "NOR_REC11hr": "rec11",
}


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1"))


def load_cluster_lookup(
    sig_dir: Path,
) -> tuple[dict[int, tuple[float, float, float, float]], list[int], object]:
    summary = pd.read_csv(sig_dir / "cluster_summary.csv")
    lookup, cluster_ids, listed = build_cluster_color_lookup(summary)
    lookup[UNMAPPED_CLUSTER] = mcolors.to_rgba(UNMAPPED_COLOR)
    return lookup, cluster_ids, listed


def attach_cluster_ids_to_tests(tests: pd.DataFrame, sig_dir: Path) -> pd.DataFrame:
    """Join HDBSCAN cluster_id on model × raw_syllable_id; unmapped → −2."""
    proto = pd.read_csv(
        sig_dir / "syllable_prototypes_clustered.csv",
        usecols=["model", "raw_syllable_id", "cluster_id"],
    )
    out = tests.merge(proto, on=["model", "raw_syllable_id"], how="left")
    cid = pd.to_numeric(out["cluster_id"], errors="coerce")
    out["cluster_id"] = cid.fillna(UNMAPPED_CLUSTER).astype(np.int64)
    return out


def _volcano_xy(tests: pd.DataFrame) -> pd.DataFrame:
    t = tests.copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    t["p"] = pd.to_numeric(t["p"], errors="coerce")
    t["median_delta_p"] = pd.to_numeric(t["median_delta_p"], errors="coerce")
    t = t[np.isfinite(t["p"]) & (t["p"] > 0) & np.isfinite(t["median_delta_p"])]
    t["neglog10_p"] = np.minimum(-np.log10(t["p"].to_numpy(dtype=float)), Y_CLIP)
    return t


def _shared_volcano_xlim(t: pd.DataFrame) -> tuple[float, float]:
    x = t["median_delta_p"].to_numpy(dtype=float)
    hi = float(np.nanpercentile(np.abs(x), 99.5))
    hi = max(hi, 0.02)
    return (-hi, hi)


def _stratified_xlim(xlim: tuple[float, float], *, edge: float = 0.15) -> tuple[float, float]:
    """Widen volcano x-range to at least ±edge (keep wider if data need it)."""
    lo, hi = float(xlim[0]), float(xlim[1])
    return (min(lo, -edge), max(hi, edge))


_DELTA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "step",
    "left",
    "right",
    "session",
    "raw_syllable_id",
    "p_left",
    "p_right",
    "delta_p",
    "bc_contrib_frac",
)


def _load_volcano_step_deltas(run: Path) -> pd.DataFrame:
    delta_path = run / "da_syllable_deltas_per_animal.csv"
    if not delta_path.exists():
        raise FileNotFoundError(
            f"Need {delta_path.name} to build sex-stratified DA tests (runner --write-deltas)"
        )
    dtab = pd.read_csv(delta_path, usecols=list(_DELTA_USECOLS))
    return dtab[dtab["step"].isin([s for s, _ in VOLCANO_STEPS])].copy()


def load_or_build_condition_sex_tests(run: Path, *, rebuild: bool) -> pd.DataFrame:
    dest = run / TXSEX_TESTS
    if dest.exists() and not rebuild:
        return pd.read_csv(dest)
    print("building tx-sex Wilcoxon from per-animal delta_p (presence + novelty + span) ...", flush=True)
    dtab = _load_volcano_step_deltas(run)
    tests = da_tests_condition_sex_from_animal_deltas(dtab, progress=True)
    tests.to_csv(dest, index=False)
    print(f"wrote {dest}  rows={len(tests)}", flush=True)
    return tests


def load_or_build_sex_pooled_tests(run: Path, *, rebuild: bool) -> pd.DataFrame:
    """Wilcoxon + BH within model × phase × step × sex (txs pooled; sexes separate)."""
    dest = run / SEX_POOLED_TESTS
    if dest.exists() and not rebuild:
        return pd.read_csv(dest)
    print(
        "building sex-pooled Wilcoxon from per-animal delta_p (txs mixed within sex) ...",
        flush=True,
    )
    dtab = _load_volcano_step_deltas(run)
    tests = da_tests_condition_sex_from_animal_deltas(
        dtab, cell_cols=SEX_POOLED_CELL_COLS, progress=True
    )
    tests.to_csv(dest, index=False)
    print(f"wrote {dest}  rows={len(tests)}", flush=True)
    return tests


def filter_tests_by_sex(tests: pd.DataFrame, sex: str) -> pd.DataFrame:
    if "sex" not in tests.columns:
        raise ValueError("tests table has no sex column to filter")
    out = tests[tests["sex"].astype(str) == sex].copy()
    if out.empty:
        raise ValueError(f"no rows for sex={sex!r}")
    return out


def fig_volcano_phase(
    tests: pd.DataFrame,
    out: Path,
    *,
    phase: str,
    dest: str,
    xlim: tuple[float, float],
) -> None:
    apply_style(dest=dest)
    t = _volcano_xy(tests)
    t = t[t["session"] == phase]
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 9.5), sharex=True, sharey=True, constrained_layout=True)
    miss_s = 16 if dest == "slides" else 9
    hit_s = 32 if dest == "slides" else 18
    ann = 11 if dest == "slides" else 7
    letters = "ABCDEFGHI"
    for r, (step, _slab) in enumerate(VOLCANO_STEPS):
        for c, tx in enumerate(CONDITION_ORDER):
            ax = axes[r, c]
            cell = t[(t["step"] == step) & (t["condition"] == condition)]
            n_hit = int(cell["hit"].sum())
            n_pt = int(len(cell))
            letter = letters[r * 3 + c]
            short = LADDER_STEP_SHORT[step]
            ax.set_title(f"{letter}  {tx}  ·  {short}", loc="left", fontweight="bold", color=INK)
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
            if r == len(VOLCANO_STEPS) - 1:
                ax.set_xlabel("median Δp")
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
        f"DA volcano · {SESSION_SHORT[phase]} · tx facets · sex shape · 21 alphabets overlaid",
        fontsize=16 if dest == "slides" else 11,
        fontweight="bold",
        color=INK,
    )
    foot = (
        f"{SESSION_SHORT[phase]} only. Columns = tx; rows = presence / novelty. "
        "One point = one model × syllable × sex (Wilcoxon on paired Δp inside tx × sex). "
        "Filled = BH q < 0.05 within model × phase × step × tx × sex. "
        "Not a Kruskal across tx. Ids not matched across alphabets. y = uncorrected p, clip 4."
    )
    fig_legend_and_footnote(fig, handles, foot, dest=dest)
    save_pdf_png(fig, out / VOLCANO_STEM[phase])


def _scatter_pooled_squares(
    ax,
    cell: pd.DataFrame,
    *,
    miss_s: float,
    hit_s: float,
    alpha: float = 0.9,
    cluster_lookup: dict[int, tuple[float, float, float, float]] | None = None,
) -> None:
    for is_hit, s, z in ((False, miss_s, 2), (True, hit_s, 3)):
        sub = cell[cell["hit"] == is_hit]
        if sub.empty:
            continue
        if cluster_lookup is not None and "cluster_id" in sub.columns:
            cols = colors_for_cluster_ids(sub["cluster_id"], cluster_lookup)
            ax.scatter(
                sub["median_delta_p"],
                sub["neglog10_p"],
                s=s,
                marker="s",
                facecolors=cols if is_hit else "none",
                edgecolors=cols,
                linewidths=0.7 if not is_hit else 0.45,
                alpha=alpha,
                zorder=z,
            )
        else:
            ax.scatter(
                sub["median_delta_p"],
                sub["neglog10_p"],
                s=s,
                marker="s",
                facecolors=GREY_SQ if is_hit else "none",
                edgecolors=GREY_SQ,
                linewidths=0.7,
                alpha=alpha,
                zorder=z,
            )


def _scatter_stratified(ax, cell: pd.DataFrame, *, miss_s: float, hit_s: float) -> None:
    for is_hit, s, alpha, z in (
        (False, miss_s, 0.45, 3),
        (True, hit_s, 0.92, 4),
    ):
        sub_h = cell[cell["hit"] == is_hit]
        for condition in CONDITION_ORDER:
            for sex in SEX_ORDER:
                sub = sub_h[(sub_h["condition"] == condition) & (sub_h["sex"] == sex)]
                if sub.empty:
                    continue
                c = CONDITION_COLOR[condition]
                ax.scatter(
                    sub["median_delta_p"],
                    sub["neglog10_p"],
                    s=s,
                    marker=SEX_MARKER[sex],
                    facecolors=c if is_hit else "none",
                    edgecolors=c,
                    linewidths=0.6 if not is_hit else 0.4,
                    alpha=alpha,
                    zorder=z,
                )


def _draw_id_ladders(
    ax,
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    *,
    line_alpha: float = 0.35,
    lw: float = 0.4,
) -> None:
    if pooled.empty or strat.empty:
        return
    keys = ["model", "raw_syllable_id"]
    p = pooled.drop_duplicates(keys).set_index(keys)
    for key, g in strat.groupby(keys, sort=False):
        if key not in p.index:
            continue
        x0 = float(p.loc[key, "median_delta_p"])
        y0 = float(p.loc[key, "neglog10_p"])
        xs = g["median_delta_p"].to_numpy(dtype=float)
        ys = g["neglog10_p"].to_numpy(dtype=float)
        ax.plot(
            np.column_stack([np.full(xs.shape, x0), xs]).T,
            np.column_stack([np.full(ys.shape, y0), ys]).T,
            color="#8f8f8f",
            lw=lw,
            alpha=line_alpha,
            zorder=1,
            solid_capstyle="round",
        )


def _step_stem_token(step: str) -> str:
    return step.replace("->", "-").replace(" ", "")


def _draw_ladder_row(
    ax_p,
    ax_s,
    pc: pd.DataFrame,
    sc: pd.DataFrame,
    *,
    dest: str,
    xlim: tuple[float, float],
    miss_s: float,
    hit_s: float,
    line_alpha: float,
    lw: float,
    pooled_on_right_alpha: float,
    cluster_lookup: dict[int, tuple[float, float, float, float]] | None,
    titles: tuple[str, str],
    title_width: int = 34,
    wrap_titles: bool = True,
    show_xlabel: bool = True,
    show_ylabel: bool = True,
    xlabel: str = "median Δp",
) -> None:
    title_kw = dict(loc="left", fontweight="bold", color=INK)
    if wrap_titles:
        set_wrapped_title(ax_p, titles[0], width=title_width, **title_kw)
        set_wrapped_title(ax_s, titles[1], width=title_width, **title_kw)
    else:
        ax_p.set_title(titles[0], **title_kw)
        ax_s.set_title(titles[1], **title_kw)
    _scatter_pooled_squares(ax_p, pc, miss_s=miss_s, hit_s=hit_s, cluster_lookup=cluster_lookup)
    _draw_id_ladders(ax_s, pc, sc, line_alpha=line_alpha, lw=lw)
    _scatter_pooled_squares(
        ax_s,
        pc,
        miss_s=miss_s * 0.7,
        hit_s=hit_s * 0.7,
        alpha=pooled_on_right_alpha,
        cluster_lookup=None,
    )
    _scatter_stratified(ax_s, sc, miss_s=miss_s, hit_s=hit_s)
    ax_p.axvline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
    ax_s.axvline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
    x_use = _stratified_xlim(xlim, edge=0.15)
    ax_p.set_xlim(*x_use)
    ax_s.set_xlim(*x_use)
    ax_p.set_ylim(-0.05, Y_CLIP + 0.15)
    ax_s.set_ylim(-0.05, Y_CLIP + 0.15)
    ann = 11 if dest == "slides" else 7
    ax_p.text(
        0.98,
        0.04,
        f"n={len(pc)}  FDR={int(pc['hit'].sum()) if len(pc) else 0}",
        transform=ax_p.transAxes,
        ha="right",
        va="bottom",
        fontsize=ann,
        color=MUTE,
    )
    ax_s.text(
        0.98,
        0.04,
        f"n={len(sc)}  FDR={int(sc['hit'].sum()) if len(sc) else 0}",
        transform=ax_s.transAxes,
        ha="right",
        va="bottom",
        fontsize=ann,
        color=MUTE,
    )
    if show_xlabel:
        ax_p.set_xlabel(xlabel)
        ax_s.set_xlabel(xlabel)
    if show_ylabel:
        ax_p.set_ylabel("−log₁₀(p)  (clip 4)")


def fig_volcano_ladder_model_phase(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    out: Path,
    *,
    model: str,
    phase: str,
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
    stem_prefix: str = "fig_da_volcano_ladder",
    split_by_step: bool = False,
) -> None:
    apply_style(dest=dest)
    steps_use = steps if steps is not None else VOLCANO_STEPS
    tag_map = facet_tag if facet_tag is not None else LADDER_PHASE_TAG
    lab_map = facet_label if facet_label is not None else SESSION_SHORT
    p_xy = _volcano_xy(pooled[(pooled["model"] == model) & (pooled[facet_col] == phase)])
    s_xy = _volcano_xy(strat[(strat["model"] == model) & (strat[facet_col] == phase)])
    miss_s = 14 if dest == "slides" else 8
    hit_s = 26 if dest == "slides" else 14
    short_map = step_short if step_short is not None else LADDER_STEP_SHORT
    foot = (
        f"{lab_map[phase]} · one alphabet. Left: pooled Wilcoxon (txs mixed, sex=all); "
        "square color = HDBSCAN cluster_id (turbo). Right: same id fans to tx×sex (color=tx, shape=sex); "
        "line = pooled → stratum. Filled = BH q < 0.05 in that panel's family. "
        "Light grey = not in signature table. Not a Kruskal across tx. y clip 4."
    )
    handles = [
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=NOISE_COLOR,
            markeredgecolor=INK,
            markersize=8 if dest == "slides" else 6,
            label="pooled square (fill = cluster_id)",
        )
    ] + condition_sex_legend_handles(dest=dest)

    def _save_one_step(step: str, step_lab: str, ax_p, ax_s) -> None:
        pc = p_xy[p_xy["step"] == step]
        sc = s_xy[s_xy["step"] == step]
        _draw_ladder_row(
            ax_p,
            ax_s,
            pc,
            sc,
            dest=dest,
            xlim=xlim,
            miss_s=miss_s,
            hit_s=hit_s,
            line_alpha=0.35,
            lw=0.55,
            pooled_on_right_alpha=0.55,
            cluster_lookup=cluster_lookup,
            titles=(f"A  {step_lab}  ·  pooled", f"B  {step_lab}  ·  stratified"),
        )

    if split_by_step:
        for step, step_lab in steps_use:
            short = step_lab if step_lab else short_map.get(step, step)
            fig, axes = plt.subplots(
                1,
                2,
                figsize=(7.2, 3.5),
                sharex=True,
                sharey=True,
                constrained_layout=True,
            )
            _save_one_step(step, short, axes[0], axes[1])
            if cluster_lookup is not None and cluster_ids is not None and listed is not None:
                add_cluster_id_colorbar(fig, axes[0], cluster_ids, listed, dest=dest)
            fig.suptitle(
                wrap_lines(
                    f"DA ladder · {lab_map[phase]} · {model}\n{short}",
                    width=52,
                ),
                fontsize=14 if dest == "slides" else 10,
                fontweight="bold",
                color=INK,
            )
            fig_legend_and_footnote(fig, handles, foot, dest=dest)
            stem = f"{stem_prefix}_{tag_map[phase]}_{model}_{_step_stem_token(step)}"
            save_pdf_png(fig, out / stem)
        return

    fig, axes = plt.subplots(
        len(steps_use),
        2,
        figsize=(7.2, 3.5 * len(steps_use)),
        sharex="col",
        sharey=True,
        constrained_layout=True,
    )
    _draw_ladder_grid(
        axes,
        p_xy,
        s_xy,
        dest=dest,
        xlim=xlim,
        miss_s=miss_s,
        hit_s=hit_s,
        line_alpha=0.35,
        lw=0.55,
        pooled_on_right_alpha=0.55,
        cluster_lookup=cluster_lookup,
        steps=steps_use,
        step_short=step_short,
    )
    if cluster_lookup is not None and cluster_ids is not None and listed is not None:
        add_cluster_id_colorbar(fig, axes[0, 0], cluster_ids, listed, dest=dest)
    fig.suptitle(
        wrap_lines(f"DA ladder · {lab_map[phase]} · {model}", width=52),
        fontsize=14 if dest == "slides" else 10,
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, handles, foot, dest=dest)
    stem = f"{stem_prefix}_{tag_map[phase]}_{model}"
    save_pdf_png(fig, out / stem)


def _draw_ladder_grid(
    axes,
    p_xy: pd.DataFrame,
    s_xy: pd.DataFrame,
    *,
    dest: str,
    xlim: tuple[float, float],
    miss_s: float,
    hit_s: float,
    line_alpha: float,
    lw: float,
    pooled_on_right_alpha: float,
    cluster_lookup: dict[int, tuple[float, float, float, float]] | None = None,
    steps: tuple[tuple[str, str], ...] | None = None,
    step_short: dict[str, str] | None = None,
) -> None:
    steps_use = steps if steps is not None else VOLCANO_STEPS
    short_map = step_short if step_short is not None else LADDER_STEP_SHORT
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for r, (step, step_lab) in enumerate(steps_use):
        short = step_lab if step_lab else short_map.get(step, step)
        letter_p = letters[2 * r] if 2 * r < len(letters) else str(2 * r)
        letter_s = letters[2 * r + 1] if 2 * r + 1 < len(letters) else str(2 * r + 1)
        titles = (
            f"{letter_p}  {short}  ·  pooled",
            f"{letter_s}  {short}  ·  stratified",
        )
        pc = p_xy[p_xy["step"] == step]
        sc = s_xy[s_xy["step"] == step]
        ax_p = axes[r, 0]
        ax_s = axes[r, 1]
        _draw_ladder_row(
            ax_p,
            ax_s,
            pc,
            sc,
            dest=dest,
            xlim=xlim,
            miss_s=miss_s,
            hit_s=hit_s,
            line_alpha=line_alpha,
            lw=lw,
            pooled_on_right_alpha=pooled_on_right_alpha,
            cluster_lookup=cluster_lookup,
            titles=titles,
            show_xlabel=(r == len(steps_use) - 1),
            show_ylabel=(r == 0),
        )
        if r != 0:
            ax_p.set_ylabel("")


_draw_ladder_2x2 = _draw_ladder_grid  # backward alias

def _overlay_legend_handles(*, dest: str, sexes: tuple[str, ...] | None = None) -> list:
    sexes_use = sexes if sexes is not None else SEX_ORDER
    return [
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=NOISE_COLOR,
            markeredgecolor=INK,
            markersize=8 if dest == "slides" else 6,
            label="pooled square (fill = cluster_id)",
        )
    ] + [
        Line2D([0], [0], marker="o", color="none", markerfacecolor=CONDITION_COLOR[t], markersize=8 if dest == "slides" else 6, label=t)
        for t in CONDITION_ORDER
    ] + [
        Line2D(
            [0],
            [0],
            marker=SEX_MARKER[s],
            color="none",
            markerfacecolor=INK,
            markersize=8 if dest == "slides" else 6,
            label=s,
        )
        for s in sexes_use
    ]


def write_volcano_ladder_overlay_legend(
    out: Path,
    *,
    dest: str,
    stem: str = "fig_da_volcano_ladder_overlay_legend",
    sexes: tuple[str, ...] | None = None,
) -> None:
    """Single SVG legend for overlay PNGs (PowerPoint paste separately)."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    handles = _overlay_legend_handles(dest=dest, sexes=sexes)
    fig = plt.figure(figsize=(7.2, 0.85))
    fig.legend(
        handles=handles,
        loc="center",
        frameon=False,
        fontsize=ts["legend"],
        ncol=5,
    )
    path = out / stem
    fig.savefig(path.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {path.with_suffix('.svg')}", flush=True)


def fig_volcano_ladder_overlay_phase(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    out: Path,
    *,
    phase: str,
    dest: str,
    xlim: tuple[float, float],
    cluster_lookup: dict[int, tuple[float, float, float, float]] | None = None,
    cluster_ids: list[int] | None = None,
    listed=None,
    steps: tuple[tuple[str, str], ...] | None = None,
    step_short: dict[str, str] | None = None,
    facet_col: str = "session",
    facet_label: dict[str, str] | None = None,
    facet_tag: dict[str, str] | None = None,
    stem_prefix: str = "fig_da_volcano_ladder_overlay",
    split_by_step: bool = False,
    panel_titles: tuple[str, str] | None = None,
    suptitle_bold_facet: bool = False,
    step_subtitle_builder=None,
    xlabel: str = "median Δp",
    sex_label: str | None = None,
) -> None:
    """Overlay ladder as PNG only (no legend/footnote — PPT paste + type footnote)."""
    apply_style(dest=dest)
    steps_use = steps if steps is not None else VOLCANO_STEPS
    lab_map = facet_label if facet_label is not None else SESSION_SHORT
    tag_map = facet_tag if facet_tag is not None else LADDER_PHASE_TAG
    short_map = step_short if step_short is not None else LADDER_STEP_SHORT
    p_xy = _volcano_xy(pooled[pooled[facet_col] == phase])
    s_xy = _volcano_xy(strat[strat[facet_col] == phase])
    miss_s = 10 if dest == "slides" else 6
    hit_s = 18 if dest == "slides" else 10
    sex_tag = f" · {sex_label} only" if sex_label else ""
    ids_note = " (ids not matched)" if sex_label is None else ""

    def _draw_pair(fig, ax_p, ax_s, step: str, step_lab: str) -> None:
        pc = p_xy[p_xy["step"] == step]
        sc = s_xy[s_xy["step"] == step]
        if panel_titles is not None:
            titles = panel_titles
        else:
            titles = (f"A  {step_lab}  ·  pooled", f"B  {step_lab}  ·  stratified")
        _draw_ladder_row(
            ax_p,
            ax_s,
            pc,
            sc,
            dest=dest,
            xlim=xlim,
            miss_s=miss_s,
            hit_s=hit_s,
            line_alpha=0.18,
            lw=0.5,
            pooled_on_right_alpha=0.28,
            cluster_lookup=cluster_lookup,
            titles=titles,
            wrap_titles=panel_titles is None,
            xlabel=xlabel,
        )

    if split_by_step:
        for step, step_lab in steps_use:
            short = step_lab if step_lab else short_map.get(step, step)
            fig, axes = plt.subplots(
                1,
                2,
                figsize=(7.2, 3.5),
                sharex=True,
                sharey=True,
                constrained_layout=True,
            )
            engine = fig.get_layout_engine()
            if engine is not None:
                engine.set(h_pad=0.04, w_pad=0.04, rect=(0.0, 0.02, 1.0, 0.94))
            _draw_pair(fig, axes[0], axes[1], step, short)
            if cluster_lookup is not None and cluster_ids is not None and listed is not None:
                add_cluster_id_colorbar(fig, axes[0], cluster_ids, listed, dest=dest)
            fs = 14 if dest == "slides" else 10
            if suptitle_bold_facet:
                sub_kw: dict[str, object] = dict(
                    before="DA ladder · ",
                    emph=lab_map[phase],
                    after=f"{sex_tag} · 21 alphabets overlaid{ids_note}",
                    fontsize=fs,
                    wrap=False,
                )
                if step_subtitle_builder is not None:
                    sub_emph, sub_after = step_subtitle_builder(step)
                    sub_kw["subtitle_emph"] = sub_emph
                    sub_kw["subtitle_after"] = sub_after
                else:
                    sub_kw["subtitle"] = short
                fig_suptitle_emph(fig, **sub_kw)
            else:
                fig.suptitle(
                    wrap_lines(
                        f"DA ladder · {lab_map[phase]}{sex_tag} · 21 alphabets overlaid{ids_note}\n{short}",
                        width=52,
                    ),
                    fontsize=fs,
                    fontweight="bold",
                    color=INK,
                )
            save_png(
                fig,
                out / f"{stem_prefix}_{tag_map[phase]}_{_step_stem_token(step)}",
            )
        return

    fig, axes = plt.subplots(
        len(steps_use),
        2,
        figsize=(7.2, 3.5 * len(steps_use)),
        sharex="col",
        sharey=True,
        constrained_layout=True,
    )
    engine = fig.get_layout_engine()
    if engine is not None:
        engine.set(h_pad=0.04, w_pad=0.04, rect=(0.0, 0.02, 1.0, 0.94))
    _draw_ladder_grid(
        axes,
        p_xy,
        s_xy,
        dest=dest,
        xlim=xlim,
        miss_s=miss_s,
        hit_s=hit_s,
        line_alpha=0.18,
        lw=0.5,
        pooled_on_right_alpha=0.28,
        cluster_lookup=cluster_lookup,
        steps=steps_use,
        step_short=step_short,
    )
    if cluster_lookup is not None and cluster_ids is not None and listed is not None:
        add_cluster_id_colorbar(fig, axes[:, 0], cluster_ids, listed, dest=dest)
    fig.suptitle(
        wrap_lines(
            f"DA ladder · {lab_map[phase]}{sex_tag} · 21 alphabets overlaid{ids_note}",
            width=52,
        ),
        fontsize=14 if dest == "slides" else 10,
        fontweight="bold",
        color=INK,
    )
    save_png(fig, out / f"{stem_prefix}_{tag_map[phase]}")


def write_volcano_ladders(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    xlim: tuple[float, float],
    cluster_lookup: dict[int, tuple[float, float, float, float]] | None = None,
    cluster_ids: list[int] | None = None,
    listed=None,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    models = sorted(pooled["model"].astype(str).unique())
    n_tot = len(models) * len(SESSIONS)
    done = 0
    for model in models:
        for phase in SESSIONS:
            done += 1
            print(f"ladder {done}/{n_tot} {SESSION_SHORT[phase]} {model}", flush=True)
            fig_volcano_ladder_model_phase(
                pooled,
                strat,
                out,
                model=model,
                phase=phase,
                dest=dest,
                xlim=xlim,
                cluster_lookup=cluster_lookup,
                cluster_ids=cluster_ids,
                listed=listed,
            )


def fig_n_hit(tests: pd.DataFrame, out: Path) -> None:
    apply_style()
    t = tests.copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    counts = t.groupby(["model", "session", "step"], as_index=False)["hit"].sum()
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, sharey=True, constrained_layout=True)
    x = np.arange(len(SESSIONS))
    for ax, (step, lab) in zip(axes, STEPS):
        ax.set_title(lab, loc="left", fontweight="bold", color=INK)
        for i, ph in enumerate(SESSIONS):
            ys = counts[(counts["step"] == step) & (counts["session"] == ph)]["hit"].to_numpy(dtype=float)
            jitter = rng.normal(0, 0.08, size=ys.size)
            ax.scatter(np.full(ys.shape, i) + jitter, ys, s=12, c="#2f5d8a", alpha=0.75, edgecolors="none")
            if ys.size:
                ax.plot([i - 0.22, i + 0.22], [np.median(ys)] * 2, color=INK, lw=1.8, zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels([SESSION_SHORT[p] for p in SESSIONS])
        ax.axhline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
        if ax is axes[0]:
            ax.set_ylabel("n FDR-hit syllables per model")
    fig.suptitle(
        "How many syllables FDR-hit the paired step? (21 models; BH within cell)",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.05,
    )
    fig_footnote(fig, FOOT, y=-0.10)
    save_pdf_png(fig, out / "fig_da_n_hit_fdr05")


def fig_lollipop_pilot(tests: pd.DataFrame, out: Path, *, model: str) -> None:
    apply_style()
    t = tests[tests["model"] == model].copy()
    t["hit"] = _as_bool(t["hit_fdr05"])
    fig, axes = plt.subplots(3, 4, figsize=(7.2, 8.4), constrained_layout=True)
    for r, (step, lab) in enumerate(STEPS):
        for c, ph in enumerate(SESSIONS):
            ax = axes[r, c]
            cell = t[(t["step"] == step) & (t["session"] == ph) & (t["hit"])]
            n_hit = int(len(cell))
            if n_hit == 0:
                ax.text(0.5, 0.5, "0 FDR hits", ha="center", va="center", color=MUTE, fontsize=8)
                ax.set_axis_off()
            else:
                cell = cell.assign(abs_d=cell["median_delta_p"].abs())
                shown = cell.sort_values("abs_d", ascending=False).head(MAX_LOLLIPOP)
                shown = shown.sort_values("median_delta_p")
                y = np.arange(len(shown))
                d = shown["median_delta_p"].to_numpy(dtype=float)
                ax.hlines(y, 0.0, d, color="#8a8a8a", lw=0.7)
                ax.scatter(d, y, s=9, c=np.where(d >= 0, "#2f5d8a", "#8a4f3d"), edgecolors="none", zorder=2)
                ax.axvline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
                ax.set_yticks(y)
                ax.set_yticklabels([str(int(i)) for i in shown["raw_syllable_id"]], fontsize=5.5)
                extra = n_hit - len(shown)
                note = f"n_hit={n_hit}" + (f"  top {len(shown)} |Δp|" if extra > 0 else "")
                ax.text(0.02, 0.98, note, transform=ax.transAxes, va="top", fontsize=6, color=MUTE)
            if r == 0:
                ax.set_title(SESSION_SHORT[ph], loc="left", fontweight="bold", color=INK, fontsize=8)
            if c == 0:
                ax.set_ylabel(lab + "\nid", fontsize=7)
            if r == 2:
                ax.set_xlabel("median Δp", fontsize=7)
    fig.suptitle(
        f"Pilot {model}: FDR-hit syllables (lollipop of median Δp; ids not portable)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.02,
    )
    fig_footnote(fig, FOOT, y=-0.03)
    save_pdf_png(fig, out / "fig_da_lollipop_pilot")


def fig_jaccard(cons: pd.DataFrame, out: Path) -> None:
    apply_style()
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 6.4), constrained_layout=True)
    # row 0: median Jaccard across 21 models (symmetric 4×4)
    for c, (step, lab) in enumerate(STEPS):
        ax = axes[0, c]
        sub = cons[cons["step"] == step]
        mat = np.full((4, 4), np.nan)
        for i, pa in enumerate(SESSIONS):
            for j, pb in enumerate(SESSIONS):
                if i == j:
                    continue
                a, b = (pa, pb) if pa < pb else (pb, pa)  # table stores lex order
                rows = sub[(sub["session_a"] == a) & (sub["session_b"] == b)]
                if rows.empty:
                    continue
                mat[i, j] = float(pd.to_numeric(rows["jaccard"], errors="coerce").median())
        im = ax.imshow(mat, cmap="viridis", vmin=0.0, vmax=1.0, aspect="equal")
        ax.set_xticks(range(4))
        ax.set_xticklabels([SESSION_SHORT[p] for p in SESSIONS], fontsize=7)
        ax.set_yticks(range(4))
        ax.set_yticklabels([SESSION_SHORT[p] for p in SESSIONS], fontsize=7)
        ax.set_title("A–C  Median Jaccard  ·  " + lab, loc="left", fontweight="bold", color=INK, fontsize=8)
        for i in range(4):
            for j in range(4):
                v = mat[i, j]
                if np.isfinite(v):
                    ax.text(
                        j,
                        i,
                        f"{v:.2f}",
                        ha="center",
                        va="center",
                        fontsize=6,
                        color=text_on_cmap(v),
                    )
    fig.colorbar(im, ax=axes[0, :].ravel().tolist(), fraction=0.03, pad=0.02, label="median Jaccard across 21 models")

    # row 1: 21-model strip of Jaccard for protocol-adjacent pairs + span
    show_pairs = PAIR_ORDER[:4]
    rng = np.random.default_rng(0)
    for c, (step, lab) in enumerate(STEPS):
        ax = axes[1, c]
        sub = cons[cons["step"] == step]
        for i, (pa, pb) in enumerate(show_pairs):
            a, b = (pa, pb) if pa < pb else (pb, pa)
            ys = pd.to_numeric(
                sub[(sub["session_a"] == a) & (sub["session_b"] == b)]["jaccard"],
                errors="coerce",
            ).to_numpy(dtype=float)
            ys = ys[np.isfinite(ys)]
            jitter = rng.normal(0, 0.07, size=ys.size)
            ax.scatter(np.full(ys.shape, i) + jitter, ys, s=10, c="#2f5d8a", alpha=0.75, edgecolors="none")
            if ys.size:
                ax.plot([i - 0.2, i + 0.2], [np.median(ys)] * 2, color=INK, lw=1.6, zorder=3)
        ax.set_xticks(range(len(show_pairs)))
        ax.set_xticklabels([PAIR_LAB[p] for p in show_pairs], fontsize=6.5, rotation=25, ha="right")
        ax.set_ylim(-0.05, 1.05)
        ax.set_title("D–F  Per-model Jaccard  ·  " + lab, loc="left", fontweight="bold", color=INK, fontsize=8)
        if c == 0:
            ax.set_ylabel("Jaccard of FDR-hit sets")
    fig.suptitle(
        "Within-model FDR-hit overlap across phases (Jaccard; ids not compared across models)",
        fontsize=10,
        fontweight="bold",
        color=INK,
        y=1.03,
    )
    fig_footnote(
        fig,
        FOOT + " session_a/b in the CSV are lexicographic; heatmaps are protocol order.",
        y=-0.04,
    )
    save_pdf_png(fig, out / "fig_da_jaccard")


def fig_persistence(pers: pd.DataFrame, out: Path, *, model: str) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 3, figsize=FIGSIZE_DOUBLE, sharey=True, constrained_layout=True)
    bins = np.arange(-0.5, 5.5, 1.0)
    for ax, (step, lab) in zip(axes, STEPS):
        sub = pers[(pers["model"] == model) & (pers["step"] == step)]
        ax.hist(sub["n_hit_fdr05"].to_numpy(dtype=float), bins=bins, color="#2f5d8a", edgecolor="white", lw=0.4)
        ax.set_xticks([0, 1, 2, 3, 4])
        ax.set_title(lab, loc="left", fontweight="bold", color=INK)
        ax.set_xlabel("n phases FDR-hit (of 4)")
        if ax is axes[0]:
            ax.set_ylabel("n syllables (this model)")
        n4 = int((sub["n_hit_fdr05"] == 4).sum())
        ax.text(0.96, 0.96, f"n_id={len(sub)}\nn_hit=4: {n4}", transform=ax.transAxes, ha="right", va="top", fontsize=7, color=MUTE)
    fig.suptitle(
        f"Pilot {model}: does the same id keep FDR-hitting across NOR phases?",
        fontsize=11,
        fontweight="bold",
        color=INK,
        y=1.05,
    )
    fig_footnote(fig, FOOT, y=-0.10)
    save_pdf_png(fig, out / "fig_da_persistence_pilot")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--pilot-model", type=str, default=PILOT_MODEL)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--volcano-only",
        action="store_true",
        help="Write only the 4 phase overlay volcanos (presence / novelty / span)",
    )
    ap.add_argument(
        "--rebuild-tx-sex",
        action="store_true",
        help="Recompute da_syllable_tests_condition_sex.csv from per-animal Δp",
    )
    ap.add_argument(
        "--ladder-only",
        action="store_true",
        help="Write 21 models × 4 phases pooled→stratified volcano ladders",
    )
    ap.add_argument(
        "--ladder-overlay-only",
        action="store_true",
        help="Write 4 phase volcano ladders with 21 models overlaid (presence / novelty / span)",
    )
    ap.add_argument(
        "--ladder-overlay-by-sex",
        action="store_true",
        help=(
            "Write sex-separated overlay ladders: pooled = Wilcoxon within sex (txs mixed); "
            "stratified = tx strata for that sex only. Stems …_overlay_{F,M}_{bl,tx,rec3,rec11}"
        ),
    )
    ap.add_argument(
        "--rebuild-sex-pooled",
        action="store_true",
        help="Recompute da_syllable_tests_sex_pooled.csv from per-animal Δp",
    )
    args = ap.parse_args(argv)
    run = args.run_dir
    out = args.out_dir or (run / "figures")
    out.mkdir(parents=True, exist_ok=True)
    cluster_lookup, cluster_ids, listed = load_cluster_lookup(args.sig_dir)

    if args.ladder_overlay_by_sex:
        txsex = load_or_build_condition_sex_tests(run, rebuild=args.rebuild_condition_sex)
        sex_pooled = load_or_build_sex_pooled_tests(run, rebuild=args.rebuild_sex_pooled)
        for sex in SEX_ORDER:
            pooled_s = attach_cluster_ids_to_tests(filter_tests_by_sex(sex_pooled, sex), args.sig_dir)
            strat_s = filter_tests_by_sex(txsex, sex)
            xy = pd.concat([_volcano_xy(strat_s), _volcano_xy(pooled_s)], ignore_index=True)
            xlim = _shared_volcano_xlim(xy)
            sex_lab = SEX_LAB[sex]
            print(f"overlay ladders · {sex_lab} only ...", flush=True)
            for ph in SESSIONS:
                fig_volcano_ladder_overlay_phase(
                    pooled_s,
                    strat_s,
                    out,
                    phase=ph,
                    dest=args.dest,
                    xlim=xlim,
                    cluster_lookup=cluster_lookup,
                    cluster_ids=cluster_ids,
                    listed=listed,
                    stem_prefix=f"fig_da_volcano_ladder_overlay_{sex}",
                    sex_label=sex_lab,
                )
            write_volcano_ladder_overlay_legend(
                out,
                dest=args.dest,
                stem=f"fig_da_volcano_ladder_overlay_legend_{sex}",
                sexes=(sex,),
            )
        return 0

    txsex = load_or_build_condition_sex_tests(run, rebuild=args.rebuild_condition_sex)
    tests_all = pd.read_csv(run / "da_syllable_tests_long.csv")
    step_keep = [s for s, _ in VOLCANO_STEPS]
    pooled = tests_all[tests_all["step"].isin(step_keep)]
    pooled = attach_cluster_ids_to_tests(pooled, args.sig_dir)
    if args.ladder_only or args.ladder_overlay_only:
        xy = pd.concat([_volcano_xy(txsex), _volcano_xy(pooled)], ignore_index=True)
        xlim = _shared_volcano_xlim(xy)
        if args.ladder_overlay_only:
            for ph in SESSIONS:
                fig_volcano_ladder_overlay_phase(
                    pooled,
                    txsex,
                    out,
                    phase=ph,
                    dest=args.dest,
                    xlim=xlim,
                    cluster_lookup=cluster_lookup,
                    cluster_ids=cluster_ids,
                    listed=listed,
                )
            write_volcano_ladder_overlay_legend(out, dest=args.dest)
            return 0
        write_volcano_ladders(
            pooled,
            txsex,
            out / "volcano_ladder",
            dest=args.dest,
            xlim=xlim,
            cluster_lookup=cluster_lookup,
            cluster_ids=cluster_ids,
            listed=listed,
        )
        return 0
    xy = _volcano_xy(txsex)
    xlim = _shared_volcano_xlim(xy)
    for ph in SESSIONS:
        fig_volcano_phase(txsex, out, phase=ph, dest=args.dest, xlim=xlim)
    if args.volcano_only:
        return 0
    cons = pd.read_csv(run / "da_consistency_phase_pairs.csv")
    pers = pd.read_csv(run / "da_syllable_phase_persistence.csv")
    fig_n_hit(tests_all, out)
    fig_lollipop_pilot(tests_all, out, model=args.pilot_model)
    fig_jaccard(cons, out)
    fig_persistence(pers, out, model=args.pilot_model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
