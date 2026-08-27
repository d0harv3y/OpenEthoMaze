"""VAST cluster × session Δp Kruskal/Mann–Whitney overview heatmaps (sex-split).

Three figures (NOR-style layout: 2×3, F/M rows × step columns):
  1. tx pairwise (RBSF-1 vs n/a), strain pooled
  2. strain pairwise (wt vs tg), tx pooled
  3. k-ary strain×tx (4 groups)

Regen:
  uv run python scratch/vast_moseq/fig_cluster_kruskal_overview.py
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
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
    type_scale,
)
from vast_moseq.vast_cluster_kruskal import (  # noqa: E402
    STEP_LAB,
    VAST_PHASES,
    VAST_STEPS,
    animal_median_delta_p_by_cluster,
    attach_cluster_ids,
    kruskal_by_cluster_session_step_sex_strain_pairwise,
    kruskal_by_cluster_session_step_sex_stx,
    kruskal_by_cluster_session_step_sex_tx_pairwise,
)
from nor_object_mi.cluster_tx_kruskal import representative_cluster_ids  # noqa: E402

DEFAULT_DA = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\_da_trial_windows")
DEFAULT_SIG = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\syllable_signatures")
DELTA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "strain",
    "tx",
    "step",
    "phase_layer",
    "raw_syllable_id",
    "delta_p",
)
NLP_VMAX = 4.0
WEIGHTING = "frame_share"


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


def _cluster_session_mats(
    kr: pd.DataFrame,
    cluster_ids: list[int],
    *,
    sex: str,
    step: str,
) -> tuple[np.ndarray, np.ndarray]:
    pmat = np.full((len(cluster_ids), len(VAST_PHASES)), np.nan)
    hits = np.zeros((len(cluster_ids), len(VAST_PHASES)), dtype=bool)
    sub = kr[(kr["sex"] == sex) & (kr["step"] == step)]
    id_to_i = {cid: i for i, cid in enumerate(cluster_ids)}
    for row in sub.itertuples(index=False):
        i = id_to_i.get(int(row.cluster_id))
        if i is None:
            continue
        try:
            j = VAST_PHASES.index(str(row.phase_layer))
        except ValueError:
            continue
        pmat[i, j] = float(row.p)
        hits[i, j] = bool(row.hit_fdr05)
    return pmat, hits


def _imshow_cluster_session(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    cluster_ids: list[int],
    *,
    title: str,
    ts: dict,
    show_ylabel: bool,
) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(VAST_PHASES)))
    ax.set_xticklabels(list(VAST_PHASES), fontsize=ts["annotation"])
    ax.set_yticks(range(len(cluster_ids)))
    if show_ylabel:
        ax.set_yticklabels([str(c) for c in cluster_ids], fontsize=ts["cell"], ha="right")
        ax.set_ylabel("cluster_id")
        ax.tick_params(axis="y", pad=2)
    else:
        ax.set_yticklabels([])
    ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    for i in range(pmat.shape[0]):
        for j in range(pmat.shape[1]):
            p = pmat[i, j]
            nlp_v = nlp[i, j]
            if not np.isfinite(p) or not np.isfinite(nlp_v):
                continue
            if not hits[i, j]:
                continue
            ax.text(
                j,
                i,
                "*" + _p_cell_text(p),
                ha="center",
                va="center",
                fontsize=ts["cell"],
                color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
            )
    return im


def _panels() -> tuple[tuple[str, str, str], ...]:
    out: list[tuple[str, str, str]] = []
    for sex in SEX_ORDER:
        label = "Female" if sex == "F" else "Male"
        for step in VAST_STEPS:
            out.append((sex, step, f"{label} · {STEP_LAB[step]}"))
    return tuple(out)


def fig_kruskal_overview(
    kr: pd.DataFrame,
    out: Path,
    *,
    stem: str,
    suptitle: str,
    footnote: str,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    cluster_ids = sorted(int(x) for x in kr["cluster_id"].unique())
    panels = _panels()
    fig_h = 14.0 if dest == "slides" else 10.5
    fig_w = 18.0 if dest == "slides" else 13.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.08, right=0.92, top=0.92, bottom=0.10, hspace=0.30, wspace=0.12)
    im = None
    for k, (ax, (sex, step, title)) in enumerate(zip(axes.ravel(), panels)):
        pmat, hits = _cluster_session_mats(kr, cluster_ids, sex=sex, step=step)
        im = _imshow_cluster_session(
            ax,
            pmat,
            hits,
            cluster_ids,
            title=title,
            ts=ts,
            show_ylabel=(k in (0, 3)),
        )
    cax = fig.add_axes([0.93, 0.35, 0.012, 0.35])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(suptitle, fontsize=ts["suptitle"], fontweight="bold", color=INK)
    fig_footnote(fig, footnote, fontsize=ts["footnote"], y=0.02, color=MUTE)
    save_pdf_png(fig, out / stem)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    out = args.out_dir or args.da_dir
    fig_out = out / "figures"
    fig_out.mkdir(parents=True, exist_ok=True)

    print("reading prototypes + animal deltas ...", flush=True)
    proto = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")
    rep = representative_cluster_ids(proto)
    deltas = pd.read_csv(
        args.da_dir / "da_syllable_deltas_per_animal.csv",
        usecols=list(DELTA_USECOLS),
        keep_default_na=False,
    )
    mapped = attach_cluster_ids(deltas, rep)
    med = animal_median_delta_p_by_cluster(mapped)
    med.to_csv(out / "cluster_animal_median_delta_p.csv", index=False)
    rep.to_csv(out / "cluster_representative_ids.csv", index=False)

    n_clusters = int(med["cluster_id"].nunique())
    bh_note = f"{n_clusters} clusters × {len(VAST_PHASES)} sessions within each sex × step panel"

    kr_tx = kruskal_by_cluster_session_step_sex_tx_pairwise(med)
    kr_tx.to_csv(out / "cluster_tx_pairwise_kruskal.csv", index=False)
    fig_kruskal_overview(
        kr_tx,
        fig_out,
        stem="fig_cluster_tx_pairwise_kruskal_overview",
        suptitle=(
            f"Mann–Whitney Δp ({WEIGHTING}) ~ tx by cluster × session  "
            "(strain pooled; within sex; * = BH q < 0.05 in panel)"
        ),
        footnote=(
            f"Δp = frame_share. Row = HDBSCAN cluster_id (representative syllable per model). "
            f"Cell = Mann–Whitney RBSF-1 vs n/a on animal median Δp across 6 alphabets; "
            f"strain pooled. Color = −log₁₀(uncorrected p); * = FDR hit. BH family = {bh_note}. "
            "Not Wilcoxon vs 0."
        ),
        dest=args.dest,
    )

    kr_strain = kruskal_by_cluster_session_step_sex_strain_pairwise(med)
    kr_strain.to_csv(out / "cluster_strain_pairwise_kruskal.csv", index=False)
    fig_kruskal_overview(
        kr_strain,
        fig_out,
        stem="fig_cluster_strain_pairwise_kruskal_overview",
        suptitle=(
            f"Mann–Whitney Δp ({WEIGHTING}) ~ strain by cluster × session  "
            "(tx pooled; within sex; * = BH q < 0.05 in panel)"
        ),
        footnote=(
            f"Cell = Mann–Whitney wt vs tg; tx pooled. BH family = {bh_note}. "
            "Same grain as tx figure."
        ),
        dest=args.dest,
    )

    kr_stx = kruskal_by_cluster_session_step_sex_stx(med)
    kr_stx.to_csv(out / "cluster_stx_kruskal.csv", index=False)
    fig_kruskal_overview(
        kr_stx,
        fig_out,
        stem="fig_cluster_stx_kruskal_overview",
        suptitle=(
            f"Kruskal Δp ({WEIGHTING}) ~ strain×tx by cluster × session  "
            "(4 groups; within sex; * = BH q < 0.05 in panel)"
        ),
        footnote=(
            f"Cell = Kruskal–Wallis on 4 groups (wt|RBSF-1, wt|n/a, tg|RBSF-1, tg|n/a). "
            f"BH family = {bh_note}."
        ),
        dest=args.dest,
    )

    summary = {
        "weighting": WEIGHTING,
        "n_clusters": n_clusters,
        "n_animal_cells": int(len(med)),
        "bh_family_per_panel": bh_note,
        "n_fdr_tx_pairwise_by_panel": {
            f"{sex}_{STEP_LAB[step]}": int(
                kr_tx[(kr_tx["sex"] == sex) & (kr_tx["step"] == step)]["hit_fdr05"].sum()
            )
            for sex in SEX_ORDER
            for step in VAST_STEPS
        },
        "n_fdr_strain_pairwise_by_panel": {
            f"{sex}_{STEP_LAB[step]}": int(
                kr_strain[(kr_strain["sex"] == sex) & (kr_strain["step"] == step)]["hit_fdr05"].sum()
            )
            for sex in SEX_ORDER
            for step in VAST_STEPS
        },
        "n_fdr_stx_by_panel": {
            f"{sex}_{STEP_LAB[step]}": int(
                kr_stx[(kr_stx["sex"] == sex) & (kr_stx["step"] == step)]["hit_fdr05"].sum()
            )
            for sex in SEX_ORDER
            for step in VAST_STEPS
        },
    }
    (out / "cluster_kruskal_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"wrote figures -> {fig_out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
