"""DA volcano ladders colored by cross-experiment meta_cluster_id.

NOR and VAST keep their own design strips (phase/session × step); only the
kinematic colormap is shared from the meta HDBSCAN fit.

Regen:
  uv run python scratch/moseq_meta/fig_meta_da.py
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

from moseq_meta.fig_meta_syllable_signatures import add_meta_cluster_colorbar  # noqa: E402
from moseq_meta.meta_cluster_style import (  # noqa: E402
    DEFAULT_META,
    attach_meta_cluster,
    filter_da_tests_for_meta,
    load_meta_lookup,
)
from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    MUTE,
    PHASE_SHORT,
    PHASES,
    apply_style,
    fig_legend_and_footnote,
    save_pdf_png,
    tx_sex_legend_handles,
)
from nor_object_mi.fig_simpler_first_da import (  # noqa: E402
    LADDER_PHASE_TAG,
    NOISE_COLOR,
    VOLCANO_STEPS,
    Y_CLIP,
    _draw_id_ladders,
    _draw_ladder_grid,
    _scatter_pooled_squares,
    _shared_volcano_xlim,
    _stratified_xlim,
    _volcano_xy,
    load_or_build_tx_sex_tests,
)
from vast_moseq.fig_da_trial_windows import (  # noqa: E402
    PHASES as VAST_PHASES,
    _as_bool,
    _scatter_strat_cohort,
    _strat_legend_handles,
)

DEFAULT_NOR_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_VAST_DA = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\_da_trial_windows")
NOR_VOLCANO_STEPS = ("no_obj->identical", "identical->novel", "no_obj->novel")
VAST_VOLCANO_STEPS = (
    ("mid_early", "mid−early"),
    ("late_mid", "late−mid"),
    ("late_early", "late−early"),
)
VAST_SESSION_TAG = {
    "S01": "s01",
    "S02": "s02",
    "S03": "s03",
    "S04": "s04",
    "S05": "s05",
}


def _nor_overlay_legend_handles(*, dest: str) -> list[Line2D]:
    return [
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=NOISE_COLOR,
            markeredgecolor=INK,
            markersize=8 if dest == "slides" else 6,
            label="pooled square (fill = meta_cluster_id)",
        )
    ] + tx_sex_legend_handles(dest=dest)


def fig_nor_volcano_ladder_overlay_phase(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    out: Path,
    *,
    phase: str,
    dest: str,
    xlim: tuple[float, float],
    cluster_lookup: dict | None,
    cluster_ids: list[int] | None,
    listed,
    n_models: int,
) -> None:
    apply_style(dest=dest)
    p_xy = _volcano_xy(pooled[pooled["phase_layer"] == phase])
    s_xy = _volcano_xy(strat[strat["phase_layer"] == phase])
    fig, axes = plt.subplots(
        len(VOLCANO_STEPS),
        2,
        figsize=(7.2, 3.5 * len(VOLCANO_STEPS)),
        sharex="col",
        sharey=True,
        constrained_layout=True,
    )
    miss_s = 10 if dest == "slides" else 6
    hit_s = 18 if dest == "slides" else 10
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
    )
    if cluster_lookup is not None and cluster_ids is not None and listed is not None:
        add_meta_cluster_colorbar(fig, axes[0, 0], cluster_ids, listed, dest=dest)
    fig.suptitle(
        f"NOR DA · {PHASE_SHORT[phase]} · meta_cluster (K=100) · {n_models} alphabets",
        fontsize=14 if dest == "slides" else 10,
        fontweight="bold",
        color=INK,
    )
    foot = (
        f"{PHASE_SHORT[phase]} · pooled Wilcoxon (left) colored by cross-experiment meta_cluster_id. "
        "Right: tx×sex stratified fan-out (NOR design strip). Filled = BH q<0.05 in panel family. "
        "Full-session Δp: presence / novelty / span."
    )
    fig_legend_and_footnote(fig, _nor_overlay_legend_handles(dest=dest), foot, dest=dest)
    save_pdf_png(fig, out / f"fig_meta_da_nor_volcano_ladder_{LADDER_PHASE_TAG[phase]}")


def _vast_overlay_legend_handles(*, dest: str) -> list[Line2D]:
    return [
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=NOISE_COLOR,
            markeredgecolor=INK,
            markersize=8 if dest == "slides" else 6,
            label="pooled square (fill = meta_cluster_id)",
        )
    ] + _strat_legend_handles(dest=dest)


def _draw_vast_ladder_grid(
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
    cluster_lookup: dict | None,
    asterisk_pt: float,
) -> None:
    letters = "ABCDEFGHIJKL"
    for r, (step, short) in enumerate(VAST_VOLCANO_STEPS):
        letter_p = letters[2 * r]
        letter_s = letters[2 * r + 1]
        titles = (
            f"{letter_p}  {short}  ·  pooled",
            f"{letter_s}  {short}  ·  stratified",
        )
        pc = p_xy[p_xy["step"] == step]
        sc = s_xy[s_xy["step"] == step]
        ax_p = axes[r, 0]
        ax_s = axes[r, 1]
        ax_p.set_title(titles[0], loc="left", fontweight="bold", color=INK)
        ax_s.set_title(titles[1], loc="left", fontweight="bold", color=INK)
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
        _scatter_strat_cohort(ax_s, sc, pt_s=miss_s, asterisk_pt=asterisk_pt)
        ax_p.axvline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
        ax_s.axvline(0.0, color="#bbbbbb", lw=0.6, ls="--", zorder=0)
        x_use = _stratified_xlim(xlim, edge=0.15)
        ax_p.set_xlim(*x_use)
        ax_s.set_xlim(*x_use)
        ax_p.set_ylim(-0.05, Y_CLIP + 0.15)
        ax_s.set_ylim(-0.05, Y_CLIP + 0.15)
        ax_p.text(
            0.98,
            0.04,
            f"n={len(pc)}  FDR={int(pc['hit'].sum()) if len(pc) else 0}",
            transform=ax_p.transAxes,
            ha="right",
            va="bottom",
            fontsize=11 if dest == "slides" else 7,
            color=MUTE,
        )
        ax_s.text(
            0.98,
            0.04,
            f"n={len(sc)}  FDR={int(sc['hit'].sum()) if len(sc) else 0}",
            transform=ax_s.transAxes,
            ha="right",
            va="bottom",
            fontsize=11 if dest == "slides" else 7,
            color=MUTE,
        )
        if r == len(VAST_VOLCANO_STEPS) - 1:
            ax_p.set_xlabel("median Δp")
            ax_s.set_xlabel("median Δp")
        ax_p.set_ylabel("−log₁₀(p)  (clip 4)")


def fig_vast_volcano_ladder_overlay_session(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    out: Path,
    *,
    session: str,
    dest: str,
    xlim: tuple[float, float],
    cluster_lookup: dict | None,
    cluster_ids: list[int] | None,
    listed,
) -> None:
    apply_style(dest=dest)
    p_xy = _vast_volcano_xy(pooled[pooled["phase_layer"] == session])
    s_xy = _vast_volcano_xy(strat[strat["phase_layer"] == session])
    fig, axes = plt.subplots(
        len(VAST_VOLCANO_STEPS),
        2,
        figsize=(7.2, 3.5 * len(VAST_VOLCANO_STEPS)),
        sharex="col",
        sharey=True,
        constrained_layout=True,
    )
    miss_s = 10 if dest == "slides" else 6
    hit_s = 18 if dest == "slides" else 10
    ast_pt = 11 if dest == "slides" else 8
    _draw_vast_ladder_grid(
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
        asterisk_pt=ast_pt,
    )
    if cluster_lookup is not None and cluster_ids is not None and listed is not None:
        add_meta_cluster_colorbar(fig, axes[0, 0], cluster_ids, listed, dest=dest)
    fig.suptitle(
        f"VAST DA · {session} · meta_cluster · gerstner_vast_fit",
        fontsize=14 if dest == "slides" else 10,
        fontweight="bold",
        color=INK,
    )
    foot = (
        f"{session} · pooled Wilcoxon (left) colored by cross-experiment meta_cluster_id. "
        "Right: tx×sex×strain stratified fan-out (VAST design strip). Grey ghost = pooled. "
        "Filled wt / open tg; color=tx; shape=sex; * = BH q<0.05 in stratum. Trial-window Δp steps."
    )
    fig_legend_and_footnote(fig, _vast_overlay_legend_handles(dest=dest), foot, dest=dest)
    save_pdf_png(fig, out / f"fig_meta_da_vast_volcano_ladder_{VAST_SESSION_TAG[session]}")


def _vast_volcano_xy(tests: pd.DataFrame) -> pd.DataFrame:
    t = tests.copy()
    t["hit"] = _as_bool(t["hit_fdr05"]) if "hit_fdr05" in t.columns else False
    t["p"] = pd.to_numeric(t["p"], errors="coerce")
    t["median_delta_p"] = pd.to_numeric(t["median_delta_p"], errors="coerce")
    t = t[np.isfinite(t["p"]) & (t["p"] > 0) & np.isfinite(t["median_delta_p"])]
    t["neglog10_p"] = np.minimum(-np.log10(t["p"].to_numpy(dtype=float)), Y_CLIP)
    return t


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--meta-dir", type=Path, default=DEFAULT_META)
    ap.add_argument("--nor-da-dir", type=Path, default=DEFAULT_NOR_DA)
    ap.add_argument("--vast-da-dir", type=Path, default=DEFAULT_VAST_DA)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument("--rebuild-nor-tx-sex", action="store_true")
    args = ap.parse_args(argv)

    meta = args.meta_dir
    out = args.out_dir or (meta / "figures" / "da")
    nor_out = out / "nor"
    vast_out = out / "vast"
    nor_out.mkdir(parents=True, exist_ok=True)
    vast_out.mkdir(parents=True, exist_ok=True)

    lookup, cluster_ids, listed = load_meta_lookup(meta)

    txsex = load_or_build_tx_sex_tests(args.nor_da_dir, rebuild=args.rebuild_nor_tx_sex)
    pooled_nor = pd.read_csv(args.nor_da_dir / "da_syllable_tests_long.csv")
    pooled_nor = pooled_nor[pooled_nor["step"].isin(NOR_VOLCANO_STEPS)]
    pooled_nor = filter_da_tests_for_meta(pooled_nor, "nor", meta)
    txsex = filter_da_tests_for_meta(txsex, "nor", meta)
    n_nor_models = int(pooled_nor["model"].nunique())
    pooled_nor = attach_meta_cluster(pooled_nor, meta, "nor")
    txsex = attach_meta_cluster(txsex, meta, "nor")
    xy = pd.concat([_volcano_xy(txsex), _volcano_xy(pooled_nor)], ignore_index=True)
    xlim = _shared_volcano_xlim(xy)
    for ph in PHASES:
        fig_nor_volcano_ladder_overlay_phase(
            pooled_nor,
            txsex,
            nor_out,
            phase=ph,
            dest=args.dest,
            xlim=xlim,
            cluster_lookup=lookup,
            cluster_ids=cluster_ids,
            listed=listed,
            n_models=n_nor_models,
        )
    print(f"NOR meta DA ladders -> {nor_out}", flush=True)

    pooled_vast = pd.read_csv(args.vast_da_dir / "da_syllable_tests_long.csv", keep_default_na=False)
    strat_vast = pd.read_csv(args.vast_da_dir / "da_syllable_tests_strat_long.csv", keep_default_na=False)
    pooled_vast = filter_da_tests_for_meta(pooled_vast, "vast", meta)
    strat_vast = filter_da_tests_for_meta(strat_vast, "vast", meta)
    pooled_vast = attach_meta_cluster(pooled_vast, meta, "vast")
    strat_vast = attach_meta_cluster(strat_vast, meta, "vast")
    v_xy = pd.concat([_vast_volcano_xy(strat_vast), _vast_volcano_xy(pooled_vast)], ignore_index=True)
    v_xlim = _shared_volcano_xlim(v_xy)
    for session in VAST_PHASES:
        fig_vast_volcano_ladder_overlay_session(
            pooled_vast,
            strat_vast,
            vast_out,
            session=session,
            dest=args.dest,
            xlim=v_xlim,
            cluster_lookup=lookup,
            cluster_ids=cluster_ids,
            listed=listed,
        )
    print(f"VAST meta DA ladders -> {vast_out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
