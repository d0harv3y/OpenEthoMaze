"""Scalar mean-model Kruskal overview (sex × step/condition × phase).

Rows = frac_near / mean_dist / richness / shannon (paired Δ).
Cell = mean uncorrected Kruskal p across models; * = majority BH across models in cell.

Regen:
  uv run python scratch/nor_object_mi/fig_scalar_tx_kruskal_mean_model_p.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    INK,
    MUTE,
    SESSION_SHORT,
    SESSIONS,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster_tx_kruskal_phase_paired import PHASE_STEPS
from nor_object_mi.cluster_tx_mean_model_p import StarRule
from nor_object_mi.fig_cluster_tx_kruskal_common import fdr_mark
from nor_object_mi.scalar_tx_mean_model_p import (  # noqa: E402
    METRIC_LAB,
    SCALAR_METRICS,
    aggregate_scalar_da,
    aggregate_scalar_pp,
    kruskal_per_model_scalar_da,
    kruskal_per_model_scalar_pp,
)
from nor_object_mi.simpler_first_phase_paired import (  # noqa: E402
    footnote_paired_n,
    paired_n_by_step,
    step_axis_labels,
)

DEFAULT_PRESENCE = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_presence_steps"
)
DEFAULT_PP = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_phase_paired"
)
NLP_VMAX = 4.0
DA_PANELS = (
    ("F", "no_obj->id_obj", "Female · presence"),
    ("F", "id_obj->nvl_obj", "Female · novelty"),
    ("F", "no_obj->nvl_obj", "Female · span"),
    ("M", "no_obj->id_obj", "Male · presence"),
    ("M", "id_obj->nvl_obj", "Male · novelty"),
    ("M", "no_obj->nvl_obj", "Male · span"),
)
PP_PANELS = (
    ("F", "no_obj", "Female · no_obj"),
    ("F", "id_obj", "Female · identical"),
    ("F", "nvl_obj", "Female · novel"),
    ("M", "no_obj", "Male · no_obj"),
    ("M", "id_obj", "Male · identical"),
    ("M", "nvl_obj", "Male · novel"),
)


def _p_cell_text(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 1e-4:
        return "<10⁻⁴"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.3f}"


def _neglog10_p(p: float) -> float:
    if not np.isfinite(p) or p <= 0:
        return float("nan")
    return float(min(NLP_VMAX, max(0.0, -np.log10(p))))


def _metric_mats(
    kr: pd.DataFrame,
    *,
    sex: str,
    facet_col: str,
    facet: str,
    col_col: str,
    col_order: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray]:
    metrics = list(SCALAR_METRICS)
    pmat = np.full((len(metrics), len(col_order)), np.nan)
    hits = np.zeros((len(metrics), len(col_order)), dtype=bool)
    sub = kr[(kr["sex"] == sex) & (kr[facet_col] == facet)]
    mi = {m: i for i, m in enumerate(metrics)}
    ci = {c: j for j, c in enumerate(col_order)}
    for row in sub.itertuples(index=False):
        i = mi.get(str(row.metric))
        j = ci.get(str(getattr(row, col_col)))
        if i is None or j is None:
            continue
        pmat[i, j] = float(row.p)
        hits[i, j] = bool(row.hit_fdr05)
    return pmat, hits


def _imshow(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    *,
    xlabels: list[str],
    title: str,
    ts: dict,
    show_ylabel: bool,
) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(xlabels)))
    ax.set_xticklabels(xlabels, fontsize=ts["annotation"])
    ax.set_yticks(range(len(SCALAR_METRICS)))
    if show_ylabel:
        ax.set_yticklabels([METRIC_LAB[m] for m in SCALAR_METRICS], fontsize=ts["annotation"])
        ax.set_ylabel("metric (paired Δ)")
    else:
        ax.set_yticklabels([])
    ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    for i in range(pmat.shape[0]):
        for j in range(pmat.shape[1]):
            p = pmat[i, j]
            nlp_v = nlp[i, j]
            if not np.isfinite(p) or not np.isfinite(nlp_v):
                continue
            mark = fdr_mark(bool(hits[i, j]), False)
            if not mark:
                continue
            ax.text(
                j,
                i,
                mark + _p_cell_text(p),
                ha="center",
                va="center",
                fontsize=ts["cell"],
                color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
            )
    return im


def fig_da(kr: pd.DataFrame, out: Path, *, dest: str, star: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = (18.0, 9.0) if dest == "slides" else (14.0, 7.0)
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.10, right=0.92, top=0.88, bottom=0.10, hspace=0.35, wspace=0.15)
    im = None
    xlabels = [SESSION_SHORT[p] for p in SESSIONS]
    for k, (ax, (sex, step, title)) in enumerate(zip(axes.ravel(), DA_PANELS)):
        pmat, hits = _metric_mats(
            kr, sex=sex, facet_col="step", facet=step, col_col="session", col_order=SESSIONS
        )
        im = _imshow(
            ax, pmat, hits, xlabels=xlabels, title=title, ts=ts, show_ylabel=(k in (0, 3))
        )
    cax = fig.add_axes([0.94, 0.30, 0.012, 0.40])
    fig.colorbar(im, cax=cax, label="−log₁₀(mean p)  (clip 4)")
    fig.suptitle(
        f"Scalar paired Δ · mean per-model Kruskal p ~ tx  (presence steps; * = majority BH, star={star})",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            "Rows = engagement (frac_near, mean_dist) and COUNT/UNCERTAINTY (richness, shannon). "
            "Cell = mean uncorrected Kruskal p on animal Δ across 21 alphabets. "
            f"* = BH q < 0.05 within ~21 models in that cell (star={star}). "
            "Not DA; not Wilcoxon vs 0."
        ),
        fontsize=ts["footnote"],
        y=0.02,
        color=MUTE,
    )
    save_pdf_png(fig, out / "fig_presence_scalar_tx_kruskal_overview_mean_model_p")


def fig_pp(kr: pd.DataFrame, out: Path, *, dest: str, star: str, n_map: dict[str, int]) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = (20.0, 9.0) if dest == "slides" else (15.0, 7.0)
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.10, right=0.92, top=0.88, bottom=0.12, hspace=0.35, wspace=0.15)
    im = None
    xlabels = step_axis_labels(n_map)
    for k, (ax, (sex, cond, title)) in enumerate(zip(axes.ravel(), PP_PANELS)):
        pmat, hits = _metric_mats(
            kr,
            sex=sex,
            facet_col="trial",
            facet=cond,
            col_col="session_step",
            col_order=PHASE_STEPS,
        )
        im = _imshow(
            ax, pmat, hits, xlabels=xlabels, title=title, ts=ts, show_ylabel=(k in (0, 3))
        )
    cax = fig.add_axes([0.94, 0.30, 0.012, 0.40])
    fig.colorbar(im, cax=cax, label="−log₁₀(mean p)  (clip 4)")
    fig.suptitle(
        f"Scalar paired Δ · mean per-model Kruskal p ~ tx  (phase-paired; * = majority BH, star={star})",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    n_line = footnote_paired_n(n_map) if n_map else ""
    fig_footnote(
        fig,
        (
            n_line
            + " Rows = frac_near, mean_dist, richness, shannon (paired Δ, condition held). "
            "Cell = mean uncorrected Kruskal p across 21 alphabets. "
            f"* = BH q < 0.05 within ~21 models in that cell (star={star}). "
            "Not DA; not Wilcoxon vs 0."
        ),
        fontsize=ts["footnote"],
        y=0.02,
        color=MUTE,
    )
    save_pdf_png(fig, out / "fig_phase_paired_scalar_tx_kruskal_overview_mean_model_p")


def _info(design: str, star: str) -> str:
    return f"""# INFO — scalar mean-model Kruskal overview

