"""INFO: shared information between object-prox DR and pause syllable Y.

Between-animal association (not within-bout stim↔syll MI). Grain: animal × phase
on ``novel_obj``; sex-stratified cells. Y is cluster-13 mapped id, median-merged
across kpMS models (see ``Y_METRICS``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from nor_object_mi._pub_style import PHASES, SEX_ORDER
from nor_object_mi.cluster13_tx_delta import (
    STEP_LAB,
    STEPS,
    animal_median_delta_p,
    filter_mapped_deltas,
)
from nor_object_mi.simpler_first_da import apply_bh
from nor_object_mi.simpler_first_object_prox import animal_median_across_models
from nor_object_mi.simpler_first_protocol_prologue import pearson_pair

LN2 = np.log(2.0)
DR_COL = "dr_exclusive"
DEFAULT_Y_METRIC = "delta_p_novelty"
Y_COL = "delta_p_pause"  # default joined-table column (delta_p_novelty)
DEFAULT_N_BINS = 3
DEFAULT_N_PERM = 9999
MIN_N_FOR_INFO = 5

DA_USECOLS = (
    "model",
    "animal_id",
    "sex",
    "tx",
    "step",
    "phase_layer",
    "raw_syllable_id",
    "delta_p",
    "p_left",
    "p_right",
)


@dataclass(frozen=True)
class YMetricSpec:
    token: str
    step: str
    value_col: str
    y_col: str
    binary: bool
    label: str
    question: str
    y_axis: str


Y_METRICS: dict[str, YMetricSpec] = {
    "delta_p_novelty": YMetricSpec(
        token="delta_p_novelty",
        step="identical->novel",
        value_col="delta_p",
        y_col="delta_p_pause",
        binary=False,
        label="pause novelty Δp",
        question="info_dr_vs_pause_novelty_delta_p",
        y_axis="pause novelty Δp",
    ),
    "delta_p_presence": YMetricSpec(
        token="delta_p_presence",
        step="no_obj->identical",
        value_col="delta_p",
        y_col="delta_p_presence",
        binary=False,
        label="pause presence-step Δp",
        question="info_dr_vs_pause_presence_delta_p",
        y_axis="pause presence-step Δp",
    ),
    "delta_p_span": YMetricSpec(
        token="delta_p_span",
        step="no_obj->novel",
        value_col="delta_p",
        y_col="delta_p_span",
        binary=False,
        label="pause span Δp",
        question="info_dr_vs_pause_span_delta_p",
        y_axis="pause span Δp",
    ),
    "p_novel": YMetricSpec(
        token="p_novel",
        step="identical->novel",
        value_col="p_right",
        y_col="p_novel",
        binary=False,
        label="pause p_k under novel_obj",
        question="info_dr_vs_pause_p_novel",
        y_axis="pause frame share (novel_obj)",
    ),
    "p_identical": YMetricSpec(
        token="p_identical",
        step="identical->novel",
        value_col="p_left",
        y_col="p_identical",
        binary=False,
        label="pause p_k under identical_obj",
        question="info_dr_vs_pause_p_identical",
        y_axis="pause frame share (identical_obj)",
    ),
    "presence_novel": YMetricSpec(
        token="presence_novel",
        step="identical->novel",
        value_col="p_right",
        y_col="presence_novel",
        binary=True,
        label="pause presence (novel_obj)",
        question="info_dr_vs_pause_presence_novel",
        y_axis="pause present on novel_obj (0/1)",
    ),
    "presence_identical": YMetricSpec(
        token="presence_identical",
        step="identical->novel",
        value_col="p_left",
        y_col="presence_identical",
        binary=True,
        label="pause presence (identical_obj)",
        question="info_dr_vs_pause_presence_identical",
        y_axis="pause present on identical_obj (0/1)",
    ),
}


def y_metric_choices() -> tuple[str, ...]:
    return tuple(Y_METRICS.keys())


def get_y_metric_spec(token: str) -> YMetricSpec:
    key = str(token).strip()
    if key not in Y_METRICS:
        raise ValueError(f"unknown y_metric {token!r}; choose from {y_metric_choices()}")
    return Y_METRICS[key]


def default_out_dir(ensemble_root: Path, y_metric: str) -> Path:
    base = ensemble_root / "_nor_object_mi"
    if y_metric == DEFAULT_Y_METRIC:
        return base / "simpler_first_info_dr_pause"
    return base / f"simpler_first_info_dr_pause__{y_metric}"


def _entropy_bits(counts: np.ndarray) -> float:
    n = float(counts.sum())
    if n <= 0:
        return 0.0
    p = counts[counts > 0] / n
    return float(-(p * np.log2(p)).sum())


def _mm_term_bits(occupied_bins: int, n: int) -> float:
    if n <= 0:
        return 0.0
    return (occupied_bins - 1) / (2.0 * n * LN2)


def _joint_counts(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    xs, x_idx = np.unique(x, return_inverse=True)
    ys, y_idx = np.unique(y, return_inverse=True)
    joint = np.zeros((xs.size, ys.size), dtype=np.int64)
    np.add.at(joint, (x_idx, y_idx), 1)
    return joint


def pair_mi_mm(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float, float, int]:
    """Plug-in I(X; Y) in bits with Miller–Madow bias correction."""
    x = np.asarray(x)
    y = np.asarray(y)
    if x.shape != y.shape:
        raise ValueError("x and y must have the same shape")
    ok = np.isfinite(x.astype(np.float64, copy=False)) & np.isfinite(y.astype(np.float64, copy=False))
    x = x[ok]
    y = y[ok]
    n = int(x.size)
    if n == 0:
        return float("nan"), float("nan"), float("nan"), float("nan"), 0

    joint = _joint_counts(x, y)
    cx = joint.sum(axis=1)
    cy = joint.sum(axis=0)
    hx = _entropy_bits(cx)
    hy = _entropy_bits(cy)
    hxy = _entropy_bits(joint.ravel())
    mi_raw = hx + hy - hxy

    kx = int((cx > 0).sum())
    ky = int((cy > 0).sum())
    kxy = int((joint > 0).sum())
    mm = _mm_term_bits(kx, n) + _mm_term_bits(ky, n) - _mm_term_bits(kxy, n)
    return float(mi_raw), float(mi_raw + mm), float(hx), float(hy), n


def fit_quantile_edges(values: np.ndarray, *, n_bins: int) -> np.ndarray:
    """Inclusive quantile edges for ``n_bins`` equal-count bins."""
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size < n_bins:
        raise ValueError(f"need at least {n_bins} finite values for {n_bins} bins")
    qs = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.quantile(v, qs)
    edges[0] = -np.inf
    edges[-1] = np.inf
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = np.nextafter(edges[i - 1], np.inf)
    return edges


def apply_quantile_edges(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Map values to integer bin labels 0 … n_bins−1; non-finite → NaN."""
    v = np.asarray(values, dtype=np.float64)
    out = np.full(v.shape, np.nan, dtype=np.float64)
    ok = np.isfinite(v)
    if not np.any(ok):
        return out
    inner = edges[1:-1]
    out[ok] = np.digitize(v[ok], inner, right=False)
    return out


