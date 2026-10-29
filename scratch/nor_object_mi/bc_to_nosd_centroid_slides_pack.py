"""BC to noSD centroid — atypicality vs sleep-deprivation control composition.

**Claim (level):** Within sex, at each ``session × trial``, does **condition**
change how far an animal’s syllable composition is from the **noSD centroid**
(Bray–Curtis dissimilarity)?

Reference = mean frame-share vector of noSD animals in the same
``model × session × trial × sex`` cell (renormalized). **Leave-one-out** for
noSD animals so they are not scored against a centroid that includes themselves.

**Not** paired step BC; **not** among-animal PERMANOVA. Syllable ids model-local
→ score per model, then median across models for consensus violins.

Source: archive ``*_clean`` ladders (same as among-animal β pack).

Regen::

    uv run python scratch/nor_object_mi/bc_to_nosd_centroid_slides_pack.py --rebuild
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial.distance import braycurtis

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi._pub_style import (  # noqa: E402
    FIGSIZE_SLIDES,
    INK,
    SESSION_SHORT,
    SESSIONS,
    SEX_ORDER,
    apply_style,
    condition_sex_legend_handles,
    fig_legend_and_footnote,
    save_pdf_svg,
    type_scale,
)
from nor_object_mi.among_animal_beta_slides_pack import (  # noqa: E402
    DEFAULT_ART_ROOT,
    SESSION_TAGS,
    animal_counts_table,
    discover_models,
    load_ladder_bouts,
)
from nor_object_mi.cluster13_frame_share import (  # noqa: E402
    TRIAL_LAB,
    animal_median_frame_share,
    kruskal_by_session_trial_sex,
    kruskal_per_model_level,
    short_model_label,
)
from nor_object_mi.fig_slides_pack import (  # noqa: E402
    SEX_LAB,
    _annotate_fm,
    _draw_condition_sex_violins,
    _imshow_model_x,
    _model_x_mats,
    _y_lim_from,
    fig_per_model_kruskal_heatmap,
)
from nor_object_mi.simpler_first_condition_extras import _counts_to_matrix  # noqa: E402
from nor_object_mi.simpler_first_presence import TRIALS  # noqa: E402

DEFAULT_PACK = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\slides_pack\bc_to_nosd_centroid"
)

CONTROL = "noSD"
YCOL = "p"  # reuse level violin helpers (absolute atypicality scalar)
METRIC_LAB = "BC to noSD centroid"

FOOT_LEVEL = (
    "Grain: animal × session × trial. Point = median Bray–Curtis to the noSD "
    "centroid across 21 kpMS models; whiskers = ±½ across-model IQR (salt). "
    "Centroid = mean frame-share of noSD animals in the same model × session × "
    "trial × sex cell (renormalized). Leave-one-out for noSD animals. Six "
    "violins = condition × sex. Kruskal within sex; * = BH q < 0.05 in the "
    "24-cell family. Not paired step BC; not among-animal PERMANOVA."
)
FOOT_MODEL = (
    "Per-model Kruskal on BC(animal, noSD centroid) ~ condition within sex. "
    "Panel grid: rows = trial, cols = sex. Heatmap: y = kpMS model, x = session. "
    "Color = −log₁₀(p), clip 4; * = BH q < 0.05 within panel (model × session)."
)


def _renorm(v: np.ndarray) -> np.ndarray:
    s = float(v.sum())
    if s <= 0 or not np.isfinite(s):
        return v * np.nan
    return v / s


def bc_to_nosd_centroid_cell(
    ac: pd.DataFrame,
    *,
    session: str,
    trial: str,
    sex: str,
    model: str,
) -> pd.DataFrame:
    """Per-animal BC to noSD centroid (LOO for noSD) in one cell."""
    sub = ac[(ac["session"] == session) & (ac["trial"] == trial) & (ac["sex"] == sex)].copy()
    if sub.empty:
        return pd.DataFrame(
            columns=["model", "animal_id", "sex", "condition", "session", "trial", YCOL, "n_nosd_ref"]
        )
    meta, P, _syll = _counts_to_matrix(sub)
    if meta.empty or P.shape[0] == 0:
        return pd.DataFrame(
            columns=["model", "animal_id", "sex", "condition", "session", "trial", YCOL, "n_nosd_ref"]
        )
    # align meta rows with P ( _counts_to_matrix drops empty counts )
    conditions = meta["condition"].astype(str).to_numpy()
    nosd_idx = np.flatnonzero(conditions == CONTROL)
    n_nosd = int(nosd_idx.size)
    rows: list[dict[str, object]] = []
    for i in range(P.shape[0]):
        if conditions[i] == CONTROL:
            others = nosd_idx[nosd_idx != i]
            if others.size < 1:
                bc = float("nan")
                n_ref = 0
            else:
                cen = _renorm(P[others].mean(axis=0))
                bc = float(braycurtis(P[i], cen)) if np.isfinite(cen).all() else float("nan")
                n_ref = int(others.size)
        else:
            if n_nosd < 1:
                bc = float("nan")
                n_ref = 0
            else:
                cen = _renorm(P[nosd_idx].mean(axis=0))
                bc = float(braycurtis(P[i], cen)) if np.isfinite(cen).all() else float("nan")
                n_ref = n_nosd
        rows.append(
            {
                "model": model,
                "animal_id": str(meta["animal_id"].iloc[i]),
                "sex": sex,
                "condition": str(conditions[i]),
                "session": session,
                "trial": trial,
                YCOL: bc,
                "n_nosd_ref": n_ref,
            }
        )
    return pd.DataFrame(rows)


def score_model(ac: pd.DataFrame, *, model: str) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for session in SESSIONS:
        for trial in TRIALS:
            for sex in SEX_ORDER:
                parts.append(
                    bc_to_nosd_centroid_cell(ac, session=session, trial=trial, sex=sex, model=model)
                )
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def run_all_models(art_root: Path) -> pd.DataFrame:
    models = discover_models(art_root)
    parts: list[pd.DataFrame] = []
    n_jobs = len(models) * len(SESSION_TAGS)
    done = 0
    for model in models:
        art = art_root / model
        bout_parts: list[pd.DataFrame] = []
        for session, tag in SESSION_TAGS:
            done += 1
            path = art / tag / "ladder_bout_features.csv"
            if not path.exists():
                print(f"[{done}/{n_jobs}] MISSING {model} {session}", flush=True)
                continue
            print(f"[{done}/{n_jobs}] load {model} {session}", flush=True)
            bout_parts.append(load_ladder_bouts(path, session=session))
        if not bout_parts:
            continue
        bouts = pd.concat(bout_parts, ignore_index=True)
        ac = animal_counts_table(bouts)
        print(f"  score BC->noSD {model}  n_animals_cells={len(ac)}", flush=True)
        parts.append(score_model(ac, model=model))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def build_pack(levels_model: pd.DataFrame) -> dict[str, pd.DataFrame]:
    med = animal_median_frame_share(levels_model)
    kr_level = kruskal_by_session_trial_sex(med, col=YCOL)
    kr_model = kruskal_per_model_level(levels_model, col=YCOL)
    models = sorted(str(x) for x in levels_model["model"].unique())
    return {
        "levels_model": levels_model,
        "animal_level": med,
        "kruskal_level": kr_level,
        "kruskal_per_model_level": kr_model,
        "model_labels": pd.DataFrame({"model": models, "label": [short_model_label(m) for m in models]}),
    }


def write_pack(pack: Path, tables: dict[str, pd.DataFrame]) -> None:
    pack.mkdir(parents=True, exist_ok=True)
    writes = (
        ("bc_nosd_animal_level.csv", tables["animal_level"]),
        ("bc_nosd_level_kruskal.csv", tables["kruskal_level"]),
        ("bc_nosd_per_model_level_kruskal.csv", tables["kruskal_per_model_level"]),
        ("bc_nosd_levels_model.csv", tables["levels_model"]),
        ("bc_nosd_model_labels.csv", tables["model_labels"]),
    )
    for name, df in writes:
        df.to_csv(pack / name, index=False)
        print(f"wrote {pack / name}  n={len(df)}", flush=True)


def load_pack(pack: Path) -> dict[str, pd.DataFrame]:
    return {
        "animal_level": pd.read_csv(pack / "bc_nosd_animal_level.csv"),
        "kruskal_level": pd.read_csv(pack / "bc_nosd_level_kruskal.csv"),
        "kruskal_per_model_level": pd.read_csv(pack / "bc_nosd_per_model_level_kruskal.csv"),
        "model_labels": pd.read_csv(pack / "bc_nosd_model_labels.csv"),
    }


def fig_level(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 8.0)
    fig = plt.figure(figsize=(fig_w * 1.08, fig_h + 0.8))
    gs = fig.add_gridspec(
        len(TRIALS),
        len(SESSIONS),
        left=0.07,
        right=0.98,
        top=0.88,
        bottom=0.22,
        hspace=0.42,
        wspace=0.30,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, YCOL)
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial"] == trial)]
            _draw_condition_sex_violins(
                ax, panel, dest=dest, rng=rng, xlabel=(i == len(TRIALS) - 1), ycol=YCOL
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial": trial}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\n{METRIC_LAB}")
    fig.suptitle(
        f"{METRIC_LAB} by condition × sex  (six violins; LOO for noSD)",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), FOOT_LEVEL, dest=dest)
    save_pdf_svg(fig, out / "fig_bc_to_nosd_level_by_sex")


def fig_combined(
    med: pd.DataFrame,
    kr: pd.DataFrame,
    kr_model: pd.DataFrame,
    labels: pd.DataFrame,
    out: Path,
    *,
    dest: str,
) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 18.0 if dest == "slides" else 14.0
    fig_h = 8.2 if dest == "slides" else 7.0
    fig = plt.figure(figsize=(fig_w, fig_h))
    outer = fig.add_gridspec(
        1, 2, width_ratios=[1.55, 1.0], left=0.05, right=0.93, top=0.88, bottom=0.16, wspace=0.18
    )
    gs_v = outer[0].subgridspec(len(TRIALS), len(SESSIONS), hspace=0.42, wspace=0.28)
    gs_h = outer[1].subgridspec(len(TRIALS), len(SEX_ORDER), hspace=0.35, wspace=0.12)

    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, YCOL)
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs_v[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial"] == trial)]
            _draw_condition_sex_violins(
                ax, panel, dest=dest, rng=rng, xlabel=(i == len(TRIALS) - 1), ycol=YCOL
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial": trial}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\n{METRIC_LAB}")

    lab_map = dict(zip(labels["model"].astype(str), labels["label"].astype(str)))
    models = sorted(str(x) for x in kr_model["model"].unique())
    y_labels = [lab_map.get(m, m.split("_")[-1][:12]) for m in models]
    x_labels = [SESSION_SHORT[s] for s in SESSIONS]
    im = None
    for i, trial in enumerate(TRIALS):
        for j, sex in enumerate(SEX_ORDER):
            ax = fig.add_subplot(gs_h[i, j])
            pmat, hits = _model_x_mats(
                kr_model,
                models=models,
                x_values=list(SESSIONS),
                x_col="session",
                row_value=trial,
                row_col="trial",
                sex=sex,
            )
            im = _imshow_model_x(
                ax,
                pmat,
                hits,
                y_labels=y_labels,
                x_labels=x_labels,
                title=SEX_LAB[sex] if i == 0 else "",
                ts=ts,
                show_ylabel=(j == 0),
                ylabel="",
            )
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\nmodel", fontsize=ts["annotation"])

    cax = fig.add_axes([0.945, 0.28, 0.012, 0.45])
    fig.colorbar(im, cax=cax, label="−log₁₀(p)  (clip 4)")
    fig.suptitle(
        f"{METRIC_LAB} by condition × sex  ·  Per-model Kruskal",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(
        fig,
        condition_sex_legend_handles(dest=dest),
        FOOT_LEVEL + "  " + FOOT_MODEL,
        dest=dest,
    )
    save_pdf_svg(fig, out / "fig_bc_to_nosd_level_combined")


def write_info(pack: Path) -> None:
    text = f"""# INFO — BC to noSD centroid (atypicality)

