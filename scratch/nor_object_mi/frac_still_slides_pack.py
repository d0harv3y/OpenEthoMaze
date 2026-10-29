"""Slides pack for IMPRESS ``frac_still`` = time_immobile_s / duration_s.

Same consensus violin lattice as the HDBSCAN cluster frame-share packs
(level / trial-step Δ / session-step Δ + Kruskal), **without** per-model
heatmaps or grid videos. Ambulation is a single scalar clock — no kpMS axis.

Regen (OpenEthoMaze repo root)::

    uv run python scratch/nor_object_mi/frac_still_slides_pack.py --rebuild
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

from nor_object_mi._pub_style import (  # noqa: E402
    CONDITION_ORDER,
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
from nor_object_mi.cluster13_frame_share import (  # noqa: E402
    SESSION_STEP_LAB,
    SESSION_STEP_NAMES,
    TRIAL_LAB,
    TRIAL_STEP_LAB,
    TRIAL_STEP_NAMES,
    TRIAL_STEPS,
    kruskal_by_session_trial_sex,
    kruskal_by_session_trial_step_sex,
    kruskal_by_trial_session_step_sex,
)
from nor_object_mi.fig_slides_pack import (  # noqa: E402
    _annotate_fm,
    _draw_condition_sex_violins,
    _y_lim_from,
)
from nor_object_mi.simpler_first_presence import TRIALS  # noqa: E402
from nor_object_mi.simpler_first_session_paired import PHASE_STEPS as SESSION_STEP_DEFS  # noqa: E402

DEFAULT_PACK = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\_nor_object_mi\slides_pack\frac_still"
)
DEFAULT_AMBULATION = Path(
    r"D:\sack\datas\impress\moseq_251017"
    r"\thresholded-signal-bouts\impress_ambulation.csv"
)

TRIAL_FROM_NOR = {
    "novel_obj": "nvl_obj",
    "identical_obj": "id_obj",
    "no_obj": "no_obj",
}

FOOT_LEVEL = (
    "Grain: animal × session × trial. Point = frac_still = time_immobile_s / "
    "duration_s from IMPRESS ambulation (fore displacement hysteresis). No "
    "across-model whiskers (single ambulation clock). Six violins = condition × "
    "sex (F then M). Kruskal within sex; * = BH q < 0.05 in the 24-cell family. "
    "Not cluster-13 frame share; not paired Δ; not Wilcoxon vs 0."
)
FOOT_TRIAL_STEP = (
    "Grain: animal × session × trial_step (prose: phase-step). Point = paired "
    "Δ frac_still (right − left trial). Six violins = condition × sex. Kruskal "
    "on Δ ~ condition within sex; * = BH q < 0.05 in the 24-cell family. Not "
    "Wilcoxon vs 0; not raw level; not kpMS syllable share."
)
FOOT_SESSION_STEP = (
    "Grain: animal × trial × session_step (prose: stage-step). Point = paired "
    "Δ frac_still (right − left session). Six violins = condition × sex. "
    "Kruskal on Δ ~ condition within sex; * = BH q < 0.05 in the 36-cell "
    "family. Not Wilcoxon vs 0; not raw level; not kpMS syllable share."
)


def load_frac_still_levels(ambulation_csv: Path) -> pd.DataFrame:
    """Animal × session × trial rows with ``p`` = frac_still."""
    raw = pd.read_csv(ambulation_csv)
    need = {"ID", "phase layer", "condition layer", "duration_s", "sex", "treatment group", "metric", "value"}
    missing = need - set(raw.columns)
    if missing:
        raise ValueError(f"ambulation CSV missing columns: {sorted(missing)}")
    sub = raw[raw["metric"] == "time_immobile_s"].copy()
    if sub.empty:
        raise ValueError("no time_immobile_s rows in ambulation CSV")
    sub["animal_id"] = sub["ID"].astype(str)
    sub["session"] = sub["phase layer"].astype(str)
    sub["trial"] = sub["condition layer"].map(TRIAL_FROM_NOR)
    sub["sex"] = sub["sex"].astype(str)
    sub["condition"] = sub["treatment group"].astype(str)
    sub["duration_s"] = pd.to_numeric(sub["duration_s"], errors="coerce")
    sub["time_immobile_s"] = pd.to_numeric(sub["value"], errors="coerce")
    sub = sub[sub["trial"].isin(TRIALS) & sub["session"].isin(SESSIONS)].copy()
    sub["p"] = sub["time_immobile_s"] / sub["duration_s"]
    out = sub[
        [
            "animal_id",
            "sex",
            "condition",
            "session",
            "trial",
            "p",
            "time_immobile_s",
            "duration_s",
        ]
    ].drop_duplicates(subset=["animal_id", "session", "trial"], keep="first")
    out["iqr_across_models"] = np.nan
    out["n_models"] = 1
    out["n_finite"] = out["p"].notna().astype(int)
    out["session"] = pd.Categorical(out["session"], categories=list(SESSIONS), ordered=True)
    out["trial"] = pd.Categorical(out["trial"], categories=list(TRIALS), ordered=True)
    out["condition"] = pd.Categorical(out["condition"], categories=list(CONDITION_ORDER), ordered=True)
    out["sex"] = pd.Categorical(out["sex"], categories=list(SEX_ORDER), ordered=True)
    return out.sort_values(["animal_id", "session", "trial"]).reset_index(drop=True)


def trial_step_deltas(levels: pd.DataFrame) -> pd.DataFrame:
    """Paired Δ frac_still across trials within session."""
    join_on = ["animal_id", "sex", "condition", "session"]
    parts: list[pd.DataFrame] = []
    for step, left, right in TRIAL_STEPS:
        L = levels[levels["trial"].astype(str) == left]
        R = levels[levels["trial"].astype(str) == right]
        j = L.merge(R, on=join_on, how="inner", suffixes=("_l", "_r"))
        if j.empty:
            continue
        parts.append(
            j.assign(
                trial_step=step,
                delta_p=pd.to_numeric(j["p_r"], errors="coerce")
                - pd.to_numeric(j["p_l"], errors="coerce"),
            )[join_on + ["trial_step", "delta_p"]]
        )
    if not parts:
        return pd.DataFrame(columns=[*join_on, "trial_step", "delta_p", "iqr_across_models", "n_models", "n_finite"])
    out = pd.concat(parts, ignore_index=True)
    out["iqr_across_models"] = np.nan
    out["n_models"] = 1
    out["n_finite"] = out["delta_p"].notna().astype(int)
    out["session"] = pd.Categorical(out["session"], categories=list(SESSIONS), ordered=True)
    out["trial_step"] = pd.Categorical(out["trial_step"], categories=list(TRIAL_STEP_NAMES), ordered=True)
    return out.sort_values(["animal_id", "session", "trial_step"]).reset_index(drop=True)


def session_step_deltas(levels: pd.DataFrame) -> pd.DataFrame:
    """Paired Δ frac_still across sessions within trial."""
    join_on = ["animal_id", "sex", "condition", "trial"]
    parts: list[pd.DataFrame] = []
    for step, left, right in SESSION_STEP_DEFS:
        L = levels[levels["session"].astype(str) == left]
        R = levels[levels["session"].astype(str) == right]
        j = L.merge(R, on=join_on, how="inner", suffixes=("_l", "_r"))
        if j.empty:
            continue
        parts.append(
            j.assign(
                session_step=step,
                delta_p=pd.to_numeric(j["p_r"], errors="coerce")
                - pd.to_numeric(j["p_l"], errors="coerce"),
            )[join_on + ["session_step", "delta_p"]]
        )
    if not parts:
        return pd.DataFrame(
            columns=[*join_on, "session_step", "delta_p", "iqr_across_models", "n_models", "n_finite"]
        )
    out = pd.concat(parts, ignore_index=True)
    out["iqr_across_models"] = np.nan
    out["n_models"] = 1
    out["n_finite"] = out["delta_p"].notna().astype(int)
    out["trial"] = pd.Categorical(out["trial"], categories=list(TRIALS), ordered=True)
    out["session_step"] = pd.Categorical(out["session_step"], categories=list(SESSION_STEP_NAMES), ordered=True)
    return out.sort_values(["animal_id", "trial", "session_step"]).reset_index(drop=True)


def build_frac_still_pack(ambulation_csv: Path) -> dict[str, pd.DataFrame]:
    levels = load_frac_still_levels(ambulation_csv)
    trial_d = trial_step_deltas(levels)
    session_d = session_step_deltas(levels)
    return {
        "animal_frac_still": levels,
        "kruskal_level": kruskal_by_session_trial_sex(levels, col="p"),
        "trial_step_delta": trial_d,
        "kruskal_trial_step": kruskal_by_session_trial_step_sex(trial_d, col="delta_p"),
        "session_step_delta": session_d,
        "kruskal_session_step": kruskal_by_trial_session_step_sex(session_d, col="delta_p"),
    }


def _write_tables(pack: Path, tables: dict[str, pd.DataFrame]) -> None:
    writes = (
        ("frac_still_animal.csv", tables["animal_frac_still"]),
        ("frac_still_kruskal.csv", tables["kruskal_level"]),
        ("frac_still_trial_step_delta.csv", tables["trial_step_delta"]),
        ("frac_still_trial_step_kruskal.csv", tables["kruskal_trial_step"]),
        ("frac_still_session_step_delta.csv", tables["session_step_delta"]),
        ("frac_still_session_step_kruskal.csv", tables["kruskal_session_step"]),
    )
    for name, df in writes:
        df.to_csv(pack / name, index=False)
        print(f"wrote {pack / name}  n={len(df)}", flush=True)


def _load_tables(pack: Path) -> dict[str, pd.DataFrame]:
    return {
        "animal_frac_still": pd.read_csv(pack / "frac_still_animal.csv"),
        "kruskal_level": pd.read_csv(pack / "frac_still_kruskal.csv"),
        "trial_step_delta": pd.read_csv(pack / "frac_still_trial_step_delta.csv"),
        "kruskal_trial_step": pd.read_csv(pack / "frac_still_trial_step_kruskal.csv"),
        "session_step_delta": pd.read_csv(pack / "frac_still_session_step_delta.csv"),
        "kruskal_session_step": pd.read_csv(pack / "frac_still_session_step_kruskal.csv"),
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
    y_lim = _y_lim_from(med, "p")
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial"] == trial)]
            _draw_condition_sex_violins(
                ax, panel, dest=dest, rng=rng, xlabel=(i == len(TRIALS) - 1), ycol="p"
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial": trial}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\nfrac still")
    fig.suptitle(
        "frac_still (time immobile / trial duration) by condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), FOOT_LEVEL, dest=dest)
    save_pdf_svg(fig, out / "fig_frac_still_by_sex")


def fig_trial_step(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w, fig_h = FIGSIZE_SLIDES if dest == "slides" else (7.2, 8.0)
    fig = plt.figure(figsize=(fig_w * 1.08, fig_h + 0.8))
    gs = fig.add_gridspec(
        len(TRIAL_STEP_NAMES),
        len(SESSIONS),
        left=0.07,
        right=0.98,
        top=0.88,
        bottom=0.22,
        hspace=0.42,
        wspace=0.30,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "delta_p")
    violin_axes: list = []
    for i, step in enumerate(TRIAL_STEP_NAMES):
        for j, session in enumerate(SESSIONS):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["session"] == session) & (med["trial_step"] == step)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIAL_STEP_NAMES) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"session": session, "trial_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_SHORT[session], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_STEP_LAB[step]}\nΔ frac still")
    fig.suptitle(
        "Δ frac_still by trial-step × condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), FOOT_TRIAL_STEP, dest=dest)
    save_pdf_svg(fig, out / "fig_frac_still_trial_step_delta_by_sex")


def fig_session_step(med: pd.DataFrame, kr: pd.DataFrame, out: Path, *, dest: str) -> None:
    apply_style(dest=dest)
    ts = type_scale(dest)
    fig_w = 14.5 if dest == "slides" else 10.0
    fig_h = 7.8 if dest == "slides" else 6.5
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = fig.add_gridspec(
        len(TRIALS),
        len(SESSION_STEP_NAMES),
        left=0.06,
        right=0.99,
        top=0.88,
        bottom=0.22,
        hspace=0.45,
        wspace=0.28,
    )
    rng = np.random.default_rng(0)
    y_lim = _y_lim_from(med, "delta_p")
    violin_axes: list = []
    for i, trial in enumerate(TRIALS):
        for j, step in enumerate(SESSION_STEP_NAMES):
            ax = fig.add_subplot(gs[i, j], sharey=violin_axes[0] if violin_axes else None)
            violin_axes.append(ax)
            panel = med[(med["trial"] == trial) & (med["session_step"] == step)]
            _draw_condition_sex_violins(
                ax,
                panel,
                dest=dest,
                rng=rng,
                xlabel=(i == len(TRIALS) - 1),
                ycol="delta_p",
                zero_line=True,
            )
            ax.set_ylim(*y_lim)
            _annotate_fm(ax, kr, filters={"trial": trial, "session_step": step}, dest=dest)
            if i == 0:
                ax.set_title(SESSION_STEP_LAB[step], loc="left", fontweight="bold", color=INK)
            if j == 0:
                ax.set_ylabel(f"{TRIAL_LAB[trial]}\nΔ frac still")
    fig.suptitle(
        "Δ frac_still by session-step × condition × sex",
        fontsize=ts["suptitle"],
        fontweight="bold",
        color=INK,
    )
    fig_legend_and_footnote(fig, condition_sex_legend_handles(dest=dest), FOOT_SESSION_STEP, dest=dest)
    save_pdf_svg(fig, out / "fig_frac_still_session_step_delta_by_sex")


def write_info_md(pack: Path) -> None:
    text = f"""# INFO — slides pack: frac_still (time immobile / trial duration)

