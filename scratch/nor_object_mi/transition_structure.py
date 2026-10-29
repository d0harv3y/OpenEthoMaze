"""Bout-transition structure scalars (Q5 TransStruct-A).

Portable alphabet: HDBSCAN ``cluster_id`` bout labels. Per-animal
row-stochastic P(next | current) with Laplace smoothing; primary scalar is
total-variation distance to the sex-pooled noSD reference P at the same
grain; companion is conditional entropy H(next | current) in bits.

Locked choices (Family TransStruct-A):
- distance: total variation = 0.5 * L1 over flattened P (all cells).
- smoothing: Laplace alpha=1.0 per possible next state, per row.
- H weights: empirical current-state marginal (row counts / total).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FAMILY_METRICS: tuple[str, ...] = ("trans_dist_to_nosd_ref", "H_next_given_curr")
FAMILY_SEXES: tuple[str, ...] = ("F", "M")
FAMILY_SESSION = "NOR_TX"
FAMILY_TRIAL = "nvl_obj"
FAMILY_A_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES)
GRAIN = "animal × NOR_TX × nvl_obj (consecutive bouts, portable cluster_id)"

# TransStruct-B: expanded grains (user OK 2026-10-05); excludes A grain to avoid double BH.
TRIAL_ORDER: tuple[str, ...] = ("no_obj", "id_obj", "nvl_obj")
TRANSSTRUCT_B_GRAINS: tuple[tuple[str, str], ...] = (
    ("NOR_TX", "full_session"),
    ("NOR_TX", "no_obj"),
    ("NOR_TX", "id_obj"),
    ("NOR_BL", "nvl_obj"),
    ("NOR_REC3hr", "nvl_obj"),
    ("NOR_REC11hr", "nvl_obj"),
)
FAMILY_B_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES) * len(TRANSSTRUCT_B_GRAINS)

# TransStruct-C: complete NOR level grid (all session × trial); excludes synthetic full_session.
SESSIONS_C: tuple[str, ...] = ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr")
TRIALS_C: tuple[str, ...] = ("no_obj", "id_obj", "nvl_obj")
TRANSSTRUCT_C_GRAINS: tuple[tuple[str, str], ...] = tuple(
    (s, t) for s in SESSIONS_C for t in TRIALS_C
)
FAMILY_C_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SEXES) * len(TRANSSTRUCT_C_GRAINS)
LAPLACE_ALPHA = 1.0
MIN_BOUTS = 20


def ordered_states(counts: object) -> list[int]:
    """Sorted unique state ids from a label sequence or count mapping."""
    if isinstance(counts, dict):
        return sorted(int(k) for k in counts)
    arr = np.asarray(list(counts), dtype=np.int64).ravel()
    return sorted(int(x) for x in np.unique(arr))


def count_transitions(
    labels: np.ndarray,
    states: list[int],
) -> np.ndarray:
    """Count matrix C[i, j] for consecutive label pairs over ``states``."""
    idx = {s: i for i, s in enumerate(states)}
    C = np.zeros((len(states), len(states)), dtype=np.float64)
    z = np.asarray(labels, dtype=np.int64).ravel()
    for a, b in zip(z[:-1], z[1:]):
        ia, ib = idx.get(int(a)), idx.get(int(b))
        if ia is not None and ib is not None:
            C[ia, ib] += 1.0
    return C


def row_stochastic_with_laplace(
    counts: np.ndarray,
    *,
    alpha: float = LAPLACE_ALPHA,
) -> np.ndarray:
    """Row-normalize with Laplace smoothing: (C + alpha) / (row_sum + alpha*K)."""
    C = np.asarray(counts, dtype=np.float64)
    k = C.shape[1]
    return (C + float(alpha)) / (C.sum(axis=1, keepdims=True) + float(alpha) * k)


def transition_matrix(
    labels: np.ndarray,
    states: list[int],
    *,
    alpha: float = LAPLACE_ALPHA,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (P, C): smoothed row-stochastic P and raw count matrix C."""
    C = count_transitions(labels, states)
    return row_stochastic_with_laplace(C, alpha=alpha), C


