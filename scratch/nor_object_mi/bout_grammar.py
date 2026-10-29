"""Novel-prox visit grammar (Q5 BoutGrammar Family A).

Portable NOR H5 scores — no kpMS syllable ids. Prox radius r = 0.10 m.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

NEAR_R_M = 0.10
FAMILY_METRICS: tuple[str, ...] = (
    "n_nvl_entries",
    "mean_nvl_visit_dur_s",
    "frac_still_near_nvl",
)
FAMILY_SESSIONS: tuple[str, ...] = (
    "NOR_BL",
    "NOR_TX",
    "NOR_REC3hr",
    "NOR_REC11hr",
)
FAMILY_SEXES: tuple[str, ...] = ("F", "M")
FAMILY_A_SIZE: int = len(FAMILY_METRICS) * len(FAMILY_SESSIONS) * len(FAMILY_SEXES)
TRIAL = "nvl_obj"
GRAIN = "animal × {session} × nvl_obj × nvl_prox_visit_r={r:g}m"


def contiguous_true_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return ``[start, end)`` runs where ``mask`` is True."""
    m = np.asarray(mask, dtype=bool)
    if m.size == 0:
        return []
    # Pad edges so transitions always close.
    padded = np.concatenate([[False], m, [False]])
    d = np.diff(padded.astype(np.int8))
    starts = np.where(d == 1)[0]
    ends = np.where(d == -1)[0]
    return [(int(s), int(e)) for s, e in zip(starts, ends)]


def near_mask(dist_m: np.ndarray, valid: np.ndarray, *, r_m: float = NEAR_R_M) -> np.ndarray:
    """Near-object mask: valid and finite distance < r."""
    d = np.asarray(dist_m, dtype=np.float64)
    ok = np.asarray(valid, dtype=bool) & np.isfinite(d)
    return ok & (d < float(r_m))


def immobile_mask_from_spans(
    n_frames: int,
    immobile_spans: Sequence[tuple[int, int, int]],
) -> np.ndarray:
    """Boolean immobile mask from ``(idx, start, end_exclusive)`` spans."""
    out = np.zeros(int(n_frames), dtype=bool)
    n = int(n_frames)
    for _i, start, end in immobile_spans:
        s = max(0, int(start))
        e = min(n, int(end))
        if e > s:
            out[s:e] = True
    return out


def bout_grammar_from_masks(
    near_nvl: np.ndarray,
    immobile: np.ndarray,
    *,
    fps: float,
) -> dict[str, float]:
    """Scalars from near-nvl and immobile frame masks."""
    near = np.asarray(near_nvl, dtype=bool)
    still = np.asarray(immobile, dtype=bool)
    if near.shape != still.shape:
        raise ValueError(f"mask length mismatch {near.shape} vs {still.shape}")
    runs = contiguous_true_runs(near)
    n_entries = len(runs)
    n_near = int(np.sum(near))
    if not np.isfinite(fps) or fps <= 0:
        return {
            "n_nvl_entries": float(n_entries),
            "mean_nvl_visit_dur_s": float("nan"),
            "median_nvl_visit_dur_s": float("nan"),
            "total_nvl_near_s": float("nan"),
            "frac_still_near_nvl": float("nan"),
            "n_near_frames": float(n_near),
        }
    dur_s = np.asarray([(e - s) / float(fps) for s, e in runs], dtype=np.float64)
    total_near_s = float(n_near / float(fps))
    if n_entries == 0:
        mean_dur = float("nan")
        med_dur = float("nan")
    else:
        mean_dur = float(np.mean(dur_s))
        med_dur = float(np.median(dur_s))
    if n_near == 0:
        frac_still = float("nan")
    else:
        frac_still = float(np.sum(near & still) / n_near)
    return {
        "n_nvl_entries": float(n_entries),
        "mean_nvl_visit_dur_s": mean_dur,
        "median_nvl_visit_dur_s": med_dur,
        "total_nvl_near_s": total_near_s,
        "frac_still_near_nvl": frac_still,
        "n_near_frames": float(n_near),
    }


def family_a_cell_keys() -> list[tuple[str, str, str]]:
    return [
        (session, sex, metric)
        for session in FAMILY_SESSIONS
        for sex in FAMILY_SEXES
        for metric in FAMILY_METRICS
    ]


def assert_family_a_size(n_finite_p: int) -> None:
    if int(n_finite_p) != FAMILY_A_SIZE:
        raise AssertionError(
            f"Family BoutGrammar-A expects {FAMILY_A_SIZE} finite-p cells, got {n_finite_p}"
        )


def row_in_family_a(row: Mapping[str, object]) -> bool:
    return (
        str(row.get("session", "")) in FAMILY_SESSIONS
        and str(row.get("sex", "")) in FAMILY_SEXES
        and str(row.get("metric", "")) in FAMILY_METRICS
        and str(row.get("trial", TRIAL)) == TRIAL
        and str(row.get("test", "kruskal")) == "kruskal"
    )