Consensus violin pack mirroring the HDBSCAN cluster frame-share layouts
(**level / phase-step Δ / stage-step Δ**), without per-model Kruskal heatmaps
or grid videos. Ambulation is one scalar clock.

| | |
| --- | --- |
| These files | `{pack.as_posix()}` |
| Dest | slides |
| How regenerated | `uv run python scratch/nor_object_mi/frac_still_slides_pack.py --rebuild` |

**IMPRESS** ambulation: `time_immobile_s` from fore displacement hysteresis.
**frac_still** = `time_immobile_s / duration_s`. **BH** = Benjamini–Hochberg.
**Kruskal** = Kruskal–Wallis.

## Questions

1. **Level:** Within sex, does **condition** change `frac_still` at each
   `session × trial`?
2. **Trial-step** (prose *phase-step*): Within sex, does condition modulate the
   paired Δ across trials inside a session?
3. **Session-step** (prose *stage-step*): Within sex, does condition modulate the
   paired Δ across sessions inside a trial?

## Grain

| Family | Point | Value |
| ------ | ----- | ----- |
| level | animal × session × trial | `p` = frac_still |
| trial_step | animal × session × trial_step | paired Δp |
| session_step | animal × trial × session_step | paired Δp |

No across-model IQR whiskers (`iqr_across_models` is NaN).