def total_variation(P: np.ndarray, Q: np.ndarray) -> float:
    """Total variation distance: 0.5 * L1 over flattened matrices."""
    p = np.asarray(P, dtype=np.float64)
    q = np.asarray(Q, dtype=np.float64)
    if p.shape != q.shape:
        raise ValueError(f"shape mismatch {p.shape} vs {q.shape}")
    if not np.all(np.isfinite(p)) or not np.all(np.isfinite(q)):
        return float("nan")
    return float(0.5 * np.sum(np.abs(p - q)))


def conditional_entropy_next_given_current(
    P: np.ndarray,
    counts: np.ndarray,
) -> float:
    """H(next | current) in bits with empirical current-state weights.

    pi_i = row_count_i / total transitions; H = -sum_i pi_i sum_j P_ij log2 P_ij.
    """
    P = np.asarray(P, dtype=np.float64)
    C = np.asarray(counts, dtype=np.float64)
    row = C.sum(axis=1)
    total = float(row.sum())
    if total <= 0:
        return float("nan")
    with np.errstate(divide="ignore", invalid="ignore"):
        logP = np.where(P > 0, np.log2(np.where(P > 0, P, 1.0)), 0.0)
    row_H = -np.sum(np.where(P > 0, P * logP, 0.0), axis=1)
    pi = row / total
    return float(np.sum(pi * row_H))


def pooled_reference_P(
    label_seqs: list[np.ndarray],
    states: list[int],
    *,
    alpha: float = LAPLACE_ALPHA,
) -> tuple[np.ndarray, np.ndarray]:
    """Pool transitions across sequences, then smooth once (reference P)."""
    C = np.zeros((len(states), len(states)), dtype=np.float64)
    for z in label_seqs:
        C += count_transitions(np.asarray(z, dtype=np.int64), states)
    return row_stochastic_with_laplace(C, alpha=alpha), C


def assert_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_A_SIZE:
        raise AssertionError(f"Family TransStruct-A expects {FAMILY_A_SIZE} finite-p cells, got {n_finite_p}")


def assert_family_b_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_B_SIZE:
        raise AssertionError(f"Family TransStruct-B expects {FAMILY_B_SIZE} finite-p cells, got {n_finite_p}")


def assert_family_c_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_C_SIZE:
        raise AssertionError(f"Family TransStruct-C expects {FAMILY_C_SIZE} finite-p cells, got {n_finite_p}")


def score_animals(
    seqs: dict[str, np.ndarray],
    meta: dict[str, dict[str, str]],
    states: list[int],
    *,
    alpha: float = LAPLACE_ALPHA,
    model: str = "",
    alphabet: str = "",
    ref_condition: str = "noSD",
) -> "pd.DataFrame":
    """Per-animal TV-to-pooled-reference + H from bout-label sequences.

    ``seqs`` maps animal_id to 1-D bout-label array; ``meta`` maps animal_id
    to a dict with at least ``sex`` and ``condition``. The reference P is
    pooled over ``ref_condition`` animals per sex. Only valid when all
    sequences share one alphabet (pooled fits) — never for per-animal fits.
    """
    refs: dict[str, np.ndarray] = {}
    for sex in FAMILY_SEXES:
        ref_seqs = [labs for aid, labs in seqs.items() if meta[aid]["sex"] == sex and meta[aid]["condition"] == ref_condition]
        if not ref_seqs:
            raise ValueError(f"no {ref_condition} sequences for sex {sex!r}")
        P_ref, _ = pooled_reference_P(ref_seqs, states, alpha=alpha)
        refs[sex] = P_ref
    rows: list[dict[str, object]] = []
    for aid, labs in seqs.items():
        arr = np.asarray(labs).ravel()
        P, C = transition_matrix(arr, states, alpha=alpha)
        rows.append(
            {
                "animal_id": aid,
                "sex": meta[aid]["sex"],
                "condition": meta[aid]["condition"],
                "session": meta[aid].get("session", FAMILY_SESSION),
                "trial": meta[aid].get("trial", FAMILY_TRIAL),
                "model": model or meta[aid].get("model", ""),
                "alphabet": alphabet,
                "n_states": len(states),
                "n_bouts": int(arr.size),
                "n_transitions": int(arr.size - 1),
                "H_next_given_curr": float(conditional_entropy_next_given_current(P, C)),
                "trans_dist_to_nosd_ref": float(total_variation(P, refs[meta[aid]["sex"]])),
            }
        )
    return pd.DataFrame(rows)
