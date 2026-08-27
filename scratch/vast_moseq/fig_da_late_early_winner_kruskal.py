"""Kruskal/Mann–Whitney heatmaps for S05 late−early DA winners (model × session).

One row per model's top-right late−early syllable at S05. Three figures:
  1. tx pairwise (RBSF-1 vs n/a), strain pooled
  2. strain pairwise (wt vs tg), tx pooled
  3. k-ary strain×tx (4 groups)

Regen:
  uv run python scratch/vast_moseq/fig_da_late_early_winner_kruskal.py
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
from vast_moseq.vast_cluster_kruskal import STEP_LAB, VAST_PHASES, VAST_STEPS  # noqa: E402
from vast_moseq.vast_syllable_kruskal import (  # noqa: E402
    filter_deltas_to_winners,
    kruskal_by_syllable_session_step_sex_stx,
    kruskal_by_syllable_session_step_sex_strain_pairwise,
    kruskal_by_syllable_session_step_sex_tx_pairwise,
    pick_late_early_winners,
)

DEFAULT_DA = Path(r"C:\Users\admin\Documents\work\sack\AZ-SD-VAST-moseq\_da_trial_windows")
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


def _row_labels(winners: pd.DataFrame) -> list[str]:
    order = winners.sort_values("model")["syllable_label"].tolist()
    return order


def _syllable_session_mats(
    kr: pd.DataFrame,
    row_labels: list[str],
    label_to_key: dict[str, tuple[str, int]],
    *,
    sex: str,
    step: str,
) -> tuple[np.ndarray, np.ndarray]:
    pmat = np.full((len(row_labels), len(VAST_PHASES)), np.nan)
    hits = np.zeros((len(row_labels), len(VAST_PHASES)), dtype=bool)
    sub = kr[(kr["sex"] == sex) & (kr["step"] == step)]
    for i, lab in enumerate(row_labels):
        model, sid = label_to_key[lab]
        row = sub[(sub["model"] == model) & (sub["raw_syllable_id"] == sid)]
        for r in row.itertuples(index=False):
            try:
                j = VAST_PHASES.index(str(r.phase_layer))
            except ValueError:
                continue
            pmat[i, j] = float(r.p)
            hits[i, j] = bool(r.hit_fdr05)
    return pmat, hits


def _panels() -> tuple[tuple[str, str, str], ...]:
    out: list[tuple[str, str, str]] = []
    for sex in SEX_ORDER:
        label = "Female" if sex == "F" else "Male"
        for step in VAST_STEPS:
            out.append((sex, step, f"{label} · {STEP_LAB[step]}"))
    return tuple(out)


def _imshow_syllable_session(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    row_labels: list[str],
    *,
    title: str,
    ts: dict,
    show_ylabel: bool,
) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(VAST_PHASES)))
    ax.set_xticklabels(list(VAST_PHASES), fontsize=ts["annotation"])
    ax.set_yticks(range(len(row_labels)))
    if show_ylabel:
        ax.set_yticklabels(row_labels, fontsize=ts["cell"] - 1, ha="right")
        ax.set_ylabel("model | syllable (S05 late−early winner)")
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
                fontsize=ts["cell"] - 1,
                color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
            )
    return im


def fig_kruskal_overview(
    kr: pd.DataFrame,
    winners: pd.DataFrame,
    out: Path,
    *,
    stem: str,
    suptitle: str,
    footnote: str,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    row_labels = _row_labels(winners)
    label_to_key = {
        str(r.syllable_label): (str(r.model), int(r.raw_syllable_id))
        for r in winners.itertuples(index=False)
    }
    panels = _panels()
    fig_h = 10.0 if dest == "slides" else 8.0
    fig_w = 18.0 if dest == "slides" else 13.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.22, right=0.92, top=0.90, bottom=0.12, hspace=0.32, wspace=0.12)
    im = None
    for k, (ax, (sex, step, title)) in enumerate(zip(axes.ravel(), panels)):
        pmat, hits = _syllable_session_mats(
            kr, row_labels, label_to_key, sex=sex, step=step
        )
        im = _imshow_syllable_session(
            ax,
            pmat,
            hits,
            row_labels,
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
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--phase", type=str, default="S05")
    ap.add_argument("--fdr-only", action="store_true", help="Only models with FDR hit at phase")
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    out = args.out_dir or args.da_dir
    fig_out = out / "figures"
    fig_out.mkdir(parents=True, exist_ok=True)

    tests = pd.read_csv(out / "da_syllable_tests_long.csv", keep_default_na=False)
    winners = pick_late_early_winners(
        tests, phase_layer=args.phase, require_positive=True, fdr_only=args.fdr_only
    )
    winners.to_csv(out / f"da_late_early_{args.phase.lower()}_winners.csv", index=False)
    print(f"{args.phase} late-early winners per model:", flush=True)
    print(winners.to_string(index=False), flush=True)

    deltas = pd.read_csv(
        out / "da_syllable_deltas_per_animal.csv",
        usecols=list(DELTA_USECOLS),
        keep_default_na=False,
    )
    med = filter_deltas_to_winners(deltas, winners)
    med.to_csv(out / "da_late_early_winner_animal_delta_p.csv", index=False)

    n_rows = len(winners)
    bh_note = f"{n_rows} winner syllables × {len(VAST_PHASES)} sessions within each sex × step panel"

    kr_tx = kruskal_by_syllable_session_step_sex_tx_pairwise(med)
    kr_tx.to_csv(out / "da_late_early_winner_tx_pairwise_kruskal.csv", index=False)
    fig_kruskal_overview(
        kr_tx,
        winners,
        fig_out,
        stem="fig_da_late_early_winner_tx_pairwise_kruskal",
        suptitle=(
            f"Mann–Whitney Δp ({WEIGHTING}) ~ tx · S05 late−early winners × session  "
            "(strain pooled; within sex; * = BH q < 0.05 in panel)"
        ),
        footnote=(
            f"Row = each model's top positive late−early syllable at {args.phase} (pooled Wilcoxon argmax). "
            f"Cell = Mann–Whitney RBSF-1 vs n/a on per-animal Δp; strain pooled. "
            f"Color = −log₁₀(uncorrected p); * = FDR within panel. BH family = {bh_note}."
        ),
        dest=args.dest,
    )

    kr_strain = kruskal_by_syllable_session_step_sex_strain_pairwise(med)
    kr_strain.to_csv(out / "da_late_early_winner_strain_pairwise_kruskal.csv", index=False)
    fig_kruskal_overview(
        kr_strain,
        winners,
        fig_out,
        stem="fig_da_late_early_winner_strain_pairwise_kruskal",
        suptitle=(
            f"Mann–Whitney Δp ({WEIGHTING}) ~ strain · S05 late−early winners × session  "
            "(tx pooled; within sex; * = BH q < 0.05 in panel)"
        ),
        footnote=(
            f"Cell = Mann–Whitney wt vs tg; tx pooled. BH family = {bh_note}. "
            "Same winner syllables as tx figure."
        ),
        dest=args.dest,
    )

    kr_stx = kruskal_by_syllable_session_step_sex_stx(med)
    kr_stx.to_csv(out / "da_late_early_winner_stx_kruskal.csv", index=False)
    fig_kruskal_overview(
        kr_stx,
        winners,
        fig_out,
        stem="fig_da_late_early_winner_stx_kruskal",
        suptitle=(
            f"Kruskal Δp ({WEIGHTING}) ~ strain×tx · S05 late−early winners × session  "
            "(4 groups; within sex; * = BH q < 0.05 in panel)"
        ),
        footnote=(
            f"Cell = Kruskal–Wallis on 4 groups (wt|RBSF-1, wt|n/a, tg|RBSF-1, tg|n/a). "
            f"BH family = {bh_note}."
        ),
        dest=args.dest,
    )

    summary = {
        "phase_layer": args.phase,
        "step": "late_early",
        "n_winner_syllables": n_rows,
        "winners": winners.to_dict(orient="records"),
        "bh_family_per_panel": bh_note,
    }
    (out / "da_late_early_winner_kruskal_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    print(f"wrote figures -> {fig_out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
