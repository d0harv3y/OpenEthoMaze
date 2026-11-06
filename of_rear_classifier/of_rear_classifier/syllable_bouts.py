"""Syllable bout tables for labeling (frame intervals + syllable id)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BOUT_COLUMNS = (
    "bout_index",
    "syllable_id",
    "t0_frame",
    "t1_frame",
    "n_frames",
    "label",
)


def bouts_from_syllable_sequence(
    syllables: np.ndarray,
    *,
    source_frame_indices: np.ndarray | None = None,
) -> pd.DataFrame:
    """Collapse a framewise syllable id stream into contiguous bouts.

    If ``source_frame_indices`` is given (kpMS filtered timeline), map bout edges
    back to those video frame indices; else assume ``syllables[i]`` is video frame i.
    """
    s = np.asarray(syllables).reshape(-1)
    if s.size == 0:
        return pd.DataFrame(columns=list(BOUT_COLUMNS))
    if source_frame_indices is None:
        src = np.arange(s.size, dtype=np.int64)
    else:
        src = np.asarray(source_frame_indices, dtype=np.int64).reshape(-1)
        if src.size != s.size:
            raise ValueError("source_frame_indices length must match syllables")

    change = np.flatnonzero(s[1:] != s[:-1]) + 1
    starts = np.concatenate([[0], change])
    ends = np.concatenate([change - 1, [s.size - 1]])
    rows = []
    for i, (a, b) in enumerate(zip(starts, ends, strict=True)):
        rows.append(
            {
                "bout_index": i,
                "syllable_id": int(s[a]),
                "t0_frame": int(src[a]),
                "t1_frame": int(src[b]),
                "n_frames": int(b - a + 1),
                "label": "",
            }
        )
    return pd.DataFrame(rows, columns=list(BOUT_COLUMNS))


def load_bout_table(path: Path | str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in ("bout_index", "syllable_id", "t0_frame", "t1_frame") if c not in df.columns]
    if missing:
        raise KeyError(f"{path}: missing columns {missing}")
    if "label" not in df.columns:
        df["label"] = ""
    if "n_frames" not in df.columns:
        df["n_frames"] = df["t1_frame"].astype(int) - df["t0_frame"].astype(int) + 1
    return df


def save_bout_table(df: pd.DataFrame, path: Path | str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def bouts_to_sturman_intervals(df: pd.DataFrame, *, fps: float, video_id: str) -> pd.DataFrame:
    """Labeled bouts → Sturman-like interval CSV (seconds)."""
    lab = df[df["label"].astype(str).str.len() > 0].copy()
    out = pd.DataFrame(
        {
            "Experimenter": "human",
            "from": lab["t0_frame"].astype(float) / float(fps),
            "to": (lab["t1_frame"].astype(float) + 1.0) / float(fps),
            "type": lab["label"].astype(str),
            "ID": video_id,
            "syllable_id": lab["syllable_id"],
            "bout_index": lab["bout_index"],
        }
    )
    return out
