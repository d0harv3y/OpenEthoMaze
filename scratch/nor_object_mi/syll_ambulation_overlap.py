"""Temporal join of syllable bouts with movement / immobile spans.

Syllable labels tile the session, so “do syllables occur during movement?” is
not a question — they occur always. The join is:

- each syllable bout interval ∩ movement intervals (exclusive ends)
- frame counts → I(syllable identity ; locomotor state) and Cramér V
- unweighted bout-mean P(move|bout) vs session P(move) (duration structure)
- median bout duration among majority-move vs majority-still bouts

Grain: animal × phase × novel_obj (locked kpMS model).
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def overlap_frames(start_a: int, end_a: int, start_b: int, end_b: int) -> int:
    """Length of ``[start, end)`` ∩ ``[start, end)``."""
    lo = max(int(start_a), int(start_b))
    hi = min(int(end_a), int(end_b))
    return max(0, hi - lo)


def frames_in_spans(
    start: int,
    end: int,
    spans: Sequence[tuple[int, int]],
) -> int:
    """Sum of overlap with sorted disjoint ``(start, end_exclusive)`` spans."""
    n = 0
    s0, e0 = int(start), int(end)
    for s1, e1 in spans:
        if e1 <= s0:
            continue
        if s1 >= e0:
            break
        n += overlap_frames(s0, e0, s1, e1)
    return n


def mutual_info_bits(move_counts: np.ndarray, still_counts: np.ndarray) -> float:
    """I(syllable; locomotor) in bits from per-syllable frame counts."""
    m = np.asarray(move_counts, dtype=np.float64)
    s = np.asarray(still_counts, dtype=np.float64)
    if m.shape != s.shape:
        raise ValueError("move/still count length mismatch")
    n_xy = np.column_stack([m, s])
    n = float(n_xy.sum())
    if n <= 0:
        return float("nan")
    p_xy = n_xy / n
    p_x = p_xy.sum(axis=1, keepdims=True)
    p_y = p_xy.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where((p_xy > 0) & (p_x > 0) & (p_y > 0), p_xy / (p_x * p_y), 1.0)
        terms = np.where(p_xy > 0, p_xy * np.log2(ratio), 0.0)
    return float(np.sum(terms))


def cramers_v_kx2(move_counts: np.ndarray, still_counts: np.ndarray) -> float:
    """Cramér V for a k×2 occupancy table (syllable × {move, still})."""
    m = np.asarray(move_counts, dtype=np.float64)
    s = np.asarray(still_counts, dtype=np.float64)
    table = np.column_stack([m, s])
    n = float(table.sum())
    if n <= 0:
        return float("nan")
    row = table.sum(axis=1, keepdims=True)
    col = table.sum(axis=0, keepdims=True)
    expected = row * col / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi = np.where(expected > 0, (table - expected) ** 2 / expected, 0.0)
    chi2 = float(np.sum(chi))
    return float(np.sqrt(chi2 / n))


def _sorted_spans(df: pd.DataFrame) -> list[tuple[int, int]]:
    if df.empty:
        return []
    starts = pd.to_numeric(df["row_start"], errors="coerce").to_numpy()
    ends = pd.to_numeric(df["row_end_exclusive"], errors="coerce").to_numpy()
    pairs = [
        (int(s), int(e))
        for s, e in zip(starts, ends, strict=True)
        if np.isfinite(s) and np.isfinite(e) and int(e) > int(s)
    ]
    pairs.sort(key=lambda p: p[0])
    return pairs


def locomotor_raster(
    move: pd.DataFrame,
    still: pd.DataFrame,
    *,
    n_frames: int,
) -> np.ndarray:
    """Frame labels: -1 uncovered, 0 still, 1 move. Move overwrites still."""
    n = int(n_frames)
    if n <= 0:
        return np.empty(0, dtype=np.int8)
    raster = np.full(n, -1, dtype=np.int8)
    for s, e in _sorted_spans(still):
        lo = max(0, s)
        hi = min(n, e)
        if hi > lo:
            raster[lo:hi] = 0
    for s, e in _sorted_spans(move):
        lo = max(0, s)
        hi = min(n, e)
        if hi > lo:
            raster[lo:hi] = 1
    return raster


def bout_occupancy_on_raster(
    starts: np.ndarray,
    ends: np.ndarray,
    raster: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-bout move/still frame counts on a locomotor raster."""
    starts = np.asarray(starts, dtype=np.int64)
    ends = np.asarray(ends, dtype=np.int64)
    n = int(starts.size)
    n_move = np.zeros(n, dtype=np.int32)
    n_still = np.zeros(n, dtype=np.int32)
    length = int(raster.size)
    for i in range(n):
        a = int(starts[i])
        b = int(ends[i])
        if a < 0:
            a = 0
        if b > length:
            b = length
        if b <= a:
            continue
        seg = raster[a:b]
        n_move[i] = int(np.sum(seg == 1))
        n_still[i] = int(np.sum(seg == 0))
    return n_move, n_still


