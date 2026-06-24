"""Block-stratified behavior-token ethogram composites (tier colors)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from maze.kpms.behavior_ethogram.locomotion import LOCO_TIER_COLORS_BGR, tier_color_bgr


@dataclass(frozen=True)
class BoutTierSpan:
    trial_key: str
    row_start: int
    row_end_exclusive: int
    tier: str
    behavior_token: int


def expand_bout_tiers_to_rows(spans: Sequence[BoutTierSpan], n_rows: int) -> np.ndarray:
    """Map bout tier labels onto kpMS row indices (length ``n_rows``)."""
    out = np.array(["unknown"] * n_rows, dtype=object)
    for span in spans:
        lo = max(0, int(span.row_start))
        hi = min(n_rows, int(span.row_end_exclusive))
        if lo < hi:
            out[lo:hi] = span.tier
    return out


def rows_to_phase_seconds(
    tiers: np.ndarray,
    trial_states: Sequence[str],
    *,
    fps: float,
    phase: str,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return per-phase-second tier labels and n_frames contributing.

    Phase onset resets the second counter (RUN or ITI/non-run).
    """
    phase = phase.strip().lower()
    states = [str(s).strip().lower() for s in trial_states]
    if len(states) != len(tiers):
        raise ValueError("tiers and trial_states length mismatch")

    sec_tiers: list[str] = []
    sec_counts: list[int] = []
    cur_sec = -1
    bucket: list[str] = []

    def _flush() -> None:
        nonlocal bucket, cur_sec
        if not bucket:
            return
        vals, counts = np.unique(np.asarray(bucket, dtype=object), return_counts=True)
        sec_tiers.append(str(vals[int(np.argmax(counts))]))
        sec_counts.append(len(bucket))
        bucket = []

    for i, st in enumerate(states):
        in_phase = (st == "run") if phase == "run" else (st != "run")
        if not in_phase:
            continue
        t_sec = int(np.floor(float(i) / float(fps))) if fps > 0 else i
        if t_sec != cur_sec:
            _flush()
            cur_sec = t_sec
        bucket.append(str(tiers[i]))

    _flush()
    if not sec_tiers:
        return np.array([], dtype=object), np.array([], dtype=np.int64)
    return np.asarray(sec_tiers, dtype=object), np.asarray(sec_counts, dtype=np.int64)


def aggregate_mode_tier_per_second(
    trial_seconds: Sequence[tuple[np.ndarray, np.ndarray]],
    max_seconds: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Trial-equal mode tier per integer second up to ``max_seconds``."""
    if max_seconds <= 0:
        return np.array([]), np.array([])
    counts = np.zeros(max_seconds, dtype=np.int64)
    tier_votes: list[list[str]] = [[] for _ in range(max_seconds)]
    for tiers, _frame_counts in trial_seconds:
        for sec, tier in enumerate(tiers):
            if sec >= max_seconds:
                break
            tier_votes[sec].append(str(tier))
            counts[sec] += 1

    mode = np.array(["unknown"] * max_seconds, dtype=object)
    for sec, votes in enumerate(tier_votes):
        if not votes:
            mode[sec] = ""
            continue
        vals, cts = np.unique(np.asarray(votes, dtype=object), return_counts=True)
        mode[sec] = str(vals[int(np.argmax(cts))])
    return mode, counts


def tier_strip_bgr(tier: str) -> tuple[int, int, int]:
    return tier_color_bgr(tier)


def render_tier_ethogram_strip(
    mode_tiers: Sequence[str],
    *,
    height_px: int = 48,
    sec_width_px: int = 4,
) -> np.ndarray:
    """BGR image strip colored by locomotion tier."""
    tiers = [str(t) for t in mode_tiers]
    width = max(1, len(tiers) * sec_width_px)
    img = np.zeros((height_px, width, 3), dtype=np.uint8)
    for i, tier in enumerate(tiers):
        if not tier:
            continue
        color = tier_strip_bgr(tier)
        x0 = i * sec_width_px
        img[:, x0 : x0 + sec_width_px] = color
    return img


def render_tier_legend_bgr() -> np.ndarray:
    import cv2

    labels = [k for k in LOCO_TIER_COLORS_BGR if k != "unknown"]
    row_h = 24
    img = np.zeros((row_h * len(labels), 180, 3), dtype=np.uint8)
    for i, label in enumerate(labels):
        color = LOCO_TIER_COLORS_BGR[label]
        img[i * row_h : (i + 1) * row_h, :20] = color
        cv2.putText(
            img,
            label,
            (28, i * row_h + 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )
    return img
