"""Fixed-budget pair-sequence scalars (NGramSeq-A).

Reference-free by design: no pooled reference, identical transition budgets
per animal, so bout counts cannot launder into signal (the TransStruct lesson).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FAMILY_METRICS: tuple[str, ...] = ("pair_MI", "bigram_richness")
FAMILY_SEXES: tuple[str, ...] = ("F", "M")
FAMILY_A_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES)
GRAIN = "animal × NOR_TX × nvl_obj (resampled consecutive-bout pairs, portable cluster_id)"
LAPLACE_ALPHA = 1.0
MIN_TRANSITIONS_FLOOR = 50
SEED = 7

# NGramSeq-B: same expanded grains as TransStruct-B (excludes A grain).
TRIAL_ORDER: tuple[str, ...] = ("no_obj", "id_obj", "nvl_obj")
NGRAMSEQ_B_GRAINS: tuple[tuple[str, str], ...] = (
    ("NOR_TX", "full_session"),
    ("NOR_TX", "no_obj"),
    ("NOR_TX", "id_obj"),
    ("NOR_BL", "nvl_obj"),
    ("NOR_REC3hr", "nvl_obj"),
    ("NOR_REC11hr", "nvl_obj"),
)
FAMILY_B_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES) * len(NGRAMSEQ_B_GRAINS)

# NGramSeq-C: complete NOR level grid (parallel to TransStruct-C).
SESSIONS_C: tuple[str, ...] = ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr")
TRIALS_C: tuple[str, ...] = ("no_obj", "id_obj", "nvl_obj")
NGRAMSEQ_C_GRAINS: tuple[tuple[str, str], ...] = tuple(
    (s, t) for s in SESSIONS_C for t in TRIALS_C
)
FAMILY_C_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES) * len(NGRAMSEQ_C_GRAINS)


def resample_pairs(
    labels: np.ndarray,
    states: list[int],
    m: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Raw K×K joint counts from m pairs resampled without replacement."""
    z = np.asarray(labels, dtype=np.int64).ravel()
    n_pairs = int(z.size - 1)
    if m > n_pairs:
        raise ValueError(f"budget m={m} exceeds {n_pairs} pairs")
    sidx = {s: i for i, s in enumerate(states)}
    C = np.zeros((len(states), len(states)), dtype=np.float64)
    for j in rng.choice(n_pairs, size=int(m), replace=False):
        a, b = int(z[j]), int(z[j + 1])
        if a in sidx and b in sidx:
            C[sidx[a], sidx[b]] += 1.0
    return C


def pair_mi_from_counts(counts: np.ndarray, *, alpha: float = LAPLACE_ALPHA) -> float:
    """I(X1;X2) in bits from K×K joint counts (Laplace-smoothed joint)."""
    C = np.asarray(counts, dtype=np.float64)
    k = C.shape[0]
    P = (C + float(alpha)) / (C.sum() + float(alpha) * k * k)
    px = P.sum(axis=1, keepdims=True)
    py = P.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(P > 0, P / np.maximum(px * py, 1e-300), 1.0)
        term = np.where(P > 0, P * np.log2(np.maximum(ratio, 1e-300)), 0.0)
    return float(np.sum(term))


def bigram_richness_from_counts(counts: np.ndarray) -> int:
    """#distinct bigrams in the resampled draw (raw counts, no smoothing)."""
    return int(np.sum(np.asarray(counts, dtype=np.float64) > 0))


def assert_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_A_SIZE:
        raise AssertionError(f"Family NGramSeq-A expects {FAMILY_A_SIZE} finite-p cells, got {n_finite_p}")


def assert_family_b_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_B_SIZE:
        raise AssertionError(f"Family NGramSeq-B expects {FAMILY_B_SIZE} finite-p cells, got {n_finite_p}")


def assert_family_c_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_C_SIZE:
        raise AssertionError(f"Family NGramSeq-C expects {FAMILY_C_SIZE} finite-p cells, got {n_finite_p}")


def score_budgeted_animals(
    seqs: dict[str, np.ndarray],
    meta: dict[str, dict[str, str]],
    states: list[int],
    m: int,
    seed: int = SEED,
    *,
    model: str = "",
    alphabet: str = "",
) -> "pd.DataFrame":
    """MI + richness on a fixed M-pair resample per animal (reference-free)."""
    rng = np.random.default_rng(int(seed))
    rows: list[dict[str, object]] = []
    for aid, labs in seqs.items():
        arr = np.asarray(labs).ravel()
        C = resample_pairs(arr, states, int(m), rng)
        k_used = int(np.sum(count_raw_states(arr, states) > 0))
        rows.append(
            {
                "animal_id": aid,
                "sex": meta[aid]["sex"],
                "condition": meta[aid]["condition"],
                "session": meta[aid].get("session", "NOR_TX"),
                "trial": meta[aid].get("trial", "nvl_obj"),
                "model": model or meta[aid].get("model", ""),
                "alphabet": alphabet,
                "n_states": len(states),
                "n_states_used": k_used,
                "n_transitions_used": int(m),
                "pair_MI": float(pair_mi_from_counts(C)),
                "bigram_richness": int(bigram_richness_from_counts(C)),
            }
        )
    return pd.DataFrame(rows)


def count_raw_states(labels: np.ndarray, states: list[int]) -> np.ndarray:
    """Per-state bout counts (for K_used)."""
    z = np.asarray(labels, dtype=np.int64).ravel()
    sidx = {s: i for i, s in enumerate(states)}
    out = np.zeros(len(states), dtype=np.float64)
    for v in z.tolist():
        if int(v) in sidx:
            out[sidx[int(v)]] += 1.0
    return out
