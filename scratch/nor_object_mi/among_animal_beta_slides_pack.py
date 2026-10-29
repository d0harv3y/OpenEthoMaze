"""Among-animal β: PERMANOVA on Bray–Curtis within ``session × trial`` cells.

**Claim:** Within sex, does **condition** partition animal syllable compositions
(abundance-difference matrix) at a fixed session × trial? Analogy-only on
syllables (Anderson 2001 PERMANOVA).

**Not** a per-animal paired-BC violin (that is the step pack). **Not** BC to a
fixed reference (deferred option 1).

Syllable ids are model-local (ADR-0005) → run PERMANOVA **per kpMS model**, then
summarize across models (median −log₁₀(p), frac FDR hit). No cross-model
composition stacking.

Source: archive ``*_clean`` condition ladders (absorb under 3 frames), same 21 models as
presence / richness packs.

Regen::

    uv run python scratch/nor_object_mi/among_animal_beta_slides_pack.py --rebuild
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import pdist, squareform

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    CONDITION_ORDER,
    INK,
    MUTE,
    SESSION_SHORT,
    SESSIONS,
    SEX_ORDER,
    apply_style,
    fig_footnote,
    save_pdf_svg,
    text_on_cmap,
    type_scale,
)
from nor_object_mi.cluster13_frame_share import (  # noqa: E402
    TRIAL_LAB,
    short_model_label,
)
from nor_object_mi.fig_slides_pack import (  # noqa: E402
    NLP_VMAX,
    SEX_LAB,
    _imshow_model_x,
    _model_x_mats,
    _neglog10_p,
    _p_cell_text,
    fig_per_model_kruskal_heatmap,
)
from nor_object_mi.simpler_first_condition_extras import (  # noqa: E402
    N_PERM_DEFAULT,
    PERM_SEED,
    _counts_to_matrix,
    _stable_seed,
)
from nor_object_mi.simpler_first_da import apply_bh_grouped  # noqa: E402
from nor_object_mi.simpler_first_presence import TRIALS  # noqa: E402
from nor_object_mi.simpler_first_q2 import permanova_braycurtis  # noqa: E402

DEFAULT_PACK = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\slides_pack\among_animal_beta"
)
DEFAULT_ART_ROOT = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\archive"
)

# (wire session, ladder folder tag) — absorb <3 clean tables
SESSION_TAGS: tuple[tuple[str, str], ...] = (
    ("NOR_BL", "condition_ladder_NOR_BL_clean"),
    ("NOR_TX", "condition_ladder_clean"),
    ("NOR_REC3hr", "condition_ladder_NOR_REC3hr_clean"),
    ("NOR_REC11hr", "condition_ladder_NOR_REC11hr_clean"),
)

TRIAL_FROM_LAYER = {
    "no_obj": "no_obj",
    "identical_obj": "id_obj",
    "novel_obj": "nvl_obj",
    "id_obj": "id_obj",
    "nvl_obj": "nvl_obj",
}

BOUT_USECOLS = (
    "animal_id",
    "sex",
    "tx",
    "condition_layer",
    "raw_syllable_id",
    "bout_frames",
)

FOOT_MODEL = (
    "Among-animal β: PERMANOVA on Bray–Curtis compositions by condition within "
    "sex (analogy-only on syllables). Panel grid: rows = trial (phase), cols = "
    "sex. Heatmap: y = kpMS model, x = session (stage). Color = −log₁₀"
    "(uncorrected p), clip 4; * = BH q < 0.05 within the panel (model × session). "
    "Not paired step BC; not BC-to-reference; not per-animal BC violins."
)
FOOT_CONSENSUS = (
    "Consensus across 21 kpMS models (syllable ids not portable). Cell = median "
    "−log₁₀(p) of per-model PERMANOVA; annotation = median p / frac models with "
    "BH q < 0.05 in that model’s panel family. Grain: animal × session × trial "
    "compositions (frame_share). DIFFERENCE = Bray–Curtis."
)


def discover_models(art_root: Path) -> list[str]:
    models = sorted(
        p.name
        for p in art_root.glob("paramscan_*")
        if p.is_dir()
        and any((p / tag / "ladder_bout_features.csv").exists() for _, tag in SESSION_TAGS)
    )
    if not models:
        raise FileNotFoundError(f"no paramscan_* ladders under {art_root}")
    return models


def load_ladder_bouts(path: Path, *, session: str) -> pd.DataFrame:
    """Normalize archive ladder CSV → wire session / trial / condition."""
    raw = pd.read_csv(path, usecols=list(BOUT_USECOLS))
    out = pd.DataFrame(
        {
            "animal_id": raw["animal_id"].astype(str),
            "sex": raw["sex"].astype(str),
            "condition": raw["tx"].astype(str),
            "session": session,
            "trial": raw["condition_layer"].map(TRIAL_FROM_LAYER),
            "raw_syllable_id": pd.to_numeric(raw["raw_syllable_id"], errors="coerce"),
            "bout_frames": pd.to_numeric(raw["bout_frames"], errors="coerce"),
        }
    )
    out = out[out["trial"].isin(TRIALS) & out["condition"].isin(CONDITION_ORDER)]
    out = out[np.isfinite(out["bout_frames"]) & (out["bout_frames"] > 0)]
    out = out[np.isfinite(out["raw_syllable_id"])]
    return out.reset_index(drop=True)


def animal_counts_table(bouts: pd.DataFrame) -> pd.DataFrame:
    """One row per animal × trial with ``counts`` dict (frame_share mass)."""
    rows: list[dict[str, object]] = []
    keys = ["animal_id", "sex", "condition", "session", "trial"]
    for key_vals, g in bouts.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        counts = g.groupby("raw_syllable_id")["bout_frames"].sum()
        cm = {int(k): float(v) for k, v in counts.items() if float(v) > 0}
        if not cm:
            continue
        rows.append({**key_map, "counts": cm})
    return pd.DataFrame(rows)


def mean_within_between_bc(P: np.ndarray, groups: np.ndarray) -> tuple[float, float]:
    """Mean pairwise BC within condition arms vs between arms."""
    n = int(P.shape[0])
    if n < 2:
        return float("nan"), float("nan")
    d = squareform(pdist(P, metric="braycurtis"))
    within: list[float] = []
    between: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            dij = float(d[i, j])
            if not np.isfinite(dij):
                continue
            if groups[i] == groups[j]:
                within.append(dij)
            else:
                between.append(dij)
    w = float(np.mean(within)) if within else float("nan")
    b = float(np.mean(between)) if between else float("nan")
    return w, b


def permanova_cell(
    ac: pd.DataFrame,
    *,
    session: str,
    trial: str,
    sex: str,
    model: str,
    n_perm: int,
    seed: int,
) -> dict[str, object]:
    sub = ac[(ac["session"] == session) & (ac["trial"] == trial) & (ac["sex"] == sex)]
    meta, P, _syll = _counts_to_matrix(sub)
    empty = {
        "model": model,
        "session": session,
        "trial": trial,
        "sex": sex,
        "test": "permanova",
        "distance": "braycurtis",
        "metric": "braycurtis_composition",
        "F": float("nan"),
        "p": float("nan"),
        "n": 0,
        "n_perm": 0,
        "mean_bc_within": float("nan"),
        "mean_bc_between": float("nan"),
        "delta_bc_between_minus_within": float("nan"),
        **{f"n_{c}": 0 for c in CONDITION_ORDER},
    }
    if meta.empty or P.shape[0] < 4:
        return empty
    groups = meta["condition"].to_numpy()
    for c in CONDITION_ORDER:
        empty[f"n_{c}"] = int(np.sum(groups == c))
    if any(int(empty[f"n_{c}"]) < 2 for c in CONDITION_ORDER):
        empty["n"] = int(P.shape[0])
        return empty
    rec = permanova_braycurtis(
        P,
        groups,
        n_perm=n_perm,
        seed=_stable_seed(model, session, trial, sex, base=seed),
    )
    w, b = mean_within_between_bc(P, groups)
    return {
        "model": model,
        "session": session,
        "trial": trial,
        "sex": sex,
        "metric": "braycurtis_composition",
        "mean_bc_within": w,
        "mean_bc_between": b,
        "delta_bc_between_minus_within": (
            b - w if np.isfinite(b) and np.isfinite(w) else float("nan")
        ),
        **{k: rec[k] for k in ("test", "distance", "F", "p", "n", "n_perm", "seed")},
        **{f"n_{c}": int(empty[f"n_{c}"]) for c in CONDITION_ORDER},
    }


def run_permanova_all_models(
    art_root: Path,
    *,
    n_perm: int = N_PERM_DEFAULT,
    seed: int = PERM_SEED,
) -> pd.DataFrame:
    models = discover_models(art_root)
    rows: list[dict[str, object]] = []
    n_jobs = len(models) * len(SESSION_TAGS)
    done = 0
    for model in models:
        art = art_root / model
        parts: list[pd.DataFrame] = []
        for session, tag in SESSION_TAGS:
            done += 1
            path = art / tag / "ladder_bout_features.csv"
            if not path.exists():
                print(f"[{done}/{n_jobs}] MISSING {model} {session}", flush=True)
                continue
            print(f"[{done}/{n_jobs}] load {model} {session}", flush=True)
            parts.append(load_ladder_bouts(path, session=session))
        if not parts:
            continue
        bouts = pd.concat(parts, ignore_index=True)
        ac = animal_counts_table(bouts)
        print(f"  PERMANOVA {model}  animals×cells={len(ac)}", flush=True)
        for session in SESSIONS:
            for trial in TRIALS:
                for sex in SEX_ORDER:
                    rows.append(
                        permanova_cell(
                            ac,
                            session=session,
                            trial=trial,
                            sex=sex,
                            model=model,
                            n_perm=n_perm,
                            seed=seed,
                        )
                    )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return apply_bh_grouped(out, ["trial", "sex"])


def consensus_across_models(per_model: pd.DataFrame) -> pd.DataFrame:
    """Median p / F / ΔBC and frac FDR hits across models per cell."""
    rows: list[dict[str, object]] = []
    for session in SESSIONS:
        for trial in TRIALS:
            for sex in SEX_ORDER:
                g = per_model[
                    (per_model["session"] == session)
                    & (per_model["trial"] == trial)
                    & (per_model["sex"] == sex)
                ]
                p = pd.to_numeric(g["p"], errors="coerce")
                f = pd.to_numeric(g["F"], errors="coerce")
                db = pd.to_numeric(g["delta_bc_between_minus_within"], errors="coerce")
                hit = g["hit_fdr05"].astype(bool) if "hit_fdr05" in g.columns else pd.Series(False, index=g.index)
                finite_p = p[np.isfinite(p)]
                rows.append(
                    {
                        "session": session,
                        "trial": trial,
                        "sex": sex,
                        "n_models": int(g["model"].nunique()) if len(g) else 0,
                        "n_finite_p": int(finite_p.size),
                        "median_p": float(np.median(finite_p)) if finite_p.size else float("nan"),
                        "median_F": float(np.nanmedian(f.to_numpy(dtype=float))),
                        "median_delta_bc_between_minus_within": float(
                            np.nanmedian(db.to_numpy(dtype=float))
                        ),
                        "frac_hit_fdr05": float(hit.mean()) if len(g) else float("nan"),
                        "n_hit_fdr05": int(hit.sum()),
                    }
                )
    return pd.DataFrame(rows)


def write_pack(pack: Path, per_model: pd.DataFrame, consensus: pd.DataFrame) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    models = sorted(str(x) for x in per_model["model"].unique())
    labels = pd.DataFrame({"model": models, "label": [short_model_label(m) for m in models]})
    per_model.to_csv(pack / "permanova_per_model.csv", index=False)
    consensus.to_csv(pack / "permanova_consensus.csv", index=False)
    labels.to_csv(pack / "model_labels.csv", index=False)
    print(f"wrote {pack / 'permanova_per_model.csv'}  n={len(per_model)}", flush=True)
    print(f"wrote {pack / 'permanova_consensus.csv'}  n={len(consensus)}", flush=True)


def fig_per_model(per_model: pd.DataFrame, labels: pd.DataFrame, out: Path, *, dest: str) -> None:
    # Reuse heatmap helper; it expects columns model, p, hit_fdr05, row/x cols.
    fig_per_model_kruskal_heatmap(
        per_model,
        labels,
        out,
        dest=dest,
        row_col="trial",
        row_values=list(TRIALS),
        row_lab=TRIAL_LAB,
        x_col="session",
        x_values=list(SESSIONS),
        x_lab=SESSION_SHORT,
        stem="fig_bc_among_animal_per_model_permanova",
        title="Among-animal β · per-model PERMANOVA (Bray–Curtis ~ condition)",
        footnote=FOOT_MODEL,
    )


def fig_consensus(consensus: pd.DataFrame, out: Path, *, dest: str) -> None:
    """3×2 trial × sex; heatmap y unused — use session as x, single row of cells via imshow of sessions."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 12.0 if dest == "slides" else 9.0
    fig_h = 8.5 if dest == "slides" else 7.0
    fig, axes = plt.subplots(len(TRIALS), len(SEX_ORDER), figsize=(fig_w, fig_h), squeeze=False)
    fig.subplots_adjust(left=0.10, right=0.90, top=0.90, bottom=0.10, hspace=0.35, wspace=0.18)
    im = None
    for i, trial in enumerate(TRIALS):
        for j, sex in enumerate(SEX_ORDER):
            ax = axes[i, j]
            # 1 × n_sessions row as a strip, or n_sessions as a 1-row heatmap
            pmat = np.full((1, len(SESSIONS)), np.nan)
            hits = np.zeros((1, len(SESSIONS)), dtype=bool)
            fracs = np.full(len(SESSIONS), np.nan)
            for k, session in enumerate(SESSIONS):
                cell = consensus[
                    (consensus["session"] == session)
                    & (consensus["trial"] == trial)
                    & (consensus["sex"] == sex)
                ]
                if len(cell) == 1:
                    pmat[0, k] = float(cell["median_p"].iloc[0])
                    fracs[k] = float(cell["frac_hit_fdr05"].iloc[0])
                    hits[0, k] = fracs[k] >= 0.5  # majority-model mark
            nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
            im = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
            ax.set_yticks([0])
            ax.set_yticklabels([TRIAL_LAB[trial]] if j == 0 else [""], fontsize=ts["annotation"])
            ax.set_xticks(range(len(SESSIONS)))
            ax.set_xticklabels(
                [SESSION_SHORT[s] for s in SESSIONS],
                fontsize=ts["annotation"],
                rotation=35,
                ha="right",
            )
            if i == 0:
                ax.set_title(SEX_LAB[sex], loc="left", fontweight="bold", color=INK)
            for k in range(len(SESSIONS)):
                p = pmat[0, k]
                nlp_v = nlp[0, k]
                if not (np.isfinite(p) and np.isfinite(nlp_v)):
                    continue
                mark = "*" if hits[0, k] else ""
                frac = fracs[k]
                frac_s = f"\n{frac:.0%}" if np.isfinite(frac) else ""
                ax.text(
                    k,
                    0,
                    mark + _p_cell_text(p) + frac_s,
                    ha="center",
                    va="center",
                    fontsize=ts["cell"] * 0.75,
                    color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
                )
    cax = fig.add_axes([0.92, 0.30, 0.015, 0.40])
    fig.colorbar(im, cax=cax, label="median −log₁₀(p)  (clip 4)")
    fig.suptitle(
        "Among-animal β · consensus PERMANOVA across models (Bray–Curtis ~ condition)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(fig, FOOT_CONSENSUS, y=0.02, color=MUTE)
    save_pdf_svg(fig, out / "fig_bc_among_animal_consensus_permanova")


def fig_combined(
    per_model: pd.DataFrame,
    consensus: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
) -> None:
    """Consensus strips (left) + per-model heatmaps (right)."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 18.0 if dest == "slides" else 14.0
    fig_h = 8.5 if dest == "slides" else 7.2
    fig = plt.figure(figsize=(fig_w, fig_h))
    outer = fig.add_gridspec(
        1, 2, width_ratios=[0.85, 1.35], left=0.05, right=0.93, top=0.88, bottom=0.12, wspace=0.20
    )
    gs_c = outer[0].subgridspec(len(TRIALS), len(SEX_ORDER), hspace=0.40, wspace=0.15)
    gs_h = outer[1].subgridspec(len(TRIALS), len(SEX_ORDER), hspace=0.35, wspace=0.12)

    im_c = None
    for i, trial in enumerate(TRIALS):
        for j, sex in enumerate(SEX_ORDER):
            ax = fig.add_subplot(gs_c[i, j])
            pmat = np.full((1, len(SESSIONS)), np.nan)
            hits = np.zeros((1, len(SESSIONS)), dtype=bool)
            fracs = np.full(len(SESSIONS), np.nan)
            for k, session in enumerate(SESSIONS):
                cell = consensus[
                    (consensus["session"] == session)
                    & (consensus["trial"] == trial)
                    & (consensus["sex"] == sex)
                ]
                if len(cell) == 1:
                    pmat[0, k] = float(cell["median_p"].iloc[0])
                    fracs[k] = float(cell["frac_hit_fdr05"].iloc[0])
                    hits[0, k] = fracs[k] >= 0.5
            nlp = np.vectorize(_neglog10_p, otypes=[float])(pmat)
            im_c = ax.imshow(nlp, cmap="viridis", vmin=0.0, vmax=NLP_VMAX, aspect="auto")
            ax.set_yticks([0])
            ax.set_yticklabels([TRIAL_LAB[trial]] if j == 0 else [""], fontsize=ts["annotation"] * 0.9)
            ax.set_xticks(range(len(SESSIONS)))
            ax.set_xticklabels(
                [SESSION_SHORT[s] for s in SESSIONS] if i == len(TRIALS) - 1 else [],
                fontsize=ts["annotation"] * 0.85,
                rotation=35,
                ha="right",
            )
            if i == 0:
                ax.set_title(f"consensus · {SEX_LAB[sex]}", loc="left", fontweight="bold", color=INK, fontsize=ts["annotation"])
            for k in range(len(SESSIONS)):
                p = pmat[0, k]
                nlp_v = nlp[0, k]
                if not (np.isfinite(p) and np.isfinite(nlp_v)):
                    continue
                mark = "*" if hits[0, k] else ""
                frac = fracs[k]
                frac_s = f"\n{frac:.0%}" if np.isfinite(frac) else ""
                ax.text(
                    k,
                    0,
                    mark + _p_cell_text(p) + frac_s,
                    ha="center",
                    va="center",
                    fontsize=ts["cell"] * 0.65,
                    color=text_on_cmap(nlp_v, vmin=0.0, vmax=NLP_VMAX),
                )

    lab_map = dict(zip(labels["model"].astype(str), labels["label"].astype(str)))
    models = sorted(str(x) for x in per_model["model"].unique())
    y_labels = [lab_map.get(m, m.split("_")[-1][:12]) for m in models]
    x_labels = [SESSION_SHORT[s] for s in SESSIONS]
    im_h = None
    for i, trial in enumerate(TRIALS):
        for j, sex in enumerate(SEX_ORDER):
            ax = fig.add_subplot(gs_h[i, j])
            pmat, hits = _model_x_mats(
                per_model,
                models=models,
                x_values=list(SESSIONS),
                x_col="session",
                row_value=trial,
                row_col="trial",
                sex=sex,
            )
            im_h = _imshow_model_x(
                ax,
                pmat,
                hits,
                y_labels=y_labels,
                x_labels=x_labels,
                title=f"per-model · {SEX_LAB[sex]}" if i == 0 else "",
                ts=ts,
                show_ylabel=(j == 0),
                ylabel="",
            )
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\nmodel", fontsize=ts["annotation"])

    cax = fig.add_axes([0.945, 0.28, 0.012, 0.45])
    fig.colorbar(im_h if im_h is not None else im_c, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        "Among-animal β · Bray–Curtis PERMANOVA by condition  (consensus | per-model)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(fig, FOOT_CONSENSUS + "  " + FOOT_MODEL, y=0.02, color=MUTE)
    save_pdf_svg(fig, out / "fig_bc_among_animal_permanova_combined")


def fig_effect_size(consensus: pd.DataFrame, out: Path, *, dest: str) -> None:
    """Median (BC_between − BC_within) across models — D companion."""
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig, axes = plt.subplots(len(TRIALS), len(SEX_ORDER), figsize=(10.5, 7.5), squeeze=False)
    fig.subplots_adjust(left=0.10, right=0.90, top=0.90, bottom=0.12, hspace=0.35, wspace=0.18)
    vals = pd.to_numeric(consensus["median_delta_bc_between_minus_within"], errors="coerce")
    vmax = float(np.nanmax(np.abs(vals.to_numpy(dtype=float)))) if vals.notna().any() else 0.1
    vmax = max(0.05, vmax)
    im = None
    for i, trial in enumerate(TRIALS):
        for j, sex in enumerate(SEX_ORDER):
            ax = axes[i, j]
            mat = np.full((1, len(SESSIONS)), np.nan)
            for k, session in enumerate(SESSIONS):
                cell = consensus[
                    (consensus["session"] == session)
                    & (consensus["trial"] == trial)
                    & (consensus["sex"] == sex)
                ]
                if len(cell) == 1:
                    mat[0, k] = float(cell["median_delta_bc_between_minus_within"].iloc[0])
            im = ax.imshow(mat, cmap="coolwarm", vmin=-vmax, vmax=vmax, aspect="auto")
            ax.set_yticks([0])
            ax.set_yticklabels([TRIAL_LAB[trial]] if j == 0 else [""], fontsize=ts["annotation"])
            ax.set_xticks(range(len(SESSIONS)))
            ax.set_xticklabels(
                [SESSION_SHORT[s] for s in SESSIONS],
                fontsize=ts["annotation"],
                rotation=35,
                ha="right",
            )
            if i == 0:
                ax.set_title(SEX_LAB[sex], loc="left", fontweight="bold", color=INK)
            for k in range(len(SESSIONS)):
                v = mat[0, k]
                if not np.isfinite(v):
                    continue
                ax.text(k, 0, f"{v:+.2f}", ha="center", va="center", fontsize=ts["cell"] * 0.8, color=INK)
    cax = fig.add_axes([0.92, 0.30, 0.015, 0.40])
    fig.colorbar(im, cax=cax, label="median (BC_between − BC_within)")
    fig.suptitle(
        "Among-animal β · effect size companion (mean pairwise BC between − within)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_footnote(
        fig,
        "D only: mean pairwise Bray–Curtis among animals in different condition arms "
        "minus mean pairwise BC within arms; median across 21 models. Not a test.",
        y=0.02,
        color=MUTE,
    )
    save_pdf_svg(fig, out / "fig_bc_among_animal_effect_size")


def write_info(pack: Path, *, n_perm: int) -> None:
    text = f"""# INFO — among-animal β (Bray–Curtis PERMANOVA)

Group partition on **syllable compositions** within each `session × trial` cell.
Independent animals; DIFFERENCE matrix = Bray–Curtis; I = PERMANOVA by
`condition` within sex (analogy-only).

| | |
| --- | --- |
| These files | `{pack.as_posix()}` |
| Dest | slides |
| How regenerated | `uv run python scratch/nor_object_mi/among_animal_beta_slides_pack.py --rebuild` |
| n_perm | {n_perm} |

## Questions

1. Within sex, at each `session × trial`, does **condition** separate animals in
   Bray–Curtis composition space?
2. Across 21 kpMS models, is that separation consistent (frac FDR hit / median p)?

## Deferred

1. **Reference BC:** BC(animal, fixed reference composition) — atypicality scalar.
2. Already shipped: **paired step BC** (`slides_pack/braycurtis/`).

## Grain

| Unit | Value |
| ---- | ----- |
| composition | animal × session × trial (frame_share over `raw_syllable_id`) |
| test cell | model × session × trial × sex |
| BH family | model × session within each trial × sex panel |

**What this is not:** not paired left↔right BC; not per-animal BC violins; not DA.

## Artifacts

| File | Unit |
| ---- | ---- |
| `permanova_per_model.csv` | model × session × trial × sex |
| `permanova_consensus.csv` | session × trial × sex (across models) |
| `figures/fig_bc_among_animal_permanova_combined.{{pdf,svg}}` | consensus + per-model |
| `figures/fig_bc_among_animal_effect_size.{{pdf,svg}}` | BC_between − BC_within |

## Source

Archive clean ladders under `_nor_object_mi/archive/paramscan_*/condition_ladder*_clean/`.
"""
    (pack / "INFO_slides_pack.md").write_text(text, encoding="utf-8")
    print(f"wrote {pack / 'INFO_slides_pack.md'}")


def write_figures_md(out: Path) -> None:
    text = """# Figures — among-animal β (PERMANOVA)

| Stem | Question | Layout | D/I |
| ---- | -------- | ------ | --- |
| `fig_bc_among_animal_permanova_combined` | Condition partition compositions? | consensus + per-model | I |
| `fig_bc_among_animal_per_model_permanova` | Per-model only | 3×2 heatmaps | I |
| `fig_bc_among_animal_consensus_permanova` | Across-model median p | 3×2 strips | I summary |
| `fig_bc_among_animal_effect_size` | Between − within mean BC | 3×2 | D |

```powershell
uv run python scratch/nor_object_mi/among_animal_beta_slides_pack.py --rebuild
```
"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "FIGURES.md").write_text(text, encoding="utf-8")
    print(f"wrote {out / 'FIGURES.md'}")


def run(*, pack: Path, art_root: Path, dest: str, rebuild: bool, n_perm: int) -> None:
    out = pack / "figures"
    out.mkdir(parents=True, exist_ok=True)
    needed = ("permanova_per_model.csv", "permanova_consensus.csv", "model_labels.csv")
    if rebuild or any(not (pack / n).exists() for n in needed):
        per_model = run_permanova_all_models(art_root, n_perm=n_perm)
        consensus = consensus_across_models(per_model)
        write_pack(pack, per_model, consensus)
    else:
        per_model = pd.read_csv(pack / "permanova_per_model.csv")
        consensus = pd.read_csv(pack / "permanova_consensus.csv")
    labels = pd.read_csv(pack / "model_labels.csv")
    fig_per_model(per_model, labels, out, dest=dest)
    fig_consensus(consensus, out, dest=dest)
    fig_combined(per_model, consensus, labels, out, dest=dest)
    fig_effect_size(consensus, out, dest=dest)
    write_info(pack, n_perm=n_perm)
    write_figures_md(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    ap.add_argument("--art-root", type=Path, default=DEFAULT_ART_ROOT)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--n-perm", type=int, default=N_PERM_DEFAULT)
    args = ap.parse_args(argv)
    run(
        pack=args.pack,
        art_root=args.art_root,
        dest=args.dest,
        rebuild=args.rebuild,
        n_perm=int(args.n_perm),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