Level lattice only. Each animal’s syllable composition is scored by Bray–Curtis
dissimilarity to the **noSD** mean composition in the same
`model × session × trial × sex` cell.

| | |
| --- | --- |
| These files | `{pack.as_posix()}` |
| Dest | slides |
| How regenerated | `uv run python scratch/nor_object_mi/bc_to_nosd_centroid_slides_pack.py --rebuild` |

**Leave-one-out:** for noSD animals, the centroid excludes that animal.
**kpMS** = keypoint-MoSeq. **BH** = Benjamini–Hochberg. **Kruskal** =
Kruskal–Wallis.

## Question

Within sex, does **condition** change atypicality vs the noSD centroid at each
`session × trial`?

## Related

| Pack | Claim |
| ---- | ----- |
| `slides_pack/braycurtis/` | paired step BC (left↔right) |
| `slides_pack/among_animal_beta/` | PERMANOVA group partition |
| this pack | BC to fixed noSD reference |

## Grain

| Family | Point | Value |
| ------ | ----- | ----- |
| level | animal × session × trial | median BC(p, noSD centroid) across 21 models |

**Hit rule:** BH `q_bh < 0.05` in the 24-cell level family
(4 sessions × 3 trials × 2 sexes).

## Artifacts

| File | Unit |
| ---- | ---- |
| `bc_nosd_animal_level.csv` | animal × session × trial |
| `bc_nosd_level_kruskal.csv` | session × trial × sex |
| `figures/fig_bc_to_nosd_level_combined.{{pdf,svg}}` | violins + per-model heatmap |
"""
    (pack / "INFO_slides_pack.md").write_text(text, encoding="utf-8")
    print(f"wrote {pack / 'INFO_slides_pack.md'}")


def write_figures_md(out: Path) -> None:
    text = """# Figures — BC to noSD centroid

