"""VAST DA figures: volcano ladders by session + pause-cluster Δp (sex-faceted).

Reads ``_da_trial_windows`` artifacts. Cohort 2×2×2 strain × tx × sex (M/F separate).

Regen:
  uv run python scratch/vast_moseq/fig_da_trial_windows.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from matplotlib.lines import Line2D  # noqa: E402

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_DOUBLE,
    INK,
    MUTE,
    SEX_MARKER,
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    type_scale,
)
from nor_object_mi.fig_simpler_first_syllable_signatures import (  # noqa: E402
    add_cluster_id_colorbar,
    build_cluster_color_lookup,
    colors_for_cluster_ids,
)

from vast_moseq.cohort_meta import STRAIN_ORDER, TX_ORDER  # noqa: E402
from vast_moseq.vast_da_strat import da_tests_cohort_strat_from_deltas  # noqa: E402

DEFAULT_DA = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\_da_trial_windows")
DEFAULT_SIG = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\syllable_signatures")

PHASES = ("S01", "S02", "S03", "S04", "S05")
STEPS = (
    ("mid_early", "mid−early"),
    ("late_mid", "late−mid"),
    ("late_early", "late−early"),
)
Y_CLIP = 4.0
GREY_SQ = "#9a9a9a"
VAST_TX_COLOR = {"RBSF-1": "#E69F00", "n/a": "#0072B2"}
STRAIN_COLOR = {"wt": "#009E73", "tg": "#CC79A7"}
TX_MARKER = {"RBSF-1": "o", "n/a": "s"}
TX_EDGE = {"RBSF-1": "#333333", "n/a": "#888888"}


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1", "yes"))


def _volcano_xy(tests: pd.DataFrame) -> pd.DataFrame:
    t = tests.copy()
    if "hit_fdr05" in t.columns:
        t["hit"] = _as_bool(t["hit_fdr05"])
    else:
        t["hit"] = False
    t["p"] = pd.to_numeric(t["p"], errors="coerce")
    t["median_delta_p"] = pd.to_numeric(t["median_delta_p"], errors="coerce")
    t = t[np.isfinite(t["p"]) & (t["p"] > 0) & np.isfinite(t["median_delta_p"])]
    t["neglog10_p"] = np.minimum(-np.log10(t["p"].to_numpy(dtype=float)), Y_CLIP)
    return t


def _attach_cluster(tests: pd.DataFrame, sig: pd.DataFrame) -> pd.DataFrame:
    out = tests.merge(
        sig[["model", "raw_syllable_id", "cluster_id"]],
        on=["model", "raw_syllable_id"],
        how="left",
    )
    out["cluster_id"] = pd.to_numeric(out["cluster_id"], errors="coerce").fillna(-1).astype(int)
    return out


def _build_cluster_lookup(sig: pd.DataFrame) -> tuple[dict[int, tuple[float, float, float, float]], list[int], object | None]:
    summary = (
        sig[sig["cluster_id"] >= 0]
        .groupby("cluster_id", as_index=False)
        .agg(n_prototypes=("raw_syllable_id", "size"))
    )
    if summary.empty:
        return {}, [], None
    lookup, cluster_ids, listed = build_cluster_color_lookup(summary)
    return lookup, cluster_ids, listed


def _scatter_pooled_cluster_squares(
    ax,
    cell: pd.DataFrame,
    *,
    lookup: dict[int, tuple[float, float, float, float]],
    miss_s: float,
    hit_s: float,
) -> None:
    """Pooled-only: edge/fill color = cluster_id heatmap; grey = noise; fill = FDR hit."""
    for is_hit, s, z in ((False, miss_s, 2), (True, hit_s, 3)):
        sub = cell[cell["hit"] == is_hit]
        if sub.empty:
            continue
        cols = colors_for_cluster_ids(sub["cluster_id"], lookup) if lookup else GREY_SQ
        ax.scatter(
            sub["median_delta_p"],
            sub["neglog10_p"],
            s=s,
            marker="s",
            facecolors=cols if is_hit else "none",
            edgecolors=cols,
            linewidths=0.65 if not is_hit else 0.45,
            alpha=0.88 if is_hit else 0.72,
            zorder=z,
            rasterized=True,
        )


def _scatter_pooled_grey_ghost(
    ax,
    cell: pd.DataFrame,
    *,
    miss_s: float,
    hit_s: float,
) -> None:
    """Stratified underlay: grey ghost squares; fill = FDR hit within pooled layer."""
    for is_hit, s, alpha, z in ((False, miss_s, 0.20, 1), (True, hit_s, 0.32, 2)):
        sub = cell[cell["hit"] == is_hit]
        if sub.empty:
            continue
        ax.scatter(
            sub["median_delta_p"],
            sub["neglog10_p"],
            s=s,
            marker="s",
            facecolors=GREY_SQ if is_hit else "none",
            edgecolors=GREY_SQ,
            linewidths=0.55 if not is_hit else 0.4,
            alpha=alpha,
            zorder=z,
            rasterized=True,
        )


def _scatter_strat_cohort(
    ax,
    cell: pd.DataFrame,
    *,
    pt_s: float,
    asterisk_pt: float,
) -> None:
    """tx=color (edge); sex=shape; fill=wt; black *=FDR q<0.05."""
    for tx in TX_ORDER:
        c = VAST_TX_COLOR[tx]
        for sex in SEX_ORDER:
            mk = SEX_MARKER[sex]
            for strain in STRAIN_ORDER:
                sub = cell[
                    (cell["tx"] == tx) & (cell["sex"] == sex) & (cell["strain"] == strain)
                ]
                if sub.empty:
                    continue
                xs = sub["median_delta_p"].to_numpy(dtype=float)
                ys = sub["neglog10_p"].to_numpy(dtype=float)
                fc = c if strain == "wt" else "none"
                ax.scatter(
                    xs,
                    ys,
                    s=pt_s,
                    marker=mk,
                    facecolors=fc,
                    edgecolors=c,
                    linewidths=0.55,
                    alpha=0.88,
                    zorder=4,
                    rasterized=True,
                )
                hits = sub[sub["hit"]]
                if hits.empty:
                    continue
                hx = hits["median_delta_p"].to_numpy(dtype=float)
                hy = hits["neglog10_p"].to_numpy(dtype=float)
                for x, y in zip(hx, hy, strict=True):
                    ax.text(
                        x,
                        y,
                        "*",
                        ha="center",
                        va="center",
                        fontsize=asterisk_pt,
                        color="#000000",
                        zorder=5,
                        clip_on=True,
                    )


def _draw_pooled_to_strat_ladders(
    ax,
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    *,
    line_alpha: float = 0.16,
    lw: float = 0.35,
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
            color="#9a9a9a",
            lw=lw,
            alpha=line_alpha,
            zorder=3,
            solid_capstyle="round",
        )


def _pooled_legend_handles(*, dest: str) -> list[Line2D]:
    ms = 8 if dest == "slides" else 6
    return [
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=GREY_SQ,
            markeredgecolor=GREY_SQ,
            markersize=ms,
            label="noise / unclustered",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor="none",
            markeredgecolor=INK,
            markersize=ms,
            label="open = not FDR",
        ),
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=INK,
            markeredgecolor=INK,
            markersize=ms,
            label="filled = FDR q<0.05",
        ),
    ]


def _strat_legend_handles(*, dest: str) -> list[Line2D]:
    ms = 8 if dest == "slides" else 6
    handles: list[Line2D] = [
        Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=GREY_SQ,
            markeredgecolor=GREY_SQ,
            markersize=ms,
            alpha=0.35,
            label="pooled ghost □",
        ),
    ]
    for tx in TX_ORDER:
        handles.append(
            Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=VAST_TX_COLOR[tx],
                markeredgecolor=VAST_TX_COLOR[tx],
                markersize=ms,
                label=f"tx={tx}",
            )
        )
    for sex in SEX_ORDER:
        handles.append(
            Line2D(
                [0],
                [0],
                marker=SEX_MARKER[sex],
                color="none",
                markerfacecolor=INK,
                markeredgecolor=INK,
                markersize=ms,
                label=f"sex={sex}",
            )
        )
    handles.extend(
        [
            Line2D(
                [0],
                [0],
                marker=SEX_MARKER["F"],
                color="none",
                markerfacecolor=VAST_TX_COLOR["RBSF-1"],
                markeredgecolor=VAST_TX_COLOR["RBSF-1"],
                markersize=ms,
                label="fill = wt",
            ),
            Line2D(
                [0],
                [0],
                marker=SEX_MARKER["F"],
                color="none",
                markerfacecolor="none",
                markeredgecolor=VAST_TX_COLOR["RBSF-1"],
                markersize=ms,
                label="open = tg",
            ),
            Line2D(
                [0],
                [0],
                marker="",
                color="none",
                label="* = FDR q<0.05",
            ),
        ]
    )
    return handles


def load_or_build_strat_tests(da: Path, *, rebuild: bool = False) -> pd.DataFrame:
    dest = da / "da_syllable_tests_strat_long.csv"
    if dest.is_file() and not rebuild:
        return pd.read_csv(dest, keep_default_na=False)
    delta_path = da / "da_syllable_deltas_per_animal.csv"
    if not delta_path.exists():
        raise FileNotFoundError(f"Need {delta_path} to build stratified DA tests")
    print("building tx×sex×strain Wilcoxon from per-animal deltas ...", flush=True)
    dtab = pd.read_csv(delta_path, keep_default_na=False)
    tests = da_tests_cohort_strat_from_deltas(dtab, progress=True)
    tests.to_csv(dest, index=False)
    print(f"wrote {dest}  rows={len(tests)}", flush=True)
    return tests


def fig_volcano_ladder_pooled_sessions(
    pooled: pd.DataFrame,
    sig: pd.DataFrame,
    out: Path,
    *,
    dest: str = "slides",
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    lookup, cluster_ids, listed = _build_cluster_lookup(sig)
    p_xy = _attach_cluster(_volcano_xy(pooled), sig)

    miss_s = 14 if dest == "slides" else 9
    hit_s = 24 if dest == "slides" else 14

    nrows, ncols = 3, 5
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(FIGSIZE_DOUBLE[0] * 1.15, FIGSIZE_DOUBLE[1] * 1.1),
        sharex=True,
        sharey=True,
    )
    for r, (step, slab) in enumerate(STEPS):
        for c, phase in enumerate(PHASES):
            ax = axes[r, c]
            pc = p_xy[(p_xy["step"] == step) & (p_xy["phase_layer"] == phase)]
            if pc.empty:
                ax.set_axis_off()
                continue
            _scatter_pooled_cluster_squares(
                ax, pc, lookup=lookup, miss_s=miss_s, hit_s=hit_s
            )
            ax.axvline(0, color=MUTE, lw=0.7, ls="--", zorder=0)
            n_fdr = int(pc["hit"].sum())
            ax.text(
                0.98,
                0.02,
                f"n={len(pc)}\nFDR={n_fdr}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=7,
                color=INK,
            )
            if r == 0:
                ax.set_title(phase, fontsize=ts["annotation"], color=INK)
            if c == 0:
                ax.set_ylabel(f"{slab}\n−log10(p)", fontsize=ts["annotation"])
            if r == nrows - 1:
                ax.set_xlabel("median Δp", fontsize=ts["annotation"])
            ax.set_ylim(-0.05, Y_CLIP + 0.12)

    fig.suptitle(
        "DA ladder · pooled · sessions as phases · 6 alphabets overlaid",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    if listed is not None and cluster_ids:
        add_cluster_id_colorbar(fig, axes[0, -1], cluster_ids, listed, dest=dest)
    fig.legend(
        handles=_pooled_legend_handles(dest=dest),
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=7,
        bbox_to_anchor=(0.5, -0.02),
    )
    fig_footnote(
        fig,
        "Pooled Wilcoxon (all animals). Square edge/fill color = HDBSCAN cluster_id (turbo); "
        "grey = noise/unclustered. Filled square = BH q<0.05 within model×session×step. Run-phase only.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / "fig_da_volcano_ladder_overlay_sessions")


def fig_volcano_ladder_stratified_sessions(
    pooled: pd.DataFrame,
    strat: pd.DataFrame,
    sig: pd.DataFrame,
    out: Path,
    *,
    dest: str = "slides",
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    p_xy = _attach_cluster(_volcano_xy(pooled), sig)
    s_xy = _attach_cluster(_volcano_xy(strat), sig)

    pt_s = 20 if dest == "slides" else 12
    ast_pt = 11 if dest == "slides" else 8

    nrows, ncols = 3, 5
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(FIGSIZE_DOUBLE[0] * 1.15, FIGSIZE_DOUBLE[1] * 1.15),
        sharex=True,
        sharey=True,
    )
    for r, (step, slab) in enumerate(STEPS):
        for c, phase in enumerate(PHASES):
            ax = axes[r, c]
            pc = p_xy[(p_xy["step"] == step) & (p_xy["phase_layer"] == phase)]
            sc = s_xy[(s_xy["step"] == step) & (s_xy["phase_layer"] == phase)]
            if pc.empty and sc.empty:
                ax.set_axis_off()
                continue
            _scatter_pooled_grey_ghost(ax, pc, miss_s=pt_s * 0.7, hit_s=pt_s * 0.85)
            _draw_pooled_to_strat_ladders(ax, pc, sc)
            _scatter_strat_cohort(ax, sc, pt_s=pt_s, asterisk_pt=ast_pt)
            ax.axvline(0, color=MUTE, lw=0.7, ls="--", zorder=0)
            n_fdr_s = int(sc["hit"].sum()) if len(sc) else 0
            ax.text(
                0.98,
                0.02,
                f"strat n={len(sc)}\nFDR={n_fdr_s}",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=6.5,
                color=INK,
            )
            if r == 0:
                ax.set_title(phase, fontsize=ts["annotation"], color=INK)
            if c == 0:
                ax.set_ylabel(f"{slab}\n−log10(p)", fontsize=ts["annotation"])
            if r == nrows - 1:
                ax.set_xlabel("median Δp", fontsize=ts["annotation"])
            ax.set_ylim(-0.05, Y_CLIP + 0.12)

    fig.suptitle(
        "DA ladder · stratified overlay · grey pooled underlay",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig.legend(
        handles=_strat_legend_handles(dest=dest),
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=7,
        bbox_to_anchor=(0.5, -0.04),
    )
    fig_footnote(
        fig,
        "Grey ghost squares = pooled Wilcoxon underlay. Overlay = tx×sex×strain Wilcoxon "
        "(color=tx, shape=sex; filled=wt, open=tg). Black * = BH q<0.05 in that stratum. "
        "Run-phase only.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / "fig_da_volcano_ladder_stratified_sessions")


def fig_cluster_delta(
    med: pd.DataFrame,
    sliced: pd.DataFrame,
    out: Path,
    *,
    cluster_id: int,
    dest: str = "slides",
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    rng = np.random.default_rng(0)
    fig, axes = plt.subplots(6, 5, figsize=(FIGSIZE_DOUBLE[0] * 1.1, FIGSIZE_DOUBLE[1] * 2.0), sharey=True)
    sex_rows = (("F", 0, 1, 2), ("M", 3, 4, 5))
    for sex, r0, r1, r2 in sex_rows:
        for r, (step, slab) in enumerate(STEPS):
            ax_row = r0 + r
            for c, phase in enumerate(PHASES):
                ax = axes[ax_row, c]
                sub = med[(med["step"] == step) & (med["phase_layer"] == phase) & (med["sex"] == sex)]
                if sub.empty:
                    ax.set_axis_off()
                    continue
                for si, strain in enumerate(("wt", "tg")):
                    for tx in ("RBSF-1", "n/a"):
                        g = sub[(sub["strain"] == strain) & (sub["tx"] == tx)]
                        if g.empty:
                            continue
                        x = np.full(len(g), si + (0.15 if tx == "n/a" else -0.15))
                        x = x + rng.normal(0, 0.04, size=len(g))
                        y = pd.to_numeric(g["delta_p"], errors="coerce")
                        half = 0.5 * pd.to_numeric(g["iqr_across_models"], errors="coerce").fillna(0)
                        ax.errorbar(
                            x,
                            y,
                            yerr=half,
                            fmt="none",
                            ecolor=MUTE,
                            elinewidth=0.6,
                            capsize=0,
                            alpha=0.45,
                            zorder=2,
                        )
                        ax.scatter(
                            x,
                            y,
                            facecolors=STRAIN_COLOR[strain],
                            edgecolors=TX_EDGE[tx],
                            marker=TX_MARKER[tx],
                            s=24 if tx == "RBSF-1" else 20,
                            alpha=0.9,
                            linewidths=0.8,
                            zorder=3,
                        )
                ax.axhline(0, color=MUTE, lw=0.7, ls="--")
                ax.set_xticks([0, 1])
                ax.set_xticklabels(["wt", "tg"], fontsize=7)
                if r == 0:
                    ax.set_title(phase, fontsize=ts["annotation"])
                if c == 0:
                    ax.set_ylabel(f"{sex} · {slab}\nΔp", fontsize=ts["annotation"])
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=STRAIN_COLOR["wt"], markeredgecolor=TX_EDGE["RBSF-1"], markersize=7, label="wt · RBSF-1"),
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=STRAIN_COLOR["wt"], markeredgecolor=TX_EDGE["n/a"], markersize=7, label="wt · n/a"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=STRAIN_COLOR["tg"], markeredgecolor=TX_EDGE["RBSF-1"], markersize=7, label="tg · RBSF-1"),
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor=STRAIN_COLOR["tg"], markeredgecolor=TX_EDGE["n/a"], markersize=7, label="tg · n/a"),
    ]
    fig.legend(handles=handles, loc="upper right", ncol=2, frameon=False, fontsize=7)
    fig.suptitle(
        f"Pause syllable Δp by session · cluster {cluster_id} (sex rows separate; fill=strain, marker=tx)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        "Points = animal median Δp across 6 alphabets. Mann–Whitney slices in companion heatmaps.",
        fontsize=ts["footnote"],
    )
    save_pdf_png(fig, out / f"fig_cluster{cluster_id}_session_delta")

    if sliced.empty:
        return
    for contrast, hold_col, hold_vals in (
        ("strain", "hold_sex", ("F", "M")),
        ("tx", "hold_sex", ("F", "M")),
    ):
        fig_h, axes_h = plt.subplots(len(STEPS), len(hold_vals), figsize=(3.2 * len(hold_vals), 2.4 * len(STEPS)))
        if len(STEPS) == 1:
            axes_h = np.asarray([axes_h])
        if len(hold_vals) == 1:
            axes_h = axes_h[:, np.newaxis]
        for i, (step, slab) in enumerate(STEPS):
            for j, hold_val in enumerate(hold_vals):
                ax = axes_h[i, j]
                sub = sliced[
                    (sliced["contrast_factor"] == contrast)
                    & (sliced["step"] == step)
                    & (sliced[hold_col] == hold_val)
                    & (sliced["hold_strain"] == "")
                    & (sliced["hold_tx"] == "")
                ]
                mat = np.full(len(PHASES), np.nan)
                for k, phase in enumerate(PHASES):
                    row = sub[sub["phase_layer"] == phase]
                    if row.empty:
                        continue
                    p = float(row.iloc[0]["p"])
                    mat[k] = -np.log10(max(p, 1e-12)) if np.isfinite(p) else np.nan
                ax.imshow(np.clip(mat, 0, 4).reshape(1, -1), aspect="auto", cmap="magma", vmin=0, vmax=4)
                for k, phase in enumerate(PHASES):
                    row = sub[sub["phase_layer"] == phase]
                    if row.empty:
                        continue
                    p = float(row.iloc[0]["p"])
                    hit = bool(row.iloc[0].get("hit_fdr05", False))
                    txt = f"{p:.3f}" if np.isfinite(p) else ""
                    if hit:
                        txt += "*"
                    ax.text(k, 0, txt, ha="center", va="center", fontsize=6, color="white")
                ax.set_yticks([])
                ax.set_xticks(range(len(PHASES)))
                ax.set_xticklabels(PHASES, fontsize=7)
                if i == 0:
                    ax.set_title(f"sex={hold_val}", fontsize=ts["annotation"])
                if j == 0:
                    ax.set_ylabel(slab, fontsize=ts["annotation"])
        fig_h.suptitle(
            f"Mann–Whitney Δp · {contrast} · cluster {cluster_id} (* BH q<0.05)",
            fontsize=ts["suptitle"],
            fontweight="bold",
        )
        save_pdf_png(fig_h, out / f"fig_cluster{cluster_id}_{contrast}_within_sex")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--pause-cluster", type=int, default=13)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    da = args.da_dir
    out = args.out_dir or (da / "figures")
    out.mkdir(parents=True, exist_ok=True)
    tests = pd.read_csv(da / "da_syllable_tests_long.csv", keep_default_na=False)
    strat = load_or_build_strat_tests(da)
    sig = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")
    fig_volcano_ladder_pooled_sessions(tests, sig, out, dest=args.dest)
    fig_volcano_ladder_stratified_sessions(tests, strat, sig, out, dest=args.dest)

    med_path = da / f"cluster{args.pause_cluster}_animal_median_delta_p.csv"
    sliced_path = da / f"cluster{args.pause_cluster}_sliced_tests.csv"
    if med_path.is_file():
        med = pd.read_csv(med_path, keep_default_na=False)
        sliced = pd.read_csv(sliced_path, keep_default_na=False) if sliced_path.is_file() else pd.DataFrame()
        if not sliced.empty:
            for col in ("hold_sex", "hold_strain", "hold_tx"):
                sliced[col] = sliced[col].fillna("")
        fig_cluster_delta(med, sliced, out, cluster_id=int(args.pause_cluster), dest=args.dest)
    print(f"wrote figures -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
