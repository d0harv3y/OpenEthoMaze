"""Q5 engagement-Δ slides: object-appearance Δfrac_near by condition (NOR_TX).

Males: inverted-triangle markers (locked claim when FDR hits).
Females: circle markers (companion).

Consensus = median across 21 kpMS models per animal, then Kruskal by condition.

Regen (OpenEthoMaze repo root):

  uv run python scratch/nor_object_mi/fig_q5_engagement_delta_slide.py
  uv run python scratch/nor_object_mi/fig_q5_engagement_delta_slide.py --dest paper
  uv run python scratch/nor_object_mi/fig_q5_engagement_delta_slide.py --sex M
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    CONDITION_COLOR,
    CONDITION_ORDER,
    FIGSIZE_SLIDES,
    INK,
    MUTE,
    SEX_MARKER,
    apply_style,
    fig_legend_and_footnote,
    panel_stats_box,
    type_scale,
)

DEFAULT_RUN = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_condition_on_paired_delta"
)

STEPS = ("no_obj->id_obj", "id_obj->nvl_obj", "no_obj->nvl_obj")
STEP_LAB = {
    "no_obj->id_obj": "Presence\nno_obj → id_obj",
    "id_obj->nvl_obj": "Novelty (control)\nid_obj → nvl_obj",
    "no_obj->nvl_obj": "Span\nno_obj → nvl_obj",
}
GRAIN = "full_session"
WEIGHTING = "frame_share"
SESSION = "NOR_TX"
METRIC = "delta_frac_near"
SEX_STEM = {"M": "m", "F": "f"}
SEX_TITLE = {"M": "males", "F": "females"}
# Base was violin_scatter * 0.35; +30% → * 0.455
MARKER_SCALE = 0.35 * 1.3
LEGEND_MS = {"slides": 9 * 1.3, "paper": 7 * 1.3}


def _as_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().isin(("true", "1", "yes"))


def _consensus_animal_deltas(deltas: pd.DataFrame, *, sex: str) -> pd.DataFrame:
    """One row per animal × step: median Δ across models (matches Stage-B consensus)."""
    sub = deltas[
        (deltas["session"] == SESSION)
        & (deltas["sex"] == sex)
        & (deltas["grain"] == GRAIN)
        & (deltas["weighting"] == WEIGHTING)
        & (deltas["step"].isin(STEPS))
    ].copy()
    if sub.empty:
        raise SystemExit(f"No animal deltas for Q5 filter (sex={sex}).")
    return (
        sub.groupby(["animal_id", "condition", "step"], as_index=False)[METRIC]
        .median()
        .rename(columns={METRIC: "delta"})
    )


def _stats_for_steps(
    tests: pd.DataFrame, agreement: pd.DataFrame, *, sex: str
) -> dict[str, dict]:
    t = tests[
        (tests["session"] == SESSION)
        & (tests["sex"] == sex)
        & (tests["grain"] == GRAIN)
        & (tests["weighting"] == WEIGHTING)
        & (tests["metric"] == METRIC)
        & (tests["step"].isin(STEPS))
    ].copy()
    a = agreement[
        (agreement["session"] == SESSION)
        & (agreement["sex"] == sex)
        & (agreement["grain"] == GRAIN)
        & (agreement["weighting"] == WEIGHTING)
        & (agreement["metric"] == METRIC)
        & (agreement["step"].isin(STEPS))
    ].copy()
    out: dict[str, dict] = {}
    for step in STEPS:
        row = t[t["step"] == step]
        agr = a[a["step"] == step]
        if row.empty:
            out[step] = {
                "p": np.nan,
                "q": np.nan,
                "hit": False,
                "frac_hit": np.nan,
                "n": 0,
            }
            continue
        r = row.iloc[0]
        frac = float(agr.iloc[0]["frac_hit"]) if not agr.empty else np.nan
        out[step] = {
            "p": float(r["p"]),
            "q": float(r["q_bh"]) if pd.notna(r["q_bh"]) else np.nan,
            "hit": bool(_as_bool(pd.Series([r["hit_fdr05"]])).iloc[0]),
            "frac_hit": frac,
            "n": int(r["n"]),
            "n_noSD": int(r["n_noSD"]),
            "n_GHSD": int(r["n_GHSD"]),
            "n_RBSD": int(r["n_RBSD"]),
            "median_noSD": float(r["median_noSD"]),
            "median_GHSD": float(r["median_GHSD"]),
            "median_RBSD": float(r["median_RBSD"]),
        }
    return out


def _footnote(stats: dict[str, dict], *, sex: str) -> str:
    hits = [s for s in STEPS if stats[s]["hit"]]
    misses = [s for s in STEPS if not stats[s]["hit"]]
    hit_lab = (
        ", ".join(STEP_LAB[s].split("\n")[0].lower() for s in hits) if hits else "none"
    )
    miss_lab = (
        ", ".join(STEP_LAB[s].split("\n")[0].lower() for s in misses)
        if misses
        else "none"
    )
    marker = "inverted triangles" if sex == "M" else "circles"
    return (
        f"Grain: full_session × frame_share. Points = animals ({marker}; "
        "median Δ across 21 kpMS models). "
        "Horizontal bar = condition median. Test: Kruskal–Wallis on Δ by condition within sex; "
        "BH FDR within the consensus-animal condition-step family (INFO). "
        f"FDR hit: {hit_lab}. FDR miss: {miss_lab}. "
        "Not discrimination ratio / novel preference. Vault: Q5 Honesty Pass."
    )


def _build_figure(
    animal: pd.DataFrame,
    stats: dict[str, dict],
    *,
    sex: str,
    dest: str,
) -> Figure:
    apply_style(dest=dest)
    ts = type_scale(dest)
    figsize = FIGSIZE_SLIDES if dest == "slides" else (7.2, 3.6)
    fig, axes = plt.subplots(1, 3, figsize=figsize, sharey=True, constrained_layout=False)
    rng = np.random.default_rng(0)
    marker = SEX_MARKER[sex]
    marker_s = ts["violin_scatter"] * MARKER_SCALE

    for ax, step in zip(axes, STEPS, strict=True):
        st = stats[step]
        parts: list[np.ndarray] = []
        for i, cond in enumerate(CONDITION_ORDER):
            vals = animal.loc[
                (animal["step"] == step) & (animal["condition"] == cond), "delta"
            ].to_numpy(dtype=float)
            vals = vals[np.isfinite(vals)]
            parts.append(vals)
            if len(vals) == 0:
                continue
            jitter = rng.uniform(-0.12, 0.12, size=len(vals))
            ax.scatter(
                np.full(len(vals), i) + jitter,
                vals,
                s=marker_s,
                marker=marker,
                color=CONDITION_COLOR[cond],
                alpha=0.55,
                edgecolors="none",
                zorder=3,
            )
            ax.hlines(
                float(np.median(vals)),
                i - 0.28,
                i + 0.28,
                colors=INK,
                linewidths=2.0,
                zorder=4,
            )

        vp = ax.violinplot(
            [p if len(p) else np.array([np.nan]) for p in parts],
            positions=list(range(len(CONDITION_ORDER))),
            widths=0.7,
            showmeans=False,
            showmedians=False,
            showextrema=False,
        )
        for body, cond in zip(vp["bodies"], CONDITION_ORDER, strict=True):
            body.set_facecolor(CONDITION_COLOR[cond])
            body.set_alpha(0.25)
            body.set_edgecolor(CONDITION_COLOR[cond])

        ax.axhline(0.0, color=MUTE, lw=0.8, ls="--", zorder=1)
        ax.set_xticks(range(len(CONDITION_ORDER)))
        ax.set_xticklabels(list(CONDITION_ORDER))
        ax.set_title(STEP_LAB[step], loc="left", fontweight="bold", color=INK)
        hit_lab = "FDR hit" if st["hit"] else "FDR miss"
        q = st["q"]
        frac = st["frac_hit"]
        panel_stats_box(
            ax,
            [
                hit_lab,
                f"Kruskal p={st['p']:.3g}" if np.isfinite(st["p"]) else "p=—",
                f"q={q:.3f}" if np.isfinite(q) else "q=—",
                f"agree {frac:.0%} models" if np.isfinite(frac) else "agree —",
                f"n={st.get('n_noSD', '?')}/{st.get('n_GHSD', '?')}/{st.get('n_RBSD', '?')}",
            ],
            dest=dest,
        )

    axes[0].set_ylabel("Δ frac_near (median across 21 models)")
    fig.suptitle(
        f"Q5 · Challenge day (NOR_TX), {SEX_TITLE[sex]} — "
        "condition modulates object-appearance engagement",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
        y=0.98,
    )
    ms = LEGEND_MS[dest]
    handles = [
        Line2D(
            [0],
            [0],
            marker=marker,
            color="none",
            markerfacecolor=CONDITION_COLOR[c],
            markersize=ms,
            label=c,
        )
        for c in CONDITION_ORDER
    ]
    fig_legend_and_footnote(fig, handles, _footnote(stats, sex=sex), dest=dest)
    return fig


def _save_all(fig: Figure, stem: Path) -> None:
    """SVG for PowerPoint (text stays text); PNG raster companion. No PDF."""
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), bbox_inches="tight", dpi=300)
    plt.close(fig)
    for suffix in (".svg", ".png"):
        print(f"wrote {stem.with_suffix(suffix)}")


def _copy_vault(stem: Path) -> None:
    vault = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "vaults"
        / "nor-impress"
        / "attachments"
    )
    vault.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".svg"):
        src = stem.with_suffix(suffix)
        if src.exists():
            dest = vault / src.name
            dest.write_bytes(src.read_bytes())
            print(f"copied {dest}")


def _render_sex(
    *,
    sex: str,
    deltas: pd.DataFrame,
    tests: pd.DataFrame,
    agreement: pd.DataFrame,
    out_dir: Path,
    dest: str,
) -> Path:
    animal = _consensus_animal_deltas(deltas, sex=sex)
    stats = _stats_for_steps(tests, agreement, sex=sex)
    stem = out_dir / f"fig_q5_engagement_delta_nor_tx_{SEX_STEM[sex]}"
    fig = _build_figure(animal, stats, sex=sex, dest=dest)
    _save_all(fig, stem)
    _copy_vault(stem)
    return stem


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument("--out-dir", type=Path, default=None, help="Default: <run-dir>/figures")
    ap.add_argument(
        "--sex",
        choices=("M", "F", "both"),
        default="both",
        help="Which sex panel(s) to write (default: both)",
    )
    args = ap.parse_args()
    run = args.run_dir
    out_dir = args.out_dir or (run / "figures")
    deltas = pd.read_csv(run / "condition_scalar_condition_deltas_per_animal.csv")
    tests = pd.read_csv(run / "condition_consensus_animal_condition_tests_long.csv")
    agreement = pd.read_csv(run / "condition_scalar_condition_agreement.csv")
    sexes = ("M", "F") if args.sex == "both" else (args.sex,)
    for sex in sexes:
        _render_sex(
            sex=sex,
            deltas=deltas,
            tests=tests,
            agreement=agreement,
            out_dir=out_dir,
            dest=args.dest,
        )


if __name__ == "__main__":
    main()
