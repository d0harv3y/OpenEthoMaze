"""Load Sturman→Davis MLP prediction CSVs into dense frame arrays for the labeler."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Fallback only when callers omit pred_dir (labeler passes sibling base_transfer_pred).
_DEFAULT_PRED_DIR = Path(r"D:\Open Field Frailty\base_transfer_pred")

CLASS_NAMES = ("None", "Supported", "Unsupported", "Grooming")


def _clean_label_series(s: pd.Series) -> np.ndarray:
    """Pandas often reads class name ``None`` as NaN."""
    out = s.astype("string").fillna("None").astype(str).to_numpy()
    return np.where(np.isin(out, ("nan", "NaN", "<NA>", "<na>")), "None", out)


def discover_mlp_pred(
    video_id: str,
    *,
    pred_dir: Path | str | None = None,
    preferred: tuple[str, ...] = ("majority", "Furkan", "Jin", "Oliver"),
) -> Path | None:
    """Find ``pred_<video>_<tag>.csv`` (spaces OK in video id).

    Default preference: HITL **majority** vote, then Furkan (best solo transfer).
    """
    root = Path(pred_dir) if pred_dir else _DEFAULT_PRED_DIR
    if not root.is_dir():
        return None
    for exp in preferred:
        cand = root / f"pred_{video_id}_{exp}.csv"
        if cand.is_file():
            return cand
    # any match for this video (skip partial y_* side columns files — none)
    hits = sorted(root.glob(f"pred_{video_id}_*.csv"))
    return hits[0] if hits else None


def experimenter_from_pred_path(path: Path | str) -> str:
    name = Path(path).stem  # pred_Test 42_Furkan
    m = re.match(r"pred_(.+)_([^_]+)$", name)
    if m:
        return m.group(2)
    return Path(path).stem


def load_mlp_pred_csv(
    path: Path | str,
    *,
    n_frames: int,
) -> dict:
    """Return dense framewise MLP outputs.

    Keys
    ----
    labels : (T,) str — class name; edges outside CSV span stay ``None``
    scores : dict[str, (T,)] float | None — ``p_<Class>`` if columns present
    frames_in_csv : int
    experimenter : str
    path : Path
    """
    path = Path(path)
    df = pd.read_csv(path)
    if "frame" not in df.columns or "y_pred" not in df.columns:
        raise KeyError(f"{path}: need columns frame, y_pred")
    frames = df["frame"].to_numpy(dtype=np.int64)
    y_pred = _clean_label_series(df["y_pred"])
    labels = np.full(int(n_frames), "None", dtype=object)
    for f, lab in zip(frames, y_pred, strict=True):
        if 0 <= int(f) < n_frames:
            labels[int(f)] = lab

    scores: dict[str, np.ndarray] | None = None
    score_cols = [c for c in df.columns if c.startswith("p_")]
    if score_cols:
        scores = {}
        for c in score_cols:
            name = c[2:]  # p_Supported → Supported
            arr = np.full(int(n_frames), np.nan, dtype=np.float64)
            vals = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=np.float64)
            for f, v in zip(frames, vals, strict=True):
                if 0 <= int(f) < n_frames:
                    arr[int(f)] = v
            scores[name] = arr

    return {
        "labels": labels,
        "scores": scores,
        "frames_in_csv": int(len(frames)),
        "experimenter": experimenter_from_pred_path(path),
        "path": path,
    }


def mlp_strip_rgb(labels: np.ndarray, *, label_rgb: dict[str, tuple[int, int, int]]) -> np.ndarray:
    """``(1, T, 3)`` uint8 strip from dense class labels."""
    t = len(labels)
    strip = np.full((1, t, 3), 16, dtype=np.uint8)
    for i, lab in enumerate(labels):
        rgb = label_rgb.get(str(lab), (148, 103, 189))
        strip[0, i] = rgb
    return strip
