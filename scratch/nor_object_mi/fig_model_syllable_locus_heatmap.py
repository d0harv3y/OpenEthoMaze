"""Per-model syllable × locus heatmaps (DA + phase-paired; F/M panels).

One figure per kpMS model, 2×2 panels:
  Female DA | Male DA
  Female PP | Male PP

X = raw_syllable_id sorted by frequency (n_bouts desc).
Y = co-occurrence loci with sex stripped (step|phase or condition|session_step).
Cell = uncorrected Kruskal p; * = panel BH q < 0.05 (syllable × locus within sex × design).

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/fig_model_syllable_locus_heatmap.py
"""

from __future__ import annotations

import argparse
import json
import re
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
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster13_condition_delta import STEP_LAB
from nor_object_mi.cluster_condition_kruskal import (  # noqa: E402
    da_locus_labels,
    filter_presence_novelty,
    kruskal_by_syllable_da_locus_sex,
)
from nor_object_mi.cluster_condition_kruskal_session_paired import (  # noqa: E402
    COND_LAB,
    STEP_LAB as PP_STEP_LAB,
    kruskal_by_syllable_trial_session_step_sex,
    pp_locus_labels,
)

DEFAULT_DA = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_da"
)
DEFAULT_PP = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_session_paired"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
DEFAULT_OUT = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\model_syllable_locus_heatmaps"
)
DA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "step",
    "session",
    "raw_syllable_id",
    "delta_p",
)
PP_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "session_step",
    "trial",
    "raw_syllable_id",
    "delta_p",
)
NLP_VMAX = 4.0
PANELS = (
    ("da", "F", "Female · DA (presence/novelty/span × phase)"),
    ("da", "M", "Male · DA (presence/novelty/span × phase)"),
    ("pp", "F", "Female · phase-paired (condition × phase step)"),
    ("pp", "M", "Male · phase-paired (condition × phase step)"),
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


def _short_da_locus(locus: str) -> str:
    step, phase = locus.split("|", 1)
    return f"{STEP_LAB.get(step, step)}|{SESSION_SHORT.get(phase, phase)}"


def _short_pp_locus(locus: str) -> str:
    cond, step = locus.split("|", 1)
    return f"{COND_LAB.get(cond, cond)}|{PP_STEP_LAB.get(step, step)}"


def syllables_by_frequency(
    model: str,
    syll_ids: list[int],
    proto: pd.DataFrame,
) -> list[int]:
    """Sort syllable ids by n_bouts descending (ties → id ascending)."""
    sub = proto[proto["model"].astype(str) == str(model)][
        ["raw_syllable_id", "n_bouts"]
    ].drop_duplicates("raw_syllable_id")
    freq = {
        int(r): int(n)
        for r, n in zip(sub["raw_syllable_id"], sub["n_bouts"], strict=False)
    }
    return sorted(syll_ids, key=lambda s: (-freq.get(int(s), 0), int(s)))


def _panel_mats(
    kr: pd.DataFrame,
    *,
    sex: str,
    sylls: list[int],
    loci: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    pmat = np.full((len(loci), len(sylls)), np.nan)
    hits = np.zeros((len(loci), len(sylls)), dtype=bool)
    sub = kr[kr["sex"] == sex]
    si = {s: j for j, s in enumerate(sylls)}
    li = {lab: i for i, lab in enumerate(loci)}
    for row in sub.itertuples(index=False):
        j = si.get(int(row.raw_syllable_id))
        i = li.get(str(row.locus))
        if i is None or j is None:
            continue
        pmat[i, j] = float(row.p)
        hits[i, j] = bool(row.hit_fdr05)
    return pmat, hits


def _imshow_syll_locus(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    *,
    sylls: list[int],
    y_labels: list[str],
    title: str,
    ts: dict,
    show_ylabel: bool,
) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(sylls)))
    ax.set_xticklabels([str(s) for s in sylls], rotation=90, fontsize=ts["cell"])
    ax.set_yticks(range(len(y_labels)))
    if show_ylabel:
        ax.set_yticklabels(y_labels, fontsize=ts["cell"])
        ax.set_ylabel("locus")
    else:
        ax.set_yticklabels([])
    ax.set_xlabel("raw_syllable_id (freq →)")
    ax.set_title(title, loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
    for i in range(pmat.shape[0]):
        for j in range(pmat.shape[1]):
            p = pmat[i, j]
            nlp_v = nlp[i, j]
            if not np.isfinite(p) or not np.isfinite(nlp_v):
                continue
            mark = "*" if hits[i, j] else ""
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


def fig_model(
    kr_da: pd.DataFrame,
    kr_pp: pd.DataFrame,
    out_stem: Path,
    *,
    model: str,
    sylls: list[int],
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    n = len(sylls)
    ts = {**ts, "cell": max(3.0, float(ts["cell"]) * min(1.0, 36.0 / max(n, 1)))}
    da_loci = da_locus_labels()
    pp_loci = pp_locus_labels()
    da_ylab = [_short_da_locus(x) for x in da_loci]
    pp_ylab = [_short_pp_locus(x) for x in pp_loci]
    fig_w = max(18.0, 0.22 * n + 8.0) if dest == "slides" else max(14.0, 0.18 * n + 6.0)
    fig_h = 14.0 if dest == "slides" else 11.0
    fig, axes = plt.subplots(2, 2, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.10, right=0.92, top=0.90, bottom=0.08, hspace=0.28, wspace=0.12)
    im = None
    for ax, (design, sex, title) in zip(axes.ravel(), PANELS):
        if design == "da":
            pmat, hits = _panel_mats(kr_da, sex=sex, sylls=sylls, loci=da_loci)
            y_labels = da_ylab
        else:
            pmat, hits = _panel_mats(kr_pp, sex=sex, sylls=sylls, loci=pp_loci)
            y_labels = pp_ylab
        im = _imshow_syll_locus(
            ax,
            pmat,
            hits,
            sylls=sylls,
            y_labels=y_labels,
            title=title,
            ts=ts,
            show_ylabel=True,
        )
    cax = fig.add_axes([0.935, 0.30, 0.012, 0.40])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        f"Kruskal Δp_k ~ tx · {model}\n"
        f"syllable (x, freq-sorted) × locus (y); * = panel BH q < 0.05",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        (
            f"{n} syllables in this alphabet, x sorted by signature n_bouts (high→low). "
            "Top: DA presence/novelty/span × phase (same loci as cluster co-occurrence, sex split). "
            "Bottom: phase-paired condition × phase step (same loci as column co-occurrence, sex split). "
            "Cell text = uncorrected Kruskal p; * = BH within that sex × design panel "
            "(all syllables × loci). Ids not portable across models. frame_share Δp."
        ),
        fontsize=ts["footnote"],
        y=0.01,
        color=MUTE,
    )
    save_pdf_png(fig, out_stem)


def _model_slug(model: str) -> str:
    return re.sub(r"[^\w\-]+", "_", model)


def _info_md() -> str:
    return """# INFO — per-model syllable × locus heatmaps

One figure per kpMS model (21). Four panels: Female/Male × DA / phase-paired.

## Axes

- **X** = `raw_syllable_id` sorted by `n_bouts` (signature table; high → low).
- **Y** = locus labels matching cluster co-occurrence columns with sex removed:
  - DA: `step|session` (alphabetical step × `NOR_BL`…`NOR_REC11hr`)
  - Phase-paired: `trial|session_step`

## Hit rule

Uncorrected Kruskal p in every cell. `*` = Benjamini–Hochberg `q_bh < 0.05`
within the **panel** (all syllable × locus cells for that sex × design).

## Grain

Animal Δp_k ~ tx within sex (independent groups). One model per figure —
syllable ids are alphabet-local.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--da-dir", type=Path, default=DEFAULT_DA)
    ap.add_argument("--pp-dir", type=Path, default=DEFAULT_PP)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument(
        "--model",
        action="append",
        default=None,
        help="Restrict to model name(s); repeatable",
    )
    args = ap.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "INFO_model_syllable_locus_heatmaps.md").write_text(_info_md(), encoding="utf-8")

    print("reading deltas + prototypes ...", flush=True)
    proto = pd.read_csv(
        args.sig_dir / "syllable_prototypes_clustered.csv",
        usecols=["model", "raw_syllable_id", "n_bouts"],
    )
    da = pd.read_csv(args.da_dir / "da_syllable_deltas_per_animal.csv", usecols=list(DA_USECOLS))
    da = filter_presence_novelty(da)
    pp = pd.read_csv(
        args.pp_dir / "session_paired_da_deltas_per_animal.csv", usecols=list(PP_USECOLS)
    )
    models = sorted(set(da["model"].astype(str)) & set(pp["model"].astype(str)))
    if args.model:
        want = set(args.model)
        models = [m for m in models if m in want]
        missing = want - set(models)
        if missing:
            raise SystemExit(f"models not found: {sorted(missing)}")

    da_parts: list[pd.DataFrame] = []
    pp_parts: list[pd.DataFrame] = []
    hit_summary: dict[str, dict[str, int]] = {}
    for i, model in enumerate(models, start=1):
        print(f"[{i}/{len(models)}] {model}", flush=True)
        da_sub = da[da["model"].astype(str) == model]
        pp_sub = pp[pp["model"].astype(str) == model]
        kr_da = kruskal_by_syllable_da_locus_sex(da_sub)
        kr_pp = kruskal_by_syllable_trial_session_step_sex(pp_sub)
        kr_da.insert(0, "model", model)
        kr_da.insert(1, "design", "da")
        kr_pp.insert(0, "model", model)
        kr_pp.insert(1, "design", "pp")
        da_parts.append(kr_da)
        pp_parts.append(kr_pp)
        sylls = syllables_by_frequency(
            model,
            sorted(set(kr_da["raw_syllable_id"].astype(int)) | set(kr_pp["raw_syllable_id"].astype(int))),
            proto,
        )
        stem = out / f"fig_model_syllable_locus_{_model_slug(model)}"
        fig_model(kr_da, kr_pp, stem, model=model, sylls=sylls, dest=args.dest)
        hit_summary[model] = {}
        for design, sex, _t in PANELS:
            tab = kr_da if design == "da" else kr_pp
            hit_summary[model][f"{design}_{sex}"] = int(
                tab.loc[tab["sex"] == sex, "hit_fdr05"].sum()
            )

    long = pd.concat(da_parts + pp_parts, ignore_index=True) if da_parts else pd.DataFrame()
    long.to_csv(out / "model_syllable_locus_kruskal.csv", index=False)
    summary = {
        "n_models": len(models),
        "models": models,
        "n_kruskal_rows": int(len(long)),
        "bh_family": "syllable x locus within sex x design",
        "da_n_loci": len(da_locus_labels()),
        "pp_n_loci": len(pp_locus_labels()),
        "n_fdr_hits_by_model_panel": hit_summary,
        "out_dir": str(out),
    }
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"n_models": len(models), "out": str(out)}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