**Hit rule:** BH `q_bh < 0.05` within each family's cell grid (level &
trial_step: 24; session_step: 36).

**What this is not:** not cluster-13 (or any) kpMS frame share; not DR; not
Wilcoxon vs 0 as the panel claim.

## Protocol gloss

| Wire | Prose on figures |
| ---- | ---------------- |
| `session` | stage |
| `trial` | phase |
| `trial_step` | phase-step |
| `session_step` | stage-step |
| `condition` | treatment arm |

## Artifacts

| File | Unit |
| ---- | ---- |
| `frac_still_animal.csv` | animal × session × trial (`p` = frac_still) |
| `frac_still_kruskal.csv` | session × trial × sex |
| `frac_still_trial_step_delta.csv` | animal × session × trial_step |
| `frac_still_trial_step_kruskal.csv` | session × trial_step × sex |
| `frac_still_session_step_delta.csv` | animal × trial × session_step |
| `frac_still_session_step_kruskal.csv` | trial × session_step × sex |
| `figures/fig_frac_still_by_sex.{{pdf,svg}}` | six-violin level |
| `figures/fig_frac_still_trial_step_delta_by_sex.{{pdf,svg}}` | phase-step Δ |
| `figures/fig_frac_still_session_step_delta_by_sex.{{pdf,svg}}` | stage-step Δ |

