"""Session-grain Pearson among two segmenters' summaries (not lagged CCF).

Same frame index, two partitions: hysteresis move|still vs kpMS syllable RLE.
Grain: animal × phase × novel_obj. Heatmap is D; Pearson r/p live in the table.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nor_object_mi.simpler_first_protocol_prologue import pearson_pair
from nor_object_mi.simpler_first_q1 import weighted_mean

BLOCKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "locomotor",
        (
            "p_session_move",
            "n_move_bouts",
            "n_still_bouts",
            "median_move_duration_s",
            "median_still_duration_s",
        ),
    ),
    (
        "syllable",
        (
            "n_syll_bouts",
            "n_syllable_ids",
            "median_syll_duration_s",
            "shannon_syll_bits",
        ),
    ),
    (
        "join",
        (
            "i_syllable_locomotor_bits",
            "cramers_v",
            "enrich_unweighted_move",
            "delta_median_duration_s_move_minus_still",
        ),
    ),
    (
        "kinematics",
        (
            "speed_syll_mps",
            "speed_move_mps",
        ),
    ),
)

FEATURES: tuple[str, ...] = tuple(c for _b, cols in BLOCKS for c in cols)
LITMUS_A = "speed_syll_mps"
LITMUS_B = "speed_move_mps"
FEATURE_LABELS: dict[str, str] = {
    "p_session_move": "P(move)",
    "n_move_bouts": "n move",
    "n_still_bouts": "n still",
    "median_move_duration_s": "med dur move",
    "median_still_duration_s": "med dur still",
    "n_syll_bouts": "n syll",
    "n_syllable_ids": "n ids",
    "median_syll_duration_s": "med dur syll",
    "shannon_syll_bits": "H syll",
    "i_syllable_locomotor_bits": "I bits",
    "cramers_v": "Cramér V",
    "enrich_unweighted_move": "enrich",
    "delta_median_duration_s_move_minus_still": "Δdur maj",
    "speed_syll_mps": "speed syll",
    "speed_move_mps": "speed move",
}


def shannon_bits(labels: np.ndarray) -> float:
    """Shannon H in bits of a label vector. One class → 0."""
    s = pd.Series(labels).dropna()
    if s.empty:
        return float("nan")
    p = s.value_counts(normalize=True).to_numpy(dtype=np.float64)
    return float(-(p * np.log2(p)).sum())


def block_index(name: str) -> int:
    for i, (block, cols) in enumerate(BLOCKS):
        if name in cols:
            return i
        if name == block:
            return i
    raise KeyError(name)


def block_edges() -> list[float]:
    """Grid lines *after* each block (except the last)."""
    edges: list[float] = []
    acc = 0
    for _b, cols in BLOCKS[:-1]:
        acc += len(cols)
        edges.append(acc - 0.5)
    return edges


def session_bout_summary(
    bouts: pd.DataFrame,
    *,
    speed_col: str,
    duration_col: str,
    frames_col: str,
) -> pd.DataFrame:
    """One row per animal × session × phase: n, median duration, frame-weighted speed."""
    if bouts.empty:
        return pd.DataFrame(
            columns=[
                "animal_id",
                "raw_session",
                "phase_layer",
                "n_bouts",
                "median_duration_s",
                "speed_mps",
            ]
        )
    df = bouts.copy()
    df["animal_id"] = df["animal_id"].astype(str)
    keys = ["animal_id", "raw_session", "phase_layer"]
    rows: list[dict[str, object]] = []
    for key, g in df.groupby(keys, sort=False):
        aid, sess, phase = key
        speed = pd.to_numeric(g[speed_col], errors="coerce").to_numpy(dtype=np.float64)
        frames = pd.to_numeric(g[frames_col], errors="coerce").to_numpy(dtype=np.float64)
        dur = pd.to_numeric(g[duration_col], errors="coerce")
        rows.append(
            {
                "animal_id": str(aid),
                "raw_session": sess,
                "phase_layer": phase,
                "n_bouts": int(len(g)),
                "median_duration_s": float(np.nanmedian(dur.to_numpy(dtype=np.float64)))
                if dur.notna().any()
                else float("nan"),
                "speed_mps": weighted_mean(speed, frames),
            }
        )
    return pd.DataFrame(rows)


def session_syllable_summary(bouts: pd.DataFrame) -> pd.DataFrame:
    """Syllable-segmenter session scalars including Shannon of ids."""
    base = session_bout_summary(
        bouts,
        speed_col="bout_mean_speed_mps",
        duration_col="bout_duration_s",
        frames_col="bout_frames",
    )
    if bouts.empty:
        base["n_syllable_ids"] = pd.Series(dtype=int)
        base["shannon_syll_bits"] = pd.Series(dtype=float)
        return base
    df = bouts.copy()
    df["animal_id"] = df["animal_id"].astype(str)
    extra_rows: list[dict[str, object]] = []
    for key, g in df.groupby(["animal_id", "raw_session", "phase_layer"], sort=False):
        aid, sess, phase = key
        extra_rows.append(
            {
                "animal_id": str(aid),
                "raw_session": sess,
                "phase_layer": phase,
                "n_syllable_ids": int(g["raw_syllable_id"].nunique()),
                "shannon_syll_bits": shannon_bits(g["raw_syllable_id"].to_numpy()),
            }
        )
    extra = pd.DataFrame(extra_rows)
    return base.merge(extra, on=["animal_id", "raw_session", "phase_layer"], how="left")


def join_session_features(
    overlap: pd.DataFrame,
    syll: pd.DataFrame,
    move: pd.DataFrame,
    still: pd.DataFrame,
) -> pd.DataFrame:
    """Inner-join overlap + both segmenters on animal × session × phase."""
    ov = overlap.copy()
    ov["animal_id"] = ov["animal_id"].astype(str)
    sy = session_syllable_summary(syll).rename(
        columns={
            "n_bouts": "n_syll_bouts_kin",
            "median_duration_s": "median_syll_duration_s",
            "speed_mps": "speed_syll_mps",
        }
    )
    mv = session_bout_summary(
        move,
        speed_col="bout_mean_speed_mps",
        duration_col="bout_duration_s",
        frames_col="bout_frames",
    ).rename(
        columns={
            "n_bouts": "n_move_bouts",
            "median_duration_s": "median_move_duration_s",
            "speed_mps": "speed_move_mps",
        }
    )
    st = session_bout_summary(
        still,
        speed_col="bout_mean_speed_mps",
        duration_col="bout_duration_s",
        frames_col="bout_frames",
    ).rename(
        columns={
            "n_bouts": "n_still_bouts",
            "median_duration_s": "median_still_duration_s",
            "speed_mps": "speed_still_mps",
        }
    )
    keys = ["animal_id", "raw_session", "phase_layer"]
    ov = ov.drop(columns=[c for c in ("n_syllable_ids",) if c in ov.columns])
    out = ov.merge(sy, on=keys, how="inner")
    out = out.merge(mv, on=keys, how="inner")
    out = out.merge(st[keys + ["n_still_bouts", "median_still_duration_s"]], on=keys, how="inner")
    if "n_syll_bouts" not in out.columns and "n_syll_bouts_kin" in out.columns:
        out["n_syll_bouts"] = out["n_syll_bouts_kin"]
    return out


def pearson_matrix(sessions: pd.DataFrame, columns: tuple[str, ...] = FEATURES) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pairwise Pearson (complete pairs). Diagonal is identity when n ≥ 3."""
    k = len(columns)
    r = np.full((k, k), np.nan)
    p = np.full((k, k), np.nan)
    n = np.zeros((k, k), dtype=np.int64)
    for i, a in enumerate(columns):
        for j, b in enumerate(columns):
            rec = pearson_pair(sessions[a].to_numpy(), sessions[b].to_numpy())
            r[i, j] = rec["pearson_r"]
            p[i, j] = rec["p"]
            n[i, j] = int(rec["n"])
    return r, p, n


def pearson_long(
    sessions: pd.DataFrame,
    *,
    phase: str,
    columns: tuple[str, ...] = FEATURES,
) -> pd.DataFrame:
    r, p, n = pearson_matrix(sessions, columns)
    rows: list[dict[str, object]] = []
    for i, a in enumerate(columns):
        for j, b in enumerate(columns):
            rows.append(
                {
                    "phase_layer": phase,
                    "feature_i": a,
                    "feature_j": b,
                    "block_i": BLOCKS[block_index(a)][0],
                    "block_j": BLOCKS[block_index(b)][0],
                    "pearson_r": float(r[i, j]),
                    "p": float(p[i, j]),
                    "n": int(n[i, j]),
                    "litmus_speed": bool(
                        {a, b} == {LITMUS_A, LITMUS_B} and a != b
                    ),
                }
            )
    return pd.DataFrame(rows)