Design: `{design}`. Companion to cluster `*_mean_model_p` overviews.

## Grain

Animal paired Δ on `frac_near`, `mean_dist_any_m`, `richness`, `shannon_bits`.
Kruskal Δ ~ tx within sex, **per model**; cell = mean p; BH family = models in cell;
star = `{star}`.

## Not

Not DA (no per-syllable rows). Not Wilcoxon vs 0 on the Δ.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--presence-dir", type=Path, default=DEFAULT_PRESENCE)
    ap.add_argument("--pp-dir", type=Path, default=DEFAULT_PP)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument("--star", choices=("any", "majority", "all"), default="majority")
    ap.add_argument("--only", choices=("da", "pp", "both"), default="both")
    args = ap.parse_args(argv)
    star: StarRule = args.star  # type: ignore[assignment]
    summaries: list[dict] = []

    if args.only in ("da", "both"):
        print("presence scalars: Kruskal per model ...", flush=True)
        deltas = pd.read_csv(args.presence_dir / "presence_step_deltas_per_animal.csv")
        per = kruskal_per_model_scalar_da(deltas)
        per.to_csv(args.presence_dir / "presence_scalar_tx_kruskal_per_model.csv", index=False)
        agg = aggregate_scalar_da(per, star=star)
        agg.to_csv(args.presence_dir / "presence_scalar_tx_kruskal_mean_model_p.csv", index=False)
        (args.presence_dir / "INFO_presence_scalar_tx_kruskal_mean_model_p.md").write_text(
            _info("presence steps (condition ladder within phase)", star), encoding="utf-8"
        )
        fig_dir = args.presence_dir / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)
        fig_da(agg, fig_dir, dest=args.dest, star=star)
        summary = {
            "design": "presence_steps",
            "star_rule": star,
            "n_agg_cells": int(len(agg)),
            "n_hit_fdr05_cells": int(agg["hit_fdr05"].sum()),
            "hits_by_metric": {
                m: int(agg.loc[agg["metric"] == m, "hit_fdr05"].sum()) for m in SCALAR_METRICS
            },
        }
        (args.presence_dir / "presence_scalar_tx_kruskal_mean_model_p_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        summaries.append(summary)

    if args.only in ("pp", "both"):
        print("phase-paired scalars: Kruskal per model ...", flush=True)
        deltas = pd.read_csv(args.pp_dir / "phase_paired_deltas_per_animal.csv")
        n_map = paired_n_by_step(deltas)
        per = kruskal_per_model_scalar_pp(deltas)
        per.to_csv(args.pp_dir / "phase_paired_scalar_tx_kruskal_per_model.csv", index=False)
        agg = aggregate_scalar_pp(per, star=star)
        agg.to_csv(args.pp_dir / "phase_paired_scalar_tx_kruskal_mean_model_p.csv", index=False)
        (args.pp_dir / "INFO_phase_paired_scalar_tx_kruskal_mean_model_p.md").write_text(
            _info("phase-paired (condition held)", star), encoding="utf-8"
        )
        fig_dir = args.pp_dir / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)
        fig_pp(agg, fig_dir, dest=args.dest, star=star, n_map=n_map)
        summary = {
            "design": "phase_paired",
            "star_rule": star,
            "n_agg_cells": int(len(agg)),
            "n_hit_fdr05_cells": int(agg["hit_fdr05"].sum()),
            "hits_by_metric": {
                m: int(agg.loc[agg["metric"] == m, "hit_fdr05"].sum()) for m in SCALAR_METRICS
            },
        }
        (args.pp_dir / "phase_paired_scalar_tx_kruskal_mean_model_p_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        summaries.append(summary)

    print(json.dumps(summaries, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
