"""Syllable-stream bout cleanup (no frames discarded).

Matches ``_syllable_descriptives/cleanup_rule.txt``:
absorb bouts shorter than ``min_bout_frames`` into a neighbor.
"""

from __future__ import annotations

import numpy as np


def rle_labels(z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (labels, durations, starts) for contiguous runs."""
    z = np.asarray(z, dtype=np.int64).ravel()
    if z.size == 0:
        empty = np.empty(0, np.int64)
        return empty, empty, empty
    ch = np.flatnonzero(z[1:] != z[:-1]) + 1
    starts = np.concatenate(([0], ch))
    ends = np.concatenate((ch, [z.size]))
    return z[starts].astype(np.int64), (ends - starts).astype(np.int64), starts


def absorb_short_bouts(
    z: np.ndarray,
    min_len: int = 3,
    *,
    max_passes: int = 32,
) -> np.ndarray:
    """Reassign frames in short bouts to a neighbor; never drop frames.

    Neighbor policy:
    - only one neighbor → that label
    - left == right → bridge with that label
    - else → longer neighbor (tie → left)
    """
    if min_len <= 1:
        return np.asarray(z, dtype=np.int64).copy()
    out = np.asarray(z, dtype=np.int64).copy()
    for _ in range(max_passes):
        labels, durs, starts = rle_labels(out)
        if labels.size == 0:
            break
        ends = starts + durs
        short = np.flatnonzero(durs < min_len)
        if short.size == 0:
            break
        new = out.copy()
        for i in short:
            left = labels[i - 1] if i > 0 else None
            right = labels[i + 1] if i + 1 < labels.size else None
            if left is None and right is None:
                continue
            if left is None:
                fill = int(right)
            elif right is None:
                fill = int(left)
            elif left == right:
                fill = int(left)
            else:
                fill = int(left) if durs[i - 1] >= durs[i + 1] else int(right)
            new[starts[i] : ends[i]] = fill
        if np.array_equal(new, out):
            break
        out = new
    return out


def maybe_absorb_short_bouts(
    z: np.ndarray,
    min_bout_frames: int | None,
) -> np.ndarray:
    """Apply :func:`absorb_short_bouts` when ``min_bout_frames`` > 1."""
    syll = np.asarray(z, dtype=np.int64).ravel()
    if min_bout_frames is None or int(min_bout_frames) <= 1:
        return syll
    return absorb_short_bouts(syll, int(min_bout_frames))
