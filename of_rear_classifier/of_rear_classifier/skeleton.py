"""22-D OFT skeleton features (Sturman ``create_skeleton_v1`` / SA-TVM names)."""

from __future__ import annotations

from typing import Mapping

import numpy as np

from of_rear_classifier.parts_map import SA_TVM_PARTS

FEATURE_NAMES: tuple[str, ...] = (
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "S6",
    "S7",
    "S8",
    "S9",
    "S10",
    "A1",
    "A2",
    "A3",
    "A4",
    "A5",
    "A6",
    "Ar1",
    "Ar2",
    "Ar3",
    "Ar4",
    "P1",
    "P2",
)
N_FEATURES = len(FEATURE_NAMES)
assert N_FEATURES == 22

# Indices of continuous cols that get per-video z-score (leave P1/P2 raw)
_ZSCORE_SLICE = slice(0, 20)


def _xy(parts: Mapping[str, np.ndarray], name: str) -> np.ndarray:
    arr = np.asarray(parts[name], dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError(f"{name}: expected (T, 2), got {arr.shape}")
    return arr


def segment_lengths(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.linalg.norm(a - b, axis=1)


def angle_between_segments(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray) -> np.ndarray:
    """Unsigned angle (radians) between vectors ``p1-p2`` and ``p3-p4`` (Sturman ``angle_features``)."""
    a = p1 - p2
    b = p3 - p4
    na = np.linalg.norm(a, axis=1)
    nb = np.linalg.norm(b, axis=1)
    denom = na * nb
    dot = np.sum(a * b, axis=1)
    cos = np.divide(dot, denom, out=np.zeros_like(dot), where=denom > 0)
    cos = np.clip(cos, -1.0, 1.0)
    return np.arccos(cos)


def polygon_areas(points: list[np.ndarray]) -> np.ndarray:
    """Shoelace absolute area/2 for a list of (T, 2) vertex tracks (cyclic)."""
    n = len(points)
    if n < 3:
        raise ValueError("polygon needs ≥3 vertices")
    area = np.zeros(points[0].shape[0], dtype=np.float64)
    for i in range(n):
        x_i, y_i = points[i][:, 0], points[i][:, 1]
        x_j, y_j = points[(i + 1) % n][:, 0], points[(i + 1) % n][:, 1]
        area += x_i * y_j - y_i * x_j
    return np.abs(area) * 0.5


def skeleton_features(
    parts_xy: Mapping[str, np.ndarray],
    *,
    in_arena_nose: np.ndarray | None = None,
    in_arena_head: np.ndarray | None = None,
) -> np.ndarray:
    """Build ``(T, 22)`` feature matrix from SA-TVM named ``(T, 2)`` tracks.

    ``in_arena_*`` are 0/1 flags length ``T`` (P1/P2). If omitted, P cols are 0.
    """
    missing = [p for p in SA_TVM_PARTS if p not in parts_xy]
    if missing:
        raise KeyError(f"missing SA-TVM parts: {missing}")

    nose = _xy(parts_xy, "nose")
    head = _xy(parts_xy, "head_midpoint")
    neck = _xy(parts_xy, "neck")
    body = _xy(parts_xy, "mouse_center")
    bcl = _xy(parts_xy, "left_midside")
    bcr = _xy(parts_xy, "right_midside")
    hipl = _xy(parts_xy, "left_hip")
    hipr = _xy(parts_xy, "right_hip")
    earl = _xy(parts_xy, "left_ear")
    earr = _xy(parts_xy, "right_ear")
    tailbase = _xy(parts_xy, "tail_base")
    tailmid = _xy(parts_xy, "tail2")
    tailtip = _xy(parts_xy, "tail_end")

    t = nose.shape[0]
    for name, arr in parts_xy.items():
        if name in SA_TVM_PARTS and arr.shape[0] != t:
            raise ValueError(f"length mismatch: {name} has {arr.shape[0]}, expected {t}")

    cols = [
        segment_lengths(nose, head),  # S1
        segment_lengths(head, neck),  # S2
        segment_lengths(neck, body),  # S3
        segment_lengths(body, bcr),  # S4
        segment_lengths(body, bcl),  # S5
        segment_lengths(body, tailbase),  # S6
        segment_lengths(tailbase, hipr),  # S7
        segment_lengths(tailbase, hipl),  # S8
        segment_lengths(tailbase, tailmid),  # S9
        segment_lengths(tailmid, tailtip),  # S10
        angle_between_segments(tailbase, tailmid, tailmid, tailtip),  # A1
        angle_between_segments(hipr, tailbase, tailbase, hipl),  # A2
        angle_between_segments(tailbase, body, body, neck),  # A3
        angle_between_segments(bcr, body, body, bcl),  # A4
        angle_between_segments(body, neck, neck, head),  # A5
        angle_between_segments(tailbase, body, neck, head),  # A6
        polygon_areas([tailbase, hipr, hipl]),  # Ar1
        polygon_areas([hipr, hipl, bcl, bcr]),  # Ar2
        polygon_areas([bcr, earr, earl, bcl]),  # Ar3
        polygon_areas([earr, nose, earl]),  # Ar4
    ]

    if in_arena_nose is None:
        p1 = np.zeros(t, dtype=np.float64)
    else:
        p1 = np.asarray(in_arena_nose, dtype=np.float64).reshape(-1)
        if p1.shape[0] != t:
            raise ValueError("in_arena_nose length mismatch")
    if in_arena_head is None:
        p2 = np.zeros(t, dtype=np.float64)
    else:
        p2 = np.asarray(in_arena_head, dtype=np.float64).reshape(-1)
        if p2.shape[0] != t:
            raise ValueError("in_arena_head length mismatch")

    cols.extend([p1, p2])
    return np.column_stack(cols)


def zscore_skeleton(features: np.ndarray) -> np.ndarray:
    """Per-video z-score on S/A/Ar; leave P1/P2 unchanged (Sturman ``ZScore_normalize_skeleton_v1``)."""
    f = np.asarray(features, dtype=np.float64)
    if f.ndim != 2 or f.shape[1] != N_FEATURES:
        raise ValueError(f"expected (T, {N_FEATURES}), got {f.shape}")
    out = f.copy()
    block = out[:, _ZSCORE_SLICE]
    mean = np.nanmean(block, axis=0)
    sd = np.nanstd(block, axis=0, ddof=0)
    sd = np.where(sd > 0, sd, 1.0)
    out[:, _ZSCORE_SLICE] = (block - mean) / sd
    return out
