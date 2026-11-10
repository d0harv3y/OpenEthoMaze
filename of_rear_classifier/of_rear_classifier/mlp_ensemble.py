"""Majority-vote ensemble over per-rater Sturman MLP prediction CSVs (HITL strip)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from of_rear_classifier.labels import CLASS_NAMES
from of_rear_classifier.mlp_pred_io import _clean_label_series
from of_rear_classifier.sturman_loocv import EXPERIMENTERS

ENSEMBLE_NAME = "majority"
# Prefer this rater when hard-vote ties (matches best Davis transfer so far).
TIE_BREAK_RATER = "Furkan"


def majority_vote_labels(
    rater_labels: dict[str, np.ndarray],
    *,
    tie_break_rater: str = TIE_BREAK_RATER,
) -> tuple[np.ndarray, np.ndarray]:
    """Framewise hard majority.

    Returns ``(y_pred, vote_frac)`` where ``vote_frac`` is the winning class's
    share of raters (1.0 = unanimous). Ties → ``tie_break_rater`` if present,
    else first name in sorted raters among the tied classes.
    """
    if not rater_labels:
        raise ValueError("need ≥1 rater label array")
    names = list(rater_labels.keys())
    n = len(next(iter(rater_labels.values())))
    for name, arr in rater_labels.items():
        if len(arr) != n:
            raise ValueError(f"{name}: length {len(arr)} != {n}")

    y_out = np.full(n, "None", dtype=object)
    frac = np.zeros(n, dtype=np.float64)
    for i in range(n):
        votes = [str(rater_labels[r][i]) for r in names]
        counts = Counter(votes)
        top = counts.most_common()
        best_n = top[0][1]
        tied = [lab for lab, c in top if c == best_n]
        if len(tied) == 1:
            win = tied[0]
        elif tie_break_rater in rater_labels and str(rater_labels[tie_break_rater][i]) in tied:
            win = str(rater_labels[tie_break_rater][i])
        else:
            # stable: prefer CLASS_NAMES order among tied
            win = next((c for c in CLASS_NAMES if c in tied), tied[0])
        y_out[i] = win
        frac[i] = best_n / len(names)
    return y_out, frac


def mean_proba(
    rater_probas: dict[str, dict[str, np.ndarray]],
    *,
    class_names: tuple[str, ...] = CLASS_NAMES,
) -> dict[str, np.ndarray] | None:
    """Mean ``p_<class>`` across raters when every rater has all classes."""
    if not rater_probas:
        return None
    for probs in rater_probas.values():
        if any(c not in probs for c in class_names):
            return None
    n = len(next(iter(next(iter(rater_probas.values())).values())))
    out: dict[str, np.ndarray] = {}
    for c in class_names:
        stacked = np.stack([rater_probas[r][c] for r in rater_probas], axis=0)
        out[c] = np.nanmean(stacked, axis=0)
        if out[c].shape[0] != n:
            raise ValueError(f"proba length mismatch for {c}")
    return out


def build_majority_pred_csv(
    pred_paths: dict[str, Path],
    *,
    out_path: Path,
    tie_break_rater: str = TIE_BREAK_RATER,
) -> Path:
    """Read per-rater ``pred_*.csv``, write ``pred_<video>_majority.csv``."""
    frames_ref: np.ndarray | None = None
    y_true_ref: np.ndarray | None = None
    covered_ref: np.ndarray | None = None
    rater_y: dict[str, np.ndarray] = {}
    rater_p: dict[str, dict[str, np.ndarray]] = {}

    for rater, path in pred_paths.items():
        df = pd.read_csv(path)
        if "frame" not in df.columns or "y_pred" not in df.columns:
            raise KeyError(f"{path}: need frame, y_pred")
        frames = df["frame"].to_numpy(dtype=np.int64)
        if frames_ref is None:
            frames_ref = frames
            if "y_true" in df.columns:
                y_true_ref = _clean_label_series(df["y_true"])
            if "covered" in df.columns:
                covered_ref = pd.to_numeric(df["covered"], errors="coerce").fillna(0).to_numpy(dtype=np.int64)
        elif not np.array_equal(frames, frames_ref):
            raise ValueError(f"{path}: frame index mismatch vs {next(iter(pred_paths.values()))}")
        rater_y[rater] = _clean_label_series(df["y_pred"])
        score_cols = [c for c in df.columns if c.startswith("p_")]
        if score_cols:
            rater_p[rater] = {
                c[2:]: pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=np.float64) for c in score_cols
            }

    assert frames_ref is not None
    y_maj, vote_frac = majority_vote_labels(rater_y, tie_break_rater=tie_break_rater)
    out: dict = {
        "frame": frames_ref,
        "y_pred": np.asarray(y_maj, dtype=str),
        "vote_frac": vote_frac,
        "n_raters": np.full(len(frames_ref), len(rater_y), dtype=np.int64),
    }
    if y_true_ref is not None:
        out["y_true"] = y_true_ref
    if covered_ref is not None:
        out["covered"] = covered_ref
    for rater, labs in rater_y.items():
        out[f"y_{rater}"] = np.asarray(labs, dtype=str)

    mean_p = mean_proba(rater_p) if len(rater_p) == len(rater_y) else None
    if mean_p is not None:
        for name, arr in mean_p.items():
            out[f"p_{name}"] = arr

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(out).to_csv(out_path, index=False, quoting=1)
    return out_path


def majority_paths_for_video(
    out_dir: Path | str,
    video_id: str,
    *,
    experimenters: tuple[str, ...] = EXPERIMENTERS,
) -> dict[str, Path] | None:
    """Return per-rater pred paths if all exist; else ``None``."""
    root = Path(out_dir)
    paths = {exp: root / f"pred_{video_id}_{exp}.csv" for exp in experimenters}
    if all(p.is_file() for p in paths.values()):
        return paths
    return None
