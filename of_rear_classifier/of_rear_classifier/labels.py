"""Interval labels → per-frame class strings (Sturman AllLabDataOFT style)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CLASS_NAMES = ("None", "Supported", "Unsupported", "Grooming")
DEFAULT_CLASS = "None"


def intervals_to_frame_labels(
    intervals: pd.DataFrame,
    *,
    n_frames: int,
    fps: float,
    type_col: str = "type",
    from_col: str = "from",
    to_col: str = "to",
    keep_types: tuple[str, ...] = ("Supported", "Unsupported", "Grooming"),
) -> np.ndarray:
    """Paint interval ``[from, to]`` (seconds) onto frame labels; gaps stay ``None``."""
    y = np.full(n_frames, DEFAULT_CLASS, dtype=object)
    if intervals.empty:
        return y
    keep = set(keep_types)
    for _, row in intervals.iterrows():
        typ = str(row[type_col])
        if typ not in keep:
            continue
        f0 = int(float(row[from_col]) * fps)
        f1 = int(float(row[to_col]) * fps)
        f0 = max(0, f0)
        f1 = min(n_frames - 1, f1)
        if f1 >= f0:
            y[f0 : f1 + 1] = typ
    return y


def load_sturman_oft_labels(csv_path: Path | str) -> pd.DataFrame:
    """Load DLCAnalyzer ``AllLabDataOFT_final.csv`` (semicolon-separated)."""
    path = Path(csv_path)
    return pd.read_csv(path, sep=";")
