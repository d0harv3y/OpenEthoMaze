"""INFO: object-prox DR vs pause bout MI (mi_mm_nvl).

Between-animal association at animal × phase grain — same lattice as
``info_dr_pause_delta`` (quantile-bin Miller–Madow MI, Y permutation null,
Spearman / Pearson cousins, BH across 8 sex×phase cells).

Y = within-animal bout occupancy MI I(pause_binary; stim_bin) on the **novel-side**
distance stream (``dist_nvl``), from a single kpMS model run (default pilot).
X = ``dr_exclusive`` median across 21 kpMS models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from nor_object_mi._pub_style import PHASES, SEX_ORDER
from nor_object_mi.info_dr_pause_delta import (
    DR_COL,
    DEFAULT_N_BINS,
    DEFAULT_N_PERM,
    discretize_pair,
    load_dr_median,
    pair_mi_mm,
    perm_p_value,
    spearman_pair,
)
from nor_object_mi.pause_stim_mi import DEFAULT_MODEL
from nor_object_mi.simpler_first_da import apply_bh
from nor_object_mi.simpler_first_protocol_prologue import pearson_pair

PAUSE_MI_COL = "mi_mm_nvl"
QUESTION = "info_dr_vs_pause_mi_mm_nvl"


@dataclass(frozen=True)
class BoutMiSpec:
    token: str = PAUSE_MI_COL
    y_col: str = PAUSE_MI_COL
    binary: bool = False
    label: str = "pause bout MI (dist_nvl)"
    y_axis: str = "I(pause; binned prox) mm (bits)"
    y_desc: str = "bout I(pause; 5-quantile prox bin) on dist_nvl; single kpMS model"
    question: str = QUESTION
    step: str = "bout_occupancy_nvl"
    step_label: str = "bout occupancy (dist_nvl)"


SPEC = BoutMiSpec()


def default_out_dir(ensemble_root: Path) -> Path:
    return ensemble_root / "_nor_object_mi" / "simpler_first_info_dr_pause_mi_mm_nvl"


def default_pause_mi_dir(art_root: Path, model: str = DEFAULT_MODEL) -> Path:
    return art_root / f"simpler_first_pause_stim_mi__{model}"


def load_pause_mi_nvl(pause_mi_dir: Path, *, y_col: str = PAUSE_MI_COL) -> pd.DataFrame:
    path = pause_mi_dir / "pause_stim_delta_excess.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    sub = df[df["mi_label"] == "pause_binary"].copy()
    if sub.empty:
        raise ValueError(f"no pause_binary rows in {path}")
    if y_col not in sub.columns:
        raise ValueError(f"{y_col} not in pause_stim_delta_excess columns")
    keys = ["animal_id", "sex", "tx", "phase_layer"]
    extra = [c for c in ("mi_mm_fam", "excess_nvl", "delta_excess", "frac_pause_bouts") if c in sub.columns]
    out = sub[keys + [y_col, *extra]].copy()
    out["animal_id"] = out["animal_id"].astype(str)
    out = out.rename(columns={y_col: y_col})  # explicit
    out["n_models"] = 1
    return out.sort_values(keys).reset_index(drop=True)


def join_dr_pause_mi(
    dr: pd.DataFrame,
    pause_mi: pd.DataFrame,
    *,
    y_col: str = PAUSE_MI_COL,
) -> pd.DataFrame:
    keys = ["animal_id", "sex", "phase_layer"]
    left = dr[keys + ["tx", DR_COL, "n_models"]].rename(columns={"n_models": "n_models_dr"}).copy()
    right_cols = [
        c
        for c in [y_col, "n_models", "mi_mm_fam", "excess_nvl", "delta_excess", "frac_pause_bouts"]
        if c in pause_mi.columns
    ]
    right = pause_mi[keys + ["tx", *right_cols]].rename(columns={"n_models": "n_models_pause_mi"}).copy()
    left["animal_id"] = left["animal_id"].astype(str)
    right["animal_id"] = right["animal_id"].astype(str)
    out = left.merge(right, on=keys + ["tx"], how="inner")
    if out.empty:
        return out
    out["animal_id"] = out["animal_id"].astype(str)
    return out.sort_values(keys + ["tx"]).reset_index(drop=True)


def info_cell(
    g: pd.DataFrame,
    *,
    y_col: str,
    n_bins: int,
    n_perm: int,
    rng: np.random.Generator,
) -> dict[str, object]:
    """One sex × phase INFO cell: X = DR, Y = pause bout MI."""
    dr = g[DR_COL].to_numpy(dtype=np.float64)
    yv = g[y_col].to_numpy(dtype=np.float64)
    xb, yb, nb = discretize_pair(dr, yv, n_bins=n_bins, y_binary=False)
    if xb.size == 0:
        mi_raw = mi_mm = h_dr = h_y = float("nan")
        null_mean = perm_p = float("nan")
    else:
        mi_raw, mi_mm, h_dr, h_y, _n = pair_mi_mm(xb, yb)
        null_mean, perm_p = perm_p_value(
            dr,
            yv,
            observed_mm=mi_mm,
            n_perm=n_perm,
            rng=rng,
            n_bins=n_bins,
            y_binary=False,
        )
    sp = spearman_pair(dr, yv)
    dr_fin = dr[np.isfinite(dr)]
    y_fin = yv[np.isfinite(yv)]
    if y_fin.size >= 3 and np.unique(y_fin).size >= 2 and np.unique(dr_fin).size >= 2:
        pr = pearson_pair(dr, yv)
    else:
        pr = {"pearson_r": float("nan"), "p": float("nan")}
    return {
        "n": int(len(g)),
        "n_finite": int((np.isfinite(dr) & np.isfinite(yv)).sum()) if len(g) else 0,
        "n_bins": int(nb) if xb.size else 0,
        "h_dr_bits": h_dr,
        "h_y_bits": h_y,
        "mi_raw_bits": mi_raw,
        "mi_mm_bits": mi_mm,
        "null_perm_mean_bits": null_mean,
        "perm_p": perm_p,
        "hit_p05": bool(np.isfinite(perm_p) and perm_p < 0.05),
        "spearman_rho": sp["spearman_rho"],
        "spearman_p": sp["p"],
        "pearson_r": pr["pearson_r"],
        "pearson_p": pr["p"],
        "median_dr": float(np.nanmedian(dr)) if len(g) else float("nan"),
        "median_y": float(np.nanmedian(yv)) if len(g) else float("nan"),
        "frac_y_positive": float("nan"),
        "y_degenerate": False,
    }


def run_info_lattice(
    joined: pd.DataFrame,
    spec: BoutMiSpec = SPEC,
    *,
    n_bins: int = DEFAULT_N_BINS,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 0,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for phase in PHASES:
        for sex in SEX_ORDER:
            g = joined[(joined["phase_layer"] == phase) & (joined["sex"] == sex)]
            rec = info_cell(g, y_col=spec.y_col, n_bins=n_bins, n_perm=n_perm, rng=rng)
            rows.append(
                {
                    "phase_layer": phase,
                    "sex": sex,
                    "step": spec.step,
                    "step_label": spec.step_label,
                    "y_metric": spec.token,
                    "y_col": spec.y_col,
                    "x_metric": DR_COL,
                    "question": spec.question,
                    "grain": "animal × phase × novel_obj; sex-stratified",
                    "design": "between_animal_association",
                    "y_binary": spec.binary,
                    **rec,
                }
            )
    tests = pd.DataFrame(rows)
    return apply_bh(tests, p_col="perm_p", q_col="q_bh_perm")


def info_md(
    spec: BoutMiSpec,
    *,
    model: str,
    n_bins: int,
    n_perm: int,
) -> str:
    return f"""# INFO — object-prox DR vs {spec.label}