| Stem | Question | Layout | D/I |
| ---- | -------- | ------ | --- |
| `fig_bc_to_nosd_level_combined` | Condition × sex on atypicality? | 3×4 + 3×2 | D + Kruskal |
| `fig_bc_to_nosd_level_by_sex` | Level violins only | 3×4 | D + Kruskal |
| `fig_bc_to_nosd_per_model_level_kruskal` | Per-model | 3×2 | I |

```powershell
uv run python scratch/nor_object_mi/bc_to_nosd_centroid_slides_pack.py --rebuild
```
"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "FIGURES.md").write_text(text, encoding="utf-8")
    print(f"wrote {out / 'FIGURES.md'}")


def run(*, pack: Path, art_root: Path, dest: str, rebuild: bool) -> None:
    out = pack / "figures"
    out.mkdir(parents=True, exist_ok=True)
    needed = (
        "bc_nosd_animal_level.csv",
        "bc_nosd_level_kruskal.csv",
        "bc_nosd_per_model_level_kruskal.csv",
        "bc_nosd_model_labels.csv",
    )
    print(f"=== bc_to_nosd_centroid -> {pack} ===", flush=True)
    if rebuild or any(not (pack / n).exists() for n in needed):
        levels = run_all_models(art_root)
        tables = build_pack(levels)
        write_pack(pack, tables)
    else:
        tables = load_pack(pack)

    fig_level(tables["animal_level"], tables["kruskal_level"], out, dest=dest)
    fig_combined(
        tables["animal_level"],
        tables["kruskal_level"],
        tables["kruskal_per_model_level"],
        tables["model_labels"],
        out,
        dest=dest,
    )
    fig_per_model_kruskal_heatmap(
        tables["kruskal_per_model_level"],
        tables["model_labels"],
        out,
        dest=dest,
        row_col="trial",
        row_values=list(TRIALS),
        row_lab=TRIAL_LAB,
        x_col="session",
        x_values=list(SESSIONS),
        x_lab=SESSION_SHORT,
        stem="fig_bc_to_nosd_per_model_level_kruskal",
        title=f"Per-model Kruskal on {METRIC_LAB} ~ condition",
        footnote=FOOT_MODEL,
    )
    write_info(pack)
    write_figures_md(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    ap.add_argument("--art-root", type=Path, default=DEFAULT_ART_ROOT)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args(argv)
    run(pack=args.pack, art_root=args.art_root, dest=args.dest, rebuild=args.rebuild)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
