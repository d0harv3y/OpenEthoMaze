"""Cluster-13 model Kruskal overviews for 2nd-order nested Δp_k.

(b) session_on_trial: panels = sex × condition step; columns = phase steps
(c) trial_on_session: panels = sex × phase step (4×3); columns = condition steps

Regen (OpenEthoMaze repo root):
  uv run python scratch/nor_object_mi/simpler_first_nested_da.py
  uv run python scratch/nor_object_mi/fig_cluster_condition_kruskal_nested.py
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
    apply_style,
    fig_footnote,
    save_pdf_png,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster_condition_kruskal_nested import (  # noqa: E402
    animal_delta_p_by_model_nested,
    attach_model_cluster_deltas_nested,
    cluster_syllable_ids,
    kruskal_by_model_trial_on_session_sex,
    kruskal_by_model_session_on_trial_sex,
)
from nor_object_mi.nested_da_delta import (  # noqa: E402
    COND_STEP_LAB,
    paired_n_by_inner_step,
    paired_n_by_outer_step,
)
from nor_object_mi.simpler_first_da import DA_STEPS  # noqa: E402
from nor_object_mi.simpler_first_session_paired import (  # noqa: E402
    PAIRED_FOOT_LEAD,
    PHASE_STEP_NAMES,
    STEP_LAB,
    footnote_paired_n,
    step_axis_label,
)

DEFAULT_NESTED = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_nested_da"
)
DEFAULT_SIG = Path(
    r"C:\Users\admin\Documents\work\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\simpler_first_syllable_signatures"
)
DELTA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "condition",
    "condition_step",
    "session_step",
    "raw_syllable_id",
    "delta_p",
)
NLP_VMAX = 4.0
PANELS_B = (
    ("F", "no_obj->id_obj", "Female · presence"),
    ("F", "id_obj->nvl_obj", "Female · novelty"),
    ("F", "no_obj->nvl_obj", "Female · span"),
    ("M", "no_obj->id_obj", "Male · presence"),
    ("M", "id_obj->nvl_obj", "Male · novelty"),
    ("M", "no_obj->nvl_obj", "Male · span"),
)


def _p_cell_text(p: float) -> str:
    if not np.isfinite(p):
        return ""
    if p < 0.001:
        return "<.001"
    if p < 0.01:
        return f"{p:.3f}".lstrip("0")
    return f"{p:.2f}".lstrip("0")


def _neglog10_p(p: float) -> float:
    if not np.isfinite(p) or p <= 0:
        return float("nan")
    return min(float(-np.log10(p)), NLP_VMAX)


def _cond_step_labels() -> list[str]:
    return [COND_STEP_LAB[s] for s in DA_STEPS]


def _session_step_labels(n_map: dict[str, int]) -> list[str]:
    return [step_axis_label(s, n_map) for s in PHASE_STEP_NAMES]


def _imshow_grid(
    ax,
    pmat: np.ndarray,
    hits: np.ndarray,
    y_labels: list[str],
    x_labels: list[str],
    *,
    title: str,
    ts: dict,
    ylabel: str,
    show_ylabel: bool,
    annotate_all_p: bool = False,
    ytick_fontsize: float | None = None,
) -> object:
    nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
    im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(x_labels, fontsize=ts["annotation"])
    ax.set_yticks(range(len(y_labels)))
    yfs = float(ytick_fontsize if ytick_fontsize is not None else ts["cell"])
    if show_ylabel:
        ax.set_yticklabels(y_labels, fontsize=yfs, ha="right")
        ax.set_ylabel(ylabel)
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
            if not annotate_all_p and not hits[i, j]:
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


def _row_mats_b(
    kr: pd.DataFrame,
    models: list[str],
    *,
    sex: str,
    condition_step: str,
) -> tuple[np.ndarray, np.ndarray]:
    pmat = np.full((len(models), len(PHASE_STEP_NAMES)), np.nan)
    hits = np.zeros((len(models), len(PHASE_STEP_NAMES)), dtype=bool)
    sub = kr[(kr["sex"] == sex) & (kr["condition_step"] == condition_step)]
    id_to_i = {m: i for i, m in enumerate(models)}
    for row in sub.itertuples(index=False):
        i = id_to_i.get(str(row.model))
        if i is None:
            continue
        try:
            j = PHASE_STEP_NAMES.index(str(row.session_step))
        except ValueError:
            continue
        pmat[i, j] = float(row.p)
        hits[i, j] = bool(row.hit_fdr05)
    return pmat, hits


def _row_mats_c(
    kr: pd.DataFrame,
    models: list[str],
    *,
    sex: str,
    session_step: str,
) -> tuple[np.ndarray, np.ndarray]:
    pmat = np.full((len(models), len(DA_STEPS)), np.nan)
    hits = np.zeros((len(models), len(DA_STEPS)), dtype=bool)
    sub = kr[(kr["sex"] == sex) & (kr["session_step"] == session_step)]
    id_to_i = {m: i for i, m in enumerate(models)}
    for row in sub.itertuples(index=False):
        i = id_to_i.get(str(row.model))
        if i is None:
            continue
        try:
            j = DA_STEPS.index(str(row.condition_step))
        except ValueError:
            continue
        pmat[i, j] = float(row.p)
        hits[i, j] = bool(row.hit_fdr05)
    return pmat, hits


def fig_nested_b_model_overview(
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    n_map: dict[str, int],
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    models = sorted(str(x) for x in kr["model"].unique())
    fig_h = 13.5 if dest == "slides" else 10.0
    fig_w = 26.0 if dest == "slides" else 18.0
    fig, axes = plt.subplots(2, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.28, right=0.92, top=0.90, bottom=0.10, hspace=0.32, wspace=0.14)
    im = None
    x_labels = _session_step_labels(n_map)
    for k, (ax, (sex, cond_step, title)) in enumerate(zip(axes.ravel(), PANELS_B)):
        pmat, hits = _row_mats_b(kr, models, sex=sex, condition_step=cond_step)
        im = _imshow_grid(
            ax,
            pmat,
            hits,
            models,
            x_labels,
            title=title,
            ts=ts,
            ylabel="model",
            show_ylabel=(k in (0, 3)),
            annotate_all_p=True,
            ytick_fontsize=ts["cell"] * 0.85,
        )
    cax = fig.add_axes([0.93, 0.35, 0.01, 0.35])
    fig.colorbar(im, cax=cax, label="−log10(p)  (clip 4)")
    fig.suptitle(
        "2nd-order Δp_k: phase step on condition-step Δ  ·  Kruskal ~ tx by model  "
        "(cluster 13; within sex; * = BH q < 0.05)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    n_line = footnote_paired_n(n_map) if n_map else PAIRED_FOOT_LEAD.rstrip()
    n_models = len(models)
    fig_footnote(
        fig,
        (
            n_line
            + " Δ²p_k = δ_k(right phase) − δ_k(left phase); "
            "δ_k = condition-step Δp_k at that phase. "
            f"BH family = {n_models} models × {len(PHASE_STEP_NAMES)} phase steps "
            f"within each sex × condition-step panel ({n_models * len(PHASE_STEP_NAMES)} tests/panel). "
            "Not Wilcoxon vs 0; not alphabet-wide DA FDR."
        ),
        fontsize=ts["footnote"],
        y=0.01,
        color=MUTE,
    )
    save_pdf_png(fig, out / "fig_nested_b_cluster13_model_condition_kruskal_overview")


def fig_nested_c_model_overview(
    kr: pd.DataFrame,
    out: Path,
    *,
    dest: str,
    n_map: dict[str, int],
    n_inner: dict[str, int],
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    models = sorted(str(x) for x in kr["model"].unique())
    panels_c: list[tuple[str, str, str]] = []
    for sex in ("F", "M"):
        sex_lab = "Female" if sex == "F" else "Male"
        for session_step in PHASE_STEP_NAMES:
            step_lab = step_axis_label(session_step, n_inner)
            panels_c.append((sex, session_step, f"{sex_lab} · {step_lab}"))
    fig_h = 22.0 if dest == "slides" else 16.0
    fig_w = 20.0 if dest == "slides" else 14.0
    fig, axes = plt.subplots(4, 3, figsize=(fig_w, fig_h), constrained_layout=False)
    fig.subplots_adjust(left=0.28, right=0.92, top=0.94, bottom=0.04, hspace=0.38, wspace=0.14)
    im = None
    x_labels = _cond_step_labels()
    for k, (ax, (sex, session_step, title)) in enumerate(zip(axes.ravel(), panels_c)):
        pmat, hits = _row_mats_c(kr, models, sex=sex, session_step=session_step)
        im = _imshow_grid(
            ax,
            pmat,
            hits,
            models,
            x_labels,
            title=title,
            ts=ts,
            ylabel="model",
            show_ylabel=(k % 3 == 0),
            annotate_all_p=True,
            ytick_fontsize=ts["cell"] * 0.78,
        )
    cax = fig.add_axes([0.93, 0.40, 0.012, 0.25])
    fig.colorbar(im, cax=cax, label="−log10(p)  (clip 4)")
    fig.suptitle(
        "2nd-order Δp_k: condition step on phase-step Δ  ·  Kruskal ~ tx by model  "
        "(cluster 13; within sex; * = BH q < 0.05)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    inner_n_line = ", ".join(
        f"{STEP_LAB[s]} {n_inner[s]}" for s in PHASE_STEP_NAMES if s in n_inner
    )
    cond_n_line = ", ".join(f"{COND_STEP_LAB.get(s, s)} {n_map.get(s, '?')}" for s in DA_STEPS)
    n_models = len(models)
    fig_footnote(
        fig,
        (
            PAIRED_FOOT_LEAD.rstrip()
            + f" Inner hold = phase step ({inner_n_line}). "
            f" Outer pairing = condition step ({cond_n_line}). "
            "Δ²p_k = δ_k(right condition) − δ_k(left condition); "
            "δ_k = phase-step Δp_k in that condition. "
            f"BH family = {n_models} models × {len(DA_STEPS)} condition steps "
            f"within each sex × phase-step panel ({n_models * len(DA_STEPS)} tests/panel). "
            "Not Wilcoxon vs 0; not alphabet-wide DA FDR."
        ),
        fontsize=ts["footnote"],
        y=0.005,
        color=MUTE,
    )
    save_pdf_png(fig, out / "fig_nested_c_cluster13_model_condition_kruskal_overview")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nested-dir", type=Path, default=DEFAULT_NESTED)
    ap.add_argument("--sig-dir", type=Path, default=DEFAULT_SIG)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    args = ap.parse_args(argv)

    out = args.out_dir or (args.nested_dir / "figures")
    out.mkdir(parents=True, exist_ok=True)

    proto = pd.read_csv(args.sig_dir / "syllable_prototypes_clustered.csv")
    cmap13 = cluster_syllable_ids(proto, cluster_id=13)

    print("(b) session_on_trial model overview ...", flush=True)
    nested_b = pd.read_csv(args.nested_dir / "nested_b_da_deltas_per_animal.csv")
    n_b = paired_n_by_outer_step(nested_b, axis="session_on_trial")
    mapped_b = attach_model_cluster_deltas_nested(nested_b, cmap13)
    med_b = animal_delta_p_by_model_nested(mapped_b, axis="session_on_trial")
    kr_b = kruskal_by_model_session_on_trial_sex(med_b)
    med_b.to_csv(args.nested_dir / "nested_b_cluster13_model_animal_delta_p.csv", index=False)
    kr_b.to_csv(args.nested_dir / "nested_b_cluster13_model_condition_kruskal.csv", index=False)
    fig_nested_b_model_overview(kr_b, out, dest=args.dest, n_map=n_b)

    print("(c) trial_on_session model overview ...", flush=True)
    nested_c = pd.read_csv(args.nested_dir / "nested_c_da_deltas_per_animal.csv")
    n_c = paired_n_by_outer_step(nested_c, axis="trial_on_session")
    n_c_inner = paired_n_by_inner_step(nested_c, axis="trial_on_session")
    mapped_c = attach_model_cluster_deltas_nested(nested_c, cmap13)
    med_c = animal_delta_p_by_model_nested(mapped_c, axis="trial_on_session")
    kr_c = kruskal_by_model_trial_on_session_sex(med_c)
    med_c.to_csv(args.nested_dir / "nested_c_cluster13_model_animal_delta_p.csv", index=False)
    kr_c.to_csv(args.nested_dir / "nested_c_cluster13_model_condition_kruskal.csv", index=False)
    fig_nested_c_model_overview(kr_c, out, dest=args.dest, n_map=n_c, n_inner=n_c_inner)

    summary = {
        "n_models": int(cmap13["model"].nunique()),
        "kruskal_fdr_b": int(kr_b["hit_fdr05"].sum()),
        "kruskal_fdr_c": int(kr_c["hit_fdr05"].sum()),
        "paired_n_b": n_b,
        "paired_n_c": n_c,
    }
    (args.nested_dir / "nested_cluster13_model_kruskal_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