def discretize_pair(
    x: np.ndarray,
    y: np.ndarray,
    *,
    n_bins: int,
    y_binary: bool = False,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Quantile-bin X; Y is binned or left as 0/1 when ``y_binary``."""
    xx = np.asarray(x, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(xx) & np.isfinite(yy)
    n = int(ok.sum())
    if n < MIN_N_FOR_INFO:
        return np.array([]), np.array([]), 0

    x_fin = xx[ok]
    y_fin = yy[ok]
    nb = int(min(n_bins, max(2, n // 2)))
    x_edges = fit_quantile_edges(x_fin, n_bins=nb)
    xb = apply_quantile_edges(xx, x_edges)

    if y_binary:
        yb = np.full(xx.shape, np.nan, dtype=np.float64)
        yb[ok] = (y_fin > 0.0).astype(np.float64)
    else:
        y_edges = fit_quantile_edges(y_fin, n_bins=nb)
        yb = apply_quantile_edges(yy, y_edges)

    ok2 = np.isfinite(xb) & np.isfinite(yb)
    return xb[ok2].astype(np.int64), yb[ok2].astype(np.int64), nb


def perm_p_value(
    x: np.ndarray,
    y: np.ndarray,
    *,
    observed_mm: float,
    n_perm: int,
    rng: np.random.Generator,
    n_bins: int,
    y_binary: bool = False,
) -> tuple[float, float]:
    """Permutation null on Y (shuffle raw y within cell)."""
    if not np.isfinite(observed_mm):
        return float("nan"), float("nan")
    xx = np.asarray(x, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(xx) & np.isfinite(yy)
    if int(ok.sum()) < MIN_N_FOR_INFO:
        return float("nan"), float("nan")

    x_obs, y_obs, nb = discretize_pair(xx, yy, n_bins=n_bins, y_binary=y_binary)
    if x_obs.size == 0:
        return float("nan"), float("nan")
    x_edges = fit_quantile_edges(xx[ok], n_bins=nb)
    x_fin = xx[ok]
    y_fin = yy[ok]

    null = np.empty(n_perm, dtype=np.float64)
    for i in range(n_perm):
        perm_y = rng.permutation(y_fin)
        xb = apply_quantile_edges(x_fin, x_edges)
        if y_binary:
            yb = (perm_y > 0.0).astype(np.float64)
        else:
            y_edges = fit_quantile_edges(y_fin, n_bins=nb)
            yb = apply_quantile_edges(perm_y, y_edges)
        okb = np.isfinite(xb) & np.isfinite(yb)
        _, mi_mm, _, _, _ = pair_mi_mm(xb[okb].astype(np.int64), yb[okb].astype(np.int64))
        null[i] = mi_mm
    null_mean = float(np.nanmean(null))
    p = float((np.sum(null >= observed_mm) + 1) / (n_perm + 1))
    return null_mean, p


def spearman_pair(x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    xx = np.asarray(x, dtype=np.float64)
    yy = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(xx) & np.isfinite(yy)
    n = int(ok.sum())
    if n < 3:
        return {"n": float(n), "spearman_rho": float("nan"), "p": float("nan")}
    if np.unique(yy[ok]).size < 2 or np.unique(xx[ok]).size < 2:
        return {"n": float(n), "spearman_rho": float("nan"), "p": float("nan")}
    rho, p = stats.spearmanr(xx[ok], yy[ok])
    return {"n": float(n), "spearman_rho": float(rho), "p": float(p)}


def animal_median_metric(mapped: pd.DataFrame, *, value_col: str, out_col: str) -> pd.DataFrame:
    """One row per animal × phase × step: median metric across models (+ IQR salt)."""
    keys = ["animal_id", "sex", "tx", "phase_layer", "step"]
    rows: list[dict[str, object]] = []
    for key_vals, g in mapped.groupby(keys, sort=True):
        key_map = dict(zip(keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        v = pd.to_numeric(g[value_col], errors="coerce").to_numpy(dtype=np.float64)
        v = v[np.isfinite(v)]
        q75, q25 = (np.percentile(v, [75.0, 25.0]) if v.size >= 2 else (float("nan"), float("nan")))
        rows.append(
            {
                **key_map,
                out_col: float(np.median(v)) if v.size else float("nan"),
                "iqr_across_models": float(q75 - q25) if v.size >= 2 else float("nan"),
                "n_models": int(g["model"].nunique()),
                "n_finite": int(v.size),
            }
        )
    return pd.DataFrame(rows)


def info_cell(
    g: pd.DataFrame,
    *,
    y_col: str,
    y_binary: bool,
    n_bins: int,
    n_perm: int,
    rng: np.random.Generator,
) -> dict[str, object]:
    """One sex × phase INFO cell."""
    dr = g[DR_COL].to_numpy(dtype=np.float64)
    yv = g[y_col].to_numpy(dtype=np.float64)
    xb, yb, nb = discretize_pair(dr, yv, n_bins=n_bins, y_binary=y_binary)
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
            y_binary=y_binary,
        )
    sp = spearman_pair(dr, yv)
    y_fin = yv[np.isfinite(yv)]
    dr_fin = dr[np.isfinite(dr)]
    if y_fin.size >= 3 and np.unique(y_fin).size >= 2 and np.unique(dr_fin).size >= 2:
        pr = pearson_pair(dr, yv)
    else:
        pr = {"pearson_r": float("nan"), "p": float("nan")}
    frac_pos = float(np.mean(y_fin > 0.0)) if y_fin.size else float("nan")
    y_degenerate = y_binary and bool(np.isfinite(frac_pos) and (frac_pos <= 0.0 or frac_pos >= 1.0))
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
        "frac_y_positive": frac_pos,
        "y_degenerate": y_degenerate,
    }


def load_dr_median(object_prox_dir: Path) -> pd.DataFrame:
    path = object_prox_dir / "object_prox_metrics_per_animal.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    animals = pd.read_csv(path)
    return animal_median_across_models(animals)


def load_pause_y(da_dir: Path, spec: YMetricSpec) -> pd.DataFrame:
    id_path = da_dir / "duration_band_vs_da.csv"
    delta_path = da_dir / "da_syllable_deltas_per_animal.csv"
    if not id_path.exists():
        raise FileNotFoundError(id_path)
    if not delta_path.exists():
        raise FileNotFoundError(delta_path)
    ids = pd.read_csv(id_path, usecols=["model", "raw_syllable_id"])
    deltas = pd.read_csv(delta_path, usecols=list(DA_USECOLS))
    mapped = filter_mapped_deltas(deltas, ids)
    mapped = mapped[mapped["step"] == spec.step].copy()
    if spec.value_col == "delta_p":
        med = animal_median_delta_p(mapped)
        med = med.rename(columns={"delta_p": spec.y_col})
    else:
        med = animal_median_metric(mapped, value_col=spec.value_col, out_col=spec.y_col)
    if spec.binary:
        med[spec.y_col] = (pd.to_numeric(med[spec.y_col], errors="coerce") > 0.0).astype(np.float64)
    return med


def load_pause_novelty_delta(da_dir: Path) -> pd.DataFrame:
    """Backward-compatible helper."""
    return load_pause_y(da_dir, get_y_metric_spec(DEFAULT_Y_METRIC))


def join_dr_pause(
    dr: pd.DataFrame,
    pause: pd.DataFrame,
    *,
    y_col: str,
) -> pd.DataFrame:
    """Inner join on animal × phase; keep tx from DR table."""
    keys = ["animal_id", "sex", "phase_layer"]
    left = dr[keys + ["tx", DR_COL, "n_models"]].rename(columns={"n_models": "n_models_dr"})
    right_cols = [c for c in [y_col, "n_models", "iqr_across_models", "step"] if c in pause.columns]
    right = pause[keys + ["tx", *right_cols]].rename(
        columns={"n_models": "n_models_da", "iqr_across_models": "iqr_y_across_models"}
    )
    out = left.merge(right, on=keys + ["tx"], how="inner", suffixes=("", "_y"))
    if out.empty:
        return out
    out["animal_id"] = out["animal_id"].astype(str)
    return out.sort_values(keys + ["tx"]).reset_index(drop=True)


def run_info_lattice(
    joined: pd.DataFrame,
    spec: YMetricSpec,
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
            rec = info_cell(
                g,
                y_col=spec.y_col,
                y_binary=spec.binary,
                n_bins=n_bins,
                n_perm=n_perm,
                rng=rng,
            )
            rows.append(
                {
                    "phase_layer": phase,
                    "sex": sex,
                    "step": spec.step,
                    "step_label": STEP_LAB.get(spec.step, spec.step),
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


def info_md(spec: YMetricSpec, *, n_bins: int, n_perm: int) -> str:
    y_rule = (
        f"`{spec.y_col}` = 1{{median {spec.value_col} > 0}} on step `{spec.step}`"
        if spec.binary
        else f"`{spec.y_col}` = median `{spec.value_col}` on step `{spec.step}`"
    )
    return f"""# INFO — object-prox DR vs {spec.label}

## Question

Within sex × phase on `novel_obj`, how many **bits** does knowing **{spec.label}**
reduce uncertainty about **object-prox discrimination ratio (DR)**?

Operation family: **INFO** (shared information). Not DA, not DIFFERENCE.

## Knobs

| Knob | Value |
|------|--------|
| `--y-metric` | `{spec.token}` |
| X | `dr_exclusive` — per-object 0.10 m prox windows; median across 21 kpMS models |
| Y | {y_rule} |
| Grain | animal × phase; one scalar each |
| Sex | stratified (F / M cells) |
| Phases | BL / TX / REC3hr / REC11hr |
| MI estimate | quantile bins on DR (`n_bins={n_bins}`); Y {"held 0/1" if spec.binary else "quantile-binned"} + Miller–Madow |
| Null (I) | permute Y within cell (`n_perm={n_perm}`); BH FDR family = 8 cells |
| Rank cousin | `spearman_rho` |
| Mean cousin | `pearson_r` |

## All `--y-metric` choices

{", ".join(f"`{k}`" for k in y_metric_choices())}

## Inputs

| File | Role |
|------|------|
| `object_prox_metrics_per_animal.csv` | per-model DR → median across models |
| `duration_band_vs_da.csv` | cluster-13 mapped id per model |
| `da_syllable_deltas_per_animal.csv` | per-model Y → median (then binarize if presence) |

## Outputs

| File | Content |
|------|---------|
| `info_dr_pause_joined_per_animal.csv` | joined animal table |
| `info_dr_pause_tests_long.csv` | sex × phase INFO + association cousins |
| `run_summary.json` | run metadata |
"""


def write_run(
    *,
    object_prox_dir: Path,
    da_dir: Path,
    out_dir: Path,
    y_metric: str = DEFAULT_Y_METRIC,
    n_bins: int = DEFAULT_N_BINS,
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 0,
) -> dict[str, object]:
    spec = get_y_metric_spec(y_metric)
    out_dir.mkdir(parents=True, exist_ok=True)
    dr = load_dr_median(object_prox_dir)
    pause = load_pause_y(da_dir, spec)
    joined = join_dr_pause(dr, pause, y_col=spec.y_col)
    joined.to_csv(out_dir / "info_dr_pause_joined_per_animal.csv", index=False)
    tests = run_info_lattice(joined, spec, n_bins=n_bins, n_perm=n_perm, seed=seed)
    tests.to_csv(out_dir / "info_dr_pause_tests_long.csv", index=False)
    (out_dir / "INFO_info_dr_pause.md").write_text(
        info_md(spec, n_bins=n_bins, n_perm=n_perm),
        encoding="utf-8",
    )
    summary = {
        "object_prox_dir": str(object_prox_dir),
        "da_dir": str(da_dir),
        "out_dir": str(out_dir),
        "y_metric": spec.token,
        "y_col": spec.y_col,
        "y_binary": spec.binary,
        "step": spec.step,
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