def occupancy_from_frame_counts(counts: pd.DataFrame) -> pd.DataFrame:
    """Session×syllable occupancy from summed move/still frames."""
    if counts.empty:
        return pd.DataFrame()
    keys = ["animal_id", "raw_session", "phase_layer"]
    if "model" in counts.columns:
        keys = ["model", *keys]
    if "condition_layer" in counts.columns:
        keys = [*keys, "condition_layer"]
    df = counts.copy()
    df["animal_id"] = df["animal_id"].astype(str)
    sess = df.groupby(keys, sort=False).agg(
        n_move_session=("n_move_frames", "sum"),
        n_still_session=("n_still_frames", "sum"),
        tx=("tx", "first"),
        sex=("sex", "first"),
    )
    labeled = sess["n_move_session"] + sess["n_still_session"]
    sess["p_session_move"] = np.where(labeled > 0, sess["n_move_session"] / labeled, np.nan)
    syll_keys = [*keys, "raw_syllable_id"]
    by = df.groupby(syll_keys, sort=False).agg(
        n_move_frames=("n_move_frames", "sum"),
        n_still_frames=("n_still_frames", "sum"),
        tx=("tx", "first"),
        sex=("sex", "first"),
    )
    out = by.reset_index().merge(
        sess[["p_session_move"]].reset_index(),
        on=keys,
        how="left",
    )
    lab = out["n_move_frames"] + out["n_still_frames"]
    out["p_move_given_syll"] = np.where(lab > 0, out["n_move_frames"] / lab, np.nan)
    out["enrich_move"] = out["p_move_given_syll"] - out["p_session_move"]
    return out


def annotate_syllable_bouts(
    syll: pd.DataFrame,
    move: pd.DataFrame,
    still: pd.DataFrame,
) -> pd.DataFrame:
    """Add overlap_move_frames / overlap_still_frames on one session's bouts."""
    move_spans = _sorted_spans(move)
    still_spans = _sorted_spans(still)
    rows = []
    for rec in syll.itertuples(index=False):
        start = int(rec.row_start)
        end = int(rec.row_end_exclusive)
        n_move = frames_in_spans(start, end, move_spans)
        n_still = frames_in_spans(start, end, still_spans)
        n = int(end - start)
        labeled = n_move + n_still
        frac_move = float(n_move / labeled) if labeled > 0 else float("nan")
        if labeled <= 0:
            majority = "uncovered"
        elif n_move > n_still:
            majority = "movement"
        elif n_still > n_move:
            majority = "immobile"
        else:
            majority = "tie"
        rows.append(
            {
                "overlap_move_frames": n_move,
                "overlap_still_frames": n_still,
                "overlap_labeled_frames": labeled,
                "overlap_uncovered_frames": int(n - labeled),
                "overlap_move_frac": frac_move,
                "majority_locomotor": majority,
            }
        )
    extra = pd.DataFrame(rows)
    return pd.concat([syll.reset_index(drop=True), extra], axis=1)