## Question

Within sex × phase on `novel_obj`, how many **bits** does knowing **pause bout MI on
the novel-side distance stream** reduce uncertainty about **object-prox DR**?

Operation family: **INFO** (shared information). Not within-bout stim↔syll MI replay;
not DA.

## Knobs

| Knob | Value |
|------|--------|
| X | `dr_exclusive` — per-object 0.10 m prox windows; **median across 21 kpMS models** |
| Y | `{spec.y_col}` — I(pause_binary; 5-quantile binned spot→object dist) on `dist_nvl`; **single model** `{model}` |
| Grain | animal × phase; one scalar each |
| Sex | stratified (F / M cells) |
| Phases | BL / TX / REC3hr / REC11hr |
| MI estimate | quantile bins on DR (`n_bins={n_bins}`); Y quantile-binned + Miller–Madow |
| Null (I) | permute Y within cell (`n_perm={n_perm}`); BH FDR family = 8 cells |
| Rank cousin | `spearman_rho` |
| Mean cousin | `pearson_r` |

## Inputs

| File | Role |
|------|------|
| `object_prox_metrics_per_animal.csv` | per-model DR → median across models |
| `pause_stim_delta_excess.csv` | bout MI scalars from pause_stim_mi run |

## Outputs

| File | Content |
|------|---------|
| `info_dr_pause_mi_joined_per_animal.csv` | joined animal table |
| `info_dr_pause_mi_tests_long.csv` | sex × phase INFO + association cousins |
| `run_summary.json` | run metadata |
"""


def write_run(
    *,
    object_prox_dir: Path,
    pause_mi_dir: Path,
    out_dir: Path,
    model: str = DEFAULT_MODEL,
    n_bins: int = DEFAULT_N_BINS,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 0,
) -> dict[str, object]:
    spec = SPEC
    out_dir.mkdir(parents=True, exist_ok=True)
    dr = load_dr_median(object_prox_dir)
    pause_mi = load_pause_mi_nvl(pause_mi_dir, y_col=spec.y_col)
    joined = join_dr_pause_mi(dr, pause_mi, y_col=spec.y_col)
    joined.to_csv(out_dir / "info_dr_pause_mi_joined_per_animal.csv", index=False)
    tests = run_info_lattice(joined, spec, n_bins=n_bins, n_perm=n_perm, seed=seed)
    tests.to_csv(out_dir / "info_dr_pause_mi_tests_long.csv", index=False)
    (out_dir / "INFO_info_dr_pause_mi.md").write_text(
        info_md(spec, model=model, n_bins=n_bins, n_perm=n_perm),
        encoding="utf-8",
    )
    summary = {
        "object_prox_dir": str(object_prox_dir),
        "pause_mi_dir": str(pause_mi_dir),
        "out_dir": str(out_dir),
        "kpms_model_pause_mi": model,
        "y_metric": spec.token,
        "y_col": spec.y_col,
        "n_joined_rows": int(len(joined)),
        "n_cells": int(len(tests)),
        "n_perm": int(n_perm),
        "n_bins": int(n_bins),
        "n_hit_perm_p05": int(tests["hit_p05"].sum()) if "hit_p05" in tests.columns else 0,
        "n_hit_fdr_perm": int(tests["hit_fdr05"].sum()) if "hit_fdr05" in tests.columns else 0,
        "x_metric": DR_COL,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