## Source (rebuild only)

| Upstream | Use |
| -------- | --- |
| `thresholded-signal-bouts/impress_ambulation.csv` | `time_immobile_s`, `duration_s` |
"""
    (pack / "INFO_slides_pack.md").write_text(text, encoding="utf-8")


def write_figures_md(out: Path) -> None:
    text = """# Figures — frac_still (slides pack)

| Stem | Claim | Layout | D / I |
| ---- | ----- | ------ | ----- |
| `fig_frac_still_by_sex` | Level: condition × sex on frac_still | 3×4 trial × session; six violins | D + Kruskal on level |
| `fig_frac_still_trial_step_delta_by_sex` | Phase-step Δ modulated by condition? | 3×4 trial_step × session | D + Kruskal on Δ |
| `fig_frac_still_session_step_delta_by_sex` | Stage-step Δ modulated by condition? | 3×6 trial × session_step | D + Kruskal on Δ |

No per-model heatmaps (ambulation is not kpMS).
"""
    (out / "FIGURES.md").write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    ap.add_argument("--ambulation-csv", type=Path, default=DEFAULT_AMBULATION)
    ap.add_argument("--dest", choices=("slides", "paper"), default="slides")
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args(argv)

    pack: Path = args.pack
    out = pack / "figures"
    pack.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    animal_csv = pack / "frac_still_animal.csv"
    if args.rebuild or not animal_csv.is_file():
        print(f"building frac_still pack from {args.ambulation_csv} ...", flush=True)
        tables = build_frac_still_pack(args.ambulation_csv)
        _write_tables(pack, tables)
    else:
        print(f"loading existing pack CSVs from {pack}", flush=True)
        tables = _load_tables(pack)

    fig_level(tables["animal_frac_still"], tables["kruskal_level"], out, dest=args.dest)
    fig_trial_step(tables["trial_step_delta"], tables["kruskal_trial_step"], out, dest=args.dest)
    fig_session_step(tables["session_step_delta"], tables["kruskal_session_step"], out, dest=args.dest)
    write_info_md(pack)
    write_figures_md(out)
    print(f"done -> {pack}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