def session_association(annotated: pd.DataFrame) -> dict[str, object]:
    """Session-grain association scalars from bout-level overlap."""
    if annotated.empty:
        return {
            "n_syll_bouts": 0,
            "n_syllable_ids": 0,
            "n_move_frames": 0,
            "n_still_frames": 0,
            "p_session_move": float("nan"),
            "mean_bout_move_frac": float("nan"),
            "enrich_unweighted_move": float("nan"),
            "i_syllable_locomotor_bits": float("nan"),
            "cramers_v": float("nan"),
            "n_majority_move": 0,
            "n_majority_still": 0,
            "median_duration_s_majority_move": float("nan"),
            "median_duration_s_majority_still": float("nan"),
            "delta_median_duration_s_move_minus_still": float("nan"),
        }
    n_move = int(pd.to_numeric(annotated["overlap_move_frames"], errors="coerce").fillna(0).sum())
    n_still = int(pd.to_numeric(annotated["overlap_still_frames"], errors="coerce").fillna(0).sum())
    labeled = n_move + n_still
    p_move = float(n_move / labeled) if labeled > 0 else float("nan")
    frac = pd.to_numeric(annotated["overlap_move_frac"], errors="coerce")
    mean_bout = float(np.nanmean(frac.to_numpy(dtype=np.float64))) if frac.notna().any() else float("nan")
    by = annotated.groupby("raw_syllable_id", sort=False)
    move_c = by["overlap_move_frames"].sum().to_numpy(dtype=np.float64)
    still_c = by["overlap_still_frames"].sum().to_numpy(dtype=np.float64)
    maj = annotated["majority_locomotor"].astype(str)
    dur = pd.to_numeric(annotated["bout_duration_s"], errors="coerce")
    d_move = dur[maj == "movement"]
    d_still = dur[maj == "immobile"]
    med_m = float(np.nanmedian(d_move.to_numpy(dtype=np.float64))) if d_move.notna().any() else float("nan")
    med_s = float(np.nanmedian(d_still.to_numpy(dtype=np.float64))) if d_still.notna().any() else float("nan")
    return {
        "n_syll_bouts": int(len(annotated)),
        "n_syllable_ids": int(annotated["raw_syllable_id"].nunique()),
        "n_move_frames": n_move,
        "n_still_frames": n_still,
        "p_session_move": p_move,
        "mean_bout_move_frac": mean_bout,
        "enrich_unweighted_move": (
            float(mean_bout - p_move) if np.isfinite(mean_bout) and np.isfinite(p_move) else float("nan")
        ),
        "i_syllable_locomotor_bits": mutual_info_bits(move_c, still_c),
        "cramers_v": cramers_v_kx2(move_c, still_c),
        "n_majority_move": int((maj == "movement").sum()),
        "n_majority_still": int((maj == "immobile").sum()),
        "median_duration_s_majority_move": med_m,
        "median_duration_s_majority_still": med_s,
        "delta_median_duration_s_move_minus_still": (
            float(med_m - med_s) if np.isfinite(med_m) and np.isfinite(med_s) else float("nan")
        ),
    }


def occupancy_by_syllable(annotated: pd.DataFrame) -> pd.DataFrame:
    """Frame occupancy per syllable id on one session (move vs still)."""
    if annotated.empty:
        return pd.DataFrame(
            columns=[
                "raw_syllable_id",
                "n_move_frames",
                "n_still_frames",
                "p_move_given_syll",
                "p_session_move",
                "enrich_move",
            ]
        )
    n_move = int(pd.to_numeric(annotated["overlap_move_frames"], errors="coerce").fillna(0).sum())
    n_still = int(pd.to_numeric(annotated["overlap_still_frames"], errors="coerce").fillna(0).sum())
    labeled = n_move + n_still
    p_session = float(n_move / labeled) if labeled > 0 else float("nan")
    by = annotated.groupby("raw_syllable_id", sort=False)
    move_c = by["overlap_move_frames"].sum()
    still_c = by["overlap_still_frames"].sum()
    rows: list[dict[str, object]] = []
    for sid in move_c.index:
        m = float(move_c.loc[sid])
        s = float(still_c.loc[sid])
        lab = m + s
        p = float(m / lab) if lab > 0 else float("nan")
        rows.append(
            {
                "raw_syllable_id": int(sid),
                "n_move_frames": int(m),
                "n_still_frames": int(s),
                "p_move_given_syll": p,
                "p_session_move": p_session,
                "enrich_move": (
                    float(p - p_session) if np.isfinite(p) and np.isfinite(p_session) else float("nan")
                ),
            }
        )
    return pd.DataFrame(rows)


def occupancy_from_bouts(bouts: pd.DataFrame) -> pd.DataFrame:
    """Animal × session × syllable occupancy (concatenated annotated bouts)."""
    if bouts.empty:
        return pd.DataFrame()
    df = bouts.copy()
    df["animal_id"] = df["animal_id"].astype(str)
    parts: list[pd.DataFrame] = []
    keys = ["animal_id", "raw_session", "phase_layer"]
    for key, g in df.groupby(keys, sort=False):
        occ = occupancy_by_syllable(g)
        if occ.empty:
            continue
        aid, sess, phase = key
        occ.insert(0, "animal_id", str(aid))
        occ.insert(1, "raw_session", sess)
        occ.insert(2, "phase_layer", phase)
        occ["tx"] = g["tx"].iloc[0]
        occ["sex"] = g["sex"].iloc[0]
        occ["model"] = g["model"].iloc[0]
        if "condition_layer" in g.columns:
            occ["condition_layer"] = g["condition_layer"].iloc[0]
        parts.append(occ)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)
