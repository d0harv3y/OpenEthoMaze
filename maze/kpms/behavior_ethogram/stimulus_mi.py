"""Stimulus-conditioned mutual information per animal (pilot analysis)."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

import numpy as np
from scipy import stats

from maze.kpms.behavior_ethogram.behavior_token_summarize import bout_in_phase

from .stimulus_join import bout_rows_for_phase
from .stimulus_mi_contract import (
    EARLY_LATE_K,
    GROUP_FACTORS,
    GROUP_MI_TEST_FIELDS,
    GROUP_MI_WHEN_TEST_FIELDS,
    MI_PER_ANIMAL_FIELDS,
    MI_PER_TRIAL_FIELDS,
    MI_TRIAL_ANIMAL_SUMMARY_FIELDS,
    MI_TYPES,
    MIN_TRIALS_FOR_EARLY_LATE,
    NULL_CLEAR_ALPHA,
    PRIMARY_WHEN_MI_TYPE,
    PRIMARY_WHEN_PHASE,
    STIM_PHASES,
    STIM_VARS,
    TRIAL_NULL_N_PERM,
    WHEN_TEST_METRICS,
)

LN2 = np.log(2.0)
MiType = Literal["occupancy", "transition"]
StimVar = Literal["duty", "dist"]
PhaseName = Literal["run", "iti"]


@dataclass(frozen=True)
class StimulusBinEdges:
    duty: np.ndarray
    dist: np.ndarray
    n_bins: int


@dataclass(frozen=True)
class AnimalMiResult:
    animal_id: str
    sex: str
    strain: str
    tx: str
    phase: str
    stim_var: str
    mi_type: str
    n_bouts: int
    H_stim: float
    H_syll: float
    mi_raw: float
    mi_mm: float
    null_circ_mean: float
    null_circ_p: float
    null_perm_mean: float
    null_perm_p: float
    iti_control_flag: int


def _entropy_bits(counts: np.ndarray) -> float:
    n = counts.sum()
    if n == 0:
        return 0.0
    p = counts[counts > 0] / n
    return float(-(p * np.log2(p)).sum())


def _mm_term_bits(occupied_bins: int, n: int) -> float:
    if n == 0:
        return 0.0
    return (occupied_bins - 1) / (2.0 * n * LN2)


def _joint_counts(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    xs, x_idx = np.unique(x, return_inverse=True)
    ys, y_idx = np.unique(y, return_inverse=True)
    joint = np.zeros((xs.size, ys.size), dtype=np.int64)
    np.add.at(joint, (x_idx, y_idx), 1)
    return joint


def _triple_counts(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
    xs, x_idx = np.unique(x, return_inverse=True)
    ys, y_idx = np.unique(y, return_inverse=True)
    zs, z_idx = np.unique(z, return_inverse=True)
    joint = np.zeros((xs.size, ys.size, zs.size), dtype=np.int64)
    np.add.at(joint, (x_idx, y_idx, z_idx), 1)
    return joint


def occupancy_mi(syllable: np.ndarray, stim_bin: np.ndarray) -> tuple[float, float, float, float, int]:
    """Return ``(mi_raw, mi_mm, H_syll, H_stim, n)`` in bits for ``I(syllable; stim_bin)``."""
    syllable = np.asarray(syllable)
    stim_bin = np.asarray(stim_bin)
    n = syllable.shape[0]
    if n == 0 or n != stim_bin.shape[0]:
        raise ValueError("syllable and stim_bin must be equal-length, non-empty")

    joint = _joint_counts(syllable, stim_bin)
    cx = joint.sum(axis=1)
    cy = joint.sum(axis=0)
    hx = _entropy_bits(cx)
    hy = _entropy_bits(cy)
    hxy = _entropy_bits(joint.ravel())
    mi_raw = hx + hy - hxy

    kx = int((cx > 0).sum())
    ky = int((cy > 0).sum())
    kxy = int((joint > 0).sum())
    mm_adjust = _mm_term_bits(kx, n) + _mm_term_bits(ky, n) - _mm_term_bits(kxy, n)
    mi_mm = mi_raw + mm_adjust
    return mi_raw, mi_mm, hx, hy, n


def transition_mi(
    cur_syll: np.ndarray,
    next_syll: np.ndarray,
    stim_bin: np.ndarray,
) -> tuple[float, float, float, float, int]:
    """Return ``(mi_raw, mi_mm, H_next, H_stim, n_pairs)`` for ``I(next; stim | cur)``."""
    cur_syll = np.asarray(cur_syll)
    next_syll = np.asarray(next_syll)
    stim_bin = np.asarray(stim_bin)
    n = cur_syll.shape[0]
    if n == 0 or n != next_syll.shape[0] or n != stim_bin.shape[0]:
        raise ValueError("cur_syll, next_syll, stim_bin must be equal-length, non-empty")

    j_cs = _joint_counts(cur_syll, stim_bin)
    j_cn = _joint_counts(cur_syll, next_syll)
    j_csn = _triple_counts(cur_syll, stim_bin, next_syll)

    h_cs = _entropy_bits(j_cs.ravel())
    h_cn = _entropy_bits(j_cn.ravel())
    h_c = _entropy_bits(j_cs.sum(axis=1))
    h_csn = _entropy_bits(j_csn.ravel())
    mi_raw = h_cs + h_cn - h_c - h_csn

    k_cs = int((j_cs > 0).sum())
    k_cn = int((j_cn > 0).sum())
    k_c = int((j_cs.sum(axis=1) > 0).sum())
    k_csn = int((j_csn > 0).sum())
    mm_adjust = _mm_term_bits(k_cs, n) + _mm_term_bits(k_cn, n) - _mm_term_bits(k_c, n) - _mm_term_bits(k_csn, n)
    mi_mm = mi_raw + mm_adjust

    j_n = _joint_counts(next_syll, stim_bin)
    h_next = _entropy_bits(j_n.sum(axis=1))
    h_stim = _entropy_bits(j_n.sum(axis=0))
    return mi_raw, mi_mm, h_next, h_stim, n


def global_quantile_bin_edges(values: Sequence[float], n_bins: int) -> np.ndarray:
    """Fixed cohort quantile edges (``n_bins`` bins -> ``n_bins + 1`` edges)."""
    arr = np.asarray(values, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        raise ValueError("no finite values for quantile bin edges")
    if n_bins < 2:
        raise ValueError("n_bins must be >= 2")
    qs = np.linspace(0.0, 1.0, n_bins + 1)
    edges = np.quantile(finite, qs)
    edges[0] = -np.inf
    edges[-1] = np.inf
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + 1e-9
    return edges


def assign_bins(values: Sequence[float], edges: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    finite = np.isfinite(arr)
    out = np.full(arr.shape, -1, dtype=np.int64)
    if not np.any(finite):
        return out
    out[finite] = np.digitize(arr[finite], edges[1:-1], right=False)
    return out


def _stim_values_for_var(rows: Sequence[Mapping[str, str]], stim_var: StimVar) -> list[float]:
    field = "bout_mean_duty" if stim_var == "duty" else "bout_mean_dist_px"
    out: list[float] = []
    for row in rows:
        raw = str(row.get(field, "")).strip()
        if not raw:
            continue
        val = float(raw)
        if np.isfinite(val):
            out.append(val)
    return out


def compute_global_bin_edges(
    rows: Sequence[Mapping[str, str]],
    *,
    n_bins: int = 4,
) -> StimulusBinEdges:
    """Quantile edges from run-phase bouts across the filtered cohort."""
    run_rows = bout_rows_for_phase(rows, "run")
    duty_vals = _stim_values_for_var(run_rows, "duty")
    dist_vals = _stim_values_for_var(run_rows, "dist")
    if not duty_vals or not dist_vals:
        raise ValueError("insufficient run-phase stimulus values for global bin edges")
    return StimulusBinEdges(
        duty=global_quantile_bin_edges(duty_vals, n_bins),
        dist=global_quantile_bin_edges(dist_vals, n_bins),
        n_bins=n_bins,
    )


def bin_edges_to_dict(edges: StimulusBinEdges) -> dict[str, object]:
    return {
        "n_bins": edges.n_bins,
        "duty_edges": [float(x) for x in edges.duty],
        "dist_edges": [float(x) for x in edges.dist],
    }


def write_bin_edges_json(path: Path | str, edges: StimulusBinEdges) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(bin_edges_to_dict(edges), f, indent=2)


def load_bin_edges_json(path: Path | str) -> StimulusBinEdges:
    with Path(path).open(encoding="utf-8") as f:
        payload = json.load(f)
    return StimulusBinEdges(
        duty=np.asarray(payload["duty_edges"], dtype=np.float64),
        dist=np.asarray(payload["dist_edges"], dtype=np.float64),
        n_bins=int(payload["n_bins"]),
    )


def _trial_streams(
    rows: Sequence[Mapping[str, str]],
    *,
    stim_var: StimVar,
    edges: StimulusBinEdges,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    field = "bout_mean_duty" if stim_var == "duty" else "bout_mean_dist_px"
    edge_arr = edges.duty if stim_var == "duty" else edges.dist
    by_trial: dict[str, list[tuple[int, int, float]]] = defaultdict(list)
    for row in rows:
        trial = str(row["trial_key"])
        bout_index = int(row["bout_index"])
        raw = str(row.get(field, "")).strip()
        if not raw:
            continue
        val = float(raw)
        if not np.isfinite(val):
            continue
        by_trial[trial].append((bout_index, int(row["raw_syllable_id"]), val))

    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for trial, items in by_trial.items():
        items.sort(key=lambda x: x[0])
        stim_vals = [v for _, _, v in items]
        stim_bin = assign_bins(stim_vals, edge_arr)
        syll = np.asarray([sid for _, sid, _ in items], dtype=np.int64)
        out[trial] = (syll, stim_bin)
    return out


def _pooled_occupancy_mi(trial_streams: dict[str, tuple[np.ndarray, np.ndarray]]) -> tuple[float, float, float, float, int]:
    syll_parts: list[np.ndarray] = []
    stim_parts: list[np.ndarray] = []
    for syll, stim in trial_streams.values():
        mask = stim >= 0
        if not np.any(mask):
            continue
        syll_parts.append(syll[mask])
        stim_parts.append(stim[mask])
    if not syll_parts:
        return 0.0, 0.0, 0.0, 0.0, 0
    syll_all = np.concatenate(syll_parts)
    stim_all = np.concatenate(stim_parts)
    return occupancy_mi(syll_all, stim_all)


def _null_p_value(observed: float, nulls: np.ndarray) -> float:
    if nulls.size == 0:
        return float("nan")
    return float((np.sum(nulls >= observed) + 1) / (nulls.size + 1))


def _circular_shift_amount(size: int, rng: np.random.Generator) -> int:
    if size <= 1:
        return 0
    return int(rng.integers(1, size))


def _circular_shift_trial_streams(
    trial_streams: dict[str, tuple[np.ndarray, np.ndarray]],
    rng: np.random.Generator,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    shifted: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for trial, (syll, stim) in trial_streams.items():
        if stim.size == 0:
            continue
        k = _circular_shift_amount(stim.size, rng)
        shifted[trial] = (syll, np.roll(stim, k))
    return shifted


def _permute_trial_streams(
    trial_streams: dict[str, tuple[np.ndarray, np.ndarray]],
    rng: np.random.Generator,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    permuted: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for trial, (syll, stim) in trial_streams.items():
        if stim.size == 0:
            continue
        perm = stim.copy()
        rng.shuffle(perm)
        permuted[trial] = (syll, perm)
    return permuted


def _compute_nulls_occupancy(
    trial_streams: dict[str, tuple[np.ndarray, np.ndarray]],
    *,
    observed_mm: float,
    n_perm: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    circ: list[float] = []
    perm: list[float] = []
    for _ in range(n_perm):
        _, mm_c, _, _, _ = _pooled_occupancy_mi(_circular_shift_trial_streams(trial_streams, rng))
        circ.append(mm_c)
        _, mm_p, _, _, _ = _pooled_occupancy_mi(_permute_trial_streams(trial_streams, rng))
        perm.append(mm_p)
    circ_arr = np.asarray(circ, dtype=np.float64)
    perm_arr = np.asarray(perm, dtype=np.float64)
    return float(np.mean(circ_arr)), _null_p_value(observed_mm, circ_arr), float(np.mean(perm_arr)), _null_p_value(
        observed_mm, perm_arr
    )


def _transition_trial_streams(
    rows: Sequence[Mapping[str, str]],
    *,
    stim_var: StimVar,
    edges: StimulusBinEdges,
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    field = "bout_mean_duty" if stim_var == "duty" else "bout_mean_dist_px"
    edge_arr = edges.duty if stim_var == "duty" else edges.dist
    by_trial: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        raw = str(row.get(field, "")).strip()
        if not raw or not np.isfinite(float(raw)):
            continue
        by_trial[str(row["trial_key"])].append(dict(row))

    out: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for trial, trial_rows in by_trial.items():
        trial_rows.sort(key=lambda r: int(r["bout_index"]))
        if len(trial_rows) < 2:
            continue
        cur: list[int] = []
        nxt: list[int] = []
        stim: list[int] = []
        for left, right in zip(trial_rows, trial_rows[1:], strict=False):
            stim_bin = int(assign_bins([float(left[field])], edge_arr)[0])
            if stim_bin < 0:
                continue
            cur.append(int(left["raw_syllable_id"]))
            nxt.append(int(right["raw_syllable_id"]))
            stim.append(stim_bin)
        if cur:
            out[trial] = (
                np.asarray(cur, dtype=np.int64),
                np.asarray(nxt, dtype=np.int64),
                np.asarray(stim, dtype=np.int64),
            )
    return out


def _pooled_transition_from_streams(
    streams: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
) -> tuple[float, float, float, float, int]:
    cur_parts: list[np.ndarray] = []
    next_parts: list[np.ndarray] = []
    stim_parts: list[np.ndarray] = []
    for cur, nxt, stim in streams.values():
        cur_parts.append(cur)
        next_parts.append(nxt)
        stim_parts.append(stim)
    if not cur_parts:
        return 0.0, 0.0, 0.0, 0.0, 0
    return transition_mi(
        np.concatenate(cur_parts),
        np.concatenate(next_parts),
        np.concatenate(stim_parts),
    )


def _compute_nulls_transition(
    streams: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    *,
    observed_mm: float,
    n_perm: int,
    rng: np.random.Generator,
) -> tuple[float, float, float, float]:
    circ: list[float] = []
    perm: list[float] = []
    for _ in range(n_perm):
        shifted: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for trial, (cur, nxt, stim) in streams.items():
            if stim.size == 0:
                continue
            k = _circular_shift_amount(stim.size, rng)
            shifted[trial] = (cur, nxt, np.roll(stim, k))
        _, mm_c, _, _, _ = _pooled_transition_from_streams(shifted)
        circ.append(mm_c)

        permuted: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for trial, (cur, nxt, stim) in streams.items():
            if stim.size == 0:
                continue
            shuffled = stim.copy()
            rng.shuffle(shuffled)
            permuted[trial] = (cur, nxt, shuffled)
        _, mm_p, _, _, _ = _pooled_transition_from_streams(permuted)
        perm.append(mm_p)
    circ_arr = np.asarray(circ, dtype=np.float64)
    perm_arr = np.asarray(perm, dtype=np.float64)
    return (
        float(np.mean(circ_arr)),
        _null_p_value(observed_mm, circ_arr),
        float(np.mean(perm_arr)),
        _null_p_value(observed_mm, perm_arr),
    )


def compute_animal_mi(
    rows: Sequence[Mapping[str, str]],
    *,
    edges: StimulusBinEdges,
    n_perm: int = 1000,
    rng: np.random.Generator | None = None,
) -> list[AnimalMiResult]:
    """Compute per-animal MI rows for all phase × stim_var × mi_type combinations."""
    gen = rng if rng is not None else np.random.default_rng(0)
    by_animal: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_animal[str(row.get("animal_id", ""))].append(dict(row))

    results: list[AnimalMiResult] = []
    for animal_id, animal_rows in sorted(by_animal.items()):
        if not animal_id:
            continue
        sex = str(animal_rows[0].get("sex", ""))
        strain = str(animal_rows[0].get("strain", ""))
        tx = str(animal_rows[0].get("tx", ""))
        for phase in STIM_PHASES:
            phase_rows = [r for r in animal_rows if bout_in_phase(str(r.get("bout_primary_state", "")), phase)]  # type: ignore[arg-type]
            if not phase_rows:
                continue
            for stim_var in STIM_VARS:
                stim_key: StimVar = stim_var  # type: ignore[assignment]
                for mi_type in MI_TYPES:
                    mi_key: MiType = mi_type  # type: ignore[assignment]
                    if mi_key == "occupancy":
                        streams = _trial_streams(phase_rows, stim_var=stim_key, edges=edges)
                        mi_raw, mi_mm, h_syll, h_stim, n_bouts = _pooled_occupancy_mi(streams)
                        if n_bouts == 0:
                            continue
                        null_circ_mean, null_circ_p, null_perm_mean, null_perm_p = _compute_nulls_occupancy(
                            streams, observed_mm=mi_mm, n_perm=n_perm, rng=gen
                        )
                    else:
                        streams_t = _transition_trial_streams(phase_rows, stim_var=stim_key, edges=edges)
                        mi_raw, mi_mm, h_syll, h_stim, n_bouts = _pooled_transition_from_streams(streams_t)
                        if n_bouts == 0:
                            continue
                        null_circ_mean, null_circ_p, null_perm_mean, null_perm_p = _compute_nulls_transition(
                            streams_t, observed_mm=mi_mm, n_perm=n_perm, rng=gen
                        )
                    iti_flag = 0
                    if phase == "iti" and np.isfinite(null_circ_p) and mi_mm > null_circ_mean and null_circ_p < 0.05:
                        iti_flag = 1
                    results.append(
                        AnimalMiResult(
                            animal_id=animal_id,
                            sex=sex,
                            strain=strain,
                            tx=tx,
                            phase=phase,
                            stim_var=stim_var,
                            mi_type=mi_type,
                            n_bouts=n_bouts,
                            H_stim=h_stim,
                            H_syll=h_syll,
                            mi_raw=mi_raw,
                            mi_mm=mi_mm,
                            null_circ_mean=null_circ_mean,
                            null_circ_p=null_circ_p,
                            null_perm_mean=null_perm_mean,
                            null_perm_p=null_perm_p,
                            iti_control_flag=iti_flag,
                        )
                    )
    return results


def animal_mi_to_row(result: AnimalMiResult) -> dict[str, object]:
    return {
        "animal_id": result.animal_id,
        "sex": result.sex,
        "strain": result.strain,
        "tx": result.tx,
        "phase": result.phase,
        "stim_var": result.stim_var,
        "mi_type": result.mi_type,
        "n_bouts": result.n_bouts,
        "H_stim": result.H_stim,
        "H_syll": result.H_syll,
        "mi_raw": result.mi_raw,
        "mi_mm": result.mi_mm,
        "null_circ_mean": result.null_circ_mean,
        "null_circ_p": result.null_circ_p,
        "null_perm_mean": result.null_perm_mean,
        "null_perm_p": result.null_perm_p,
        "iti_control_flag": result.iti_control_flag,
    }


def write_mi_per_animal_csv(path: Path | str, rows: Sequence[AnimalMiResult | Mapping[str, object]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(MI_PER_ANIMAL_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            if isinstance(row, AnimalMiResult):
                writer.writerow(animal_mi_to_row(row))
            else:
                writer.writerow(row)


def read_mi_per_animal_csv(path: Path | str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _factor_value(row: Mapping[str, str], factor: str) -> str:
    if factor == "genotype":
        return str(row.get("strain", "")).strip()
    return str(row.get(factor, "")).strip()


def run_group_mi_tests(mi_rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    """Mann-Whitney (2 levels) or Kruskal (>2) on per-animal ``mi_mm`` distributions."""
    grouped: dict[tuple[str, str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in mi_rows:
        key = (str(row["phase"]), str(row["stim_var"]), str(row["mi_type"]))
        grouped[key].append(row)

    out: list[dict[str, object]] = []
    for (phase, stim_var, mi_type), subset in sorted(grouped.items()):
        for factor in GROUP_FACTORS:
            by_level: dict[str, list[float]] = defaultdict(list)
            for row in subset:
                level = _factor_value(row, factor)
                if not level:
                    continue
                val = float(row["mi_mm"])
                if not np.isfinite(val):
                    continue
                by_level[level].append(val)
            levels = sorted(by_level)
            if len(levels) < 2:
                continue
            if len(levels) == 2:
                a, b = levels
                vals_a = by_level[a]
                vals_b = by_level[b]
                stat, p = stats.mannwhitneyu(vals_a, vals_b, alternative="two-sided")
                out.append(
                    {
                        "factor": factor,
                        "level_a": a,
                        "level_b": b,
                        "phase": phase,
                        "stim_var": stim_var,
                        "mi_type": mi_type,
                        "n_a": len(vals_a),
                        "n_b": len(vals_b),
                        "median_a": float(np.median(vals_a)),
                        "median_b": float(np.median(vals_b)),
                        "stat": float(stat),
                        "p": float(p),
                        "test": "mannwhitneyu",
                    }
                )
            else:
                samples = [by_level[level] for level in levels]
                stat, p = stats.kruskal(*samples)
                all_vals = [v for s in samples for v in s]
                out.append(
                    {
                        "factor": factor,
                        "level_a": "(all)",
                        "level_b": "",
                        "phase": phase,
                        "stim_var": stim_var,
                        "mi_type": mi_type,
                        "n_a": len(all_vals),
                        "n_b": 0,
                        "median_a": float(np.median(all_vals)),
                        "median_b": float("nan"),
                        "stat": float(stat),
                        "p": float(p),
                        "test": "kruskal",
                    }
                )
    return out


def write_group_mi_tests_csv(path: Path | str, rows: Sequence[Mapping[str, object]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(GROUP_MI_TEST_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


_ORD_SUFFIX_RE = re.compile(r"(\d+)\s*$")


def parse_ordinal_suffix(label: str) -> int:
    """Parse trailing digits from session/trial labels (e.g. ``S01`` -> 1)."""
    text = str(label).strip()
    match = _ORD_SUFFIX_RE.search(text)
    if not match:
        raise ValueError(f"cannot parse ordinal suffix from {label!r}")
    return int(match.group(1))


@dataclass(frozen=True)
class TrialOrderEntry:
    trial_key: str
    session: str
    trial: str
    trial_ord: int


def trial_order_for_animal(rows: Sequence[Mapping[str, str]]) -> list[TrialOrderEntry]:
    """Chronological trial order within one animal from session/trial suffixes."""
    seen: dict[str, tuple[str, str]] = {}
    for row in rows:
        trial_key = str(row["trial_key"])
        if trial_key in seen:
            continue
        seen[trial_key] = (str(row.get("session", "")), str(row.get("trial", "")))

    sortable: list[tuple[int, int, str, str, str]] = []
    for trial_key, (session, trial) in seen.items():
        session_ord = parse_ordinal_suffix(session)
        trial_ord_suffix = parse_ordinal_suffix(trial)
        sortable.append((session_ord, trial_ord_suffix, trial_key, session, trial))
    sortable.sort()

    return [
        TrialOrderEntry(
            trial_key=trial_key,
            session=session,
            trial=trial,
            trial_ord=idx,
        )
        for idx, (_, _, trial_key, session, trial) in enumerate(sortable)
    ]


def cum_run_bouts_for_animal(
    rows: Sequence[Mapping[str, str]],
    trial_order: Sequence[TrialOrderEntry],
) -> dict[str, int]:
    """Running sum of run-phase bouts through each trial (inclusive)."""
    run_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if not bout_in_phase(str(row.get("bout_primary_state", "")), "run"):
            continue
        run_counts[str(row["trial_key"])] += 1

    cumulative: dict[str, int] = {}
    total = 0
    for entry in trial_order:
        total += run_counts.get(entry.trial_key, 0)
        cumulative[entry.trial_key] = total
    return cumulative


@dataclass(frozen=True)
class TrialMiResult:
    animal_id: str
    sex: str
    strain: str
    tx: str
    session: str
    trial: str
    trial_key: str
    trial_ord: int
    cum_run_bouts: int
    phase: str
    stim_var: str
    mi_type: str
    n_bouts: int
    H_stim: float
    H_syll: float
    mi_raw: float
    mi_mm: float
    null_circ_mean: float
    null_circ_p: float
    excess: float


def _single_trial_occupancy_mi(
    streams: dict[str, tuple[np.ndarray, np.ndarray]],
    trial_key: str,
) -> tuple[float, float, float, float, int]:
    if trial_key not in streams:
        return 0.0, 0.0, 0.0, 0.0, 0
    syll, stim = streams[trial_key]
    mask = stim >= 0
    if not np.any(mask):
        return 0.0, 0.0, 0.0, 0.0, 0
    return occupancy_mi(syll[mask], stim[mask])


def _single_trial_transition_mi(
    streams: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    trial_key: str,
) -> tuple[float, float, float, float, int]:
    if trial_key not in streams:
        return 0.0, 0.0, 0.0, 0.0, 0
    cur, nxt, stim = streams[trial_key]
    if cur.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 0
    return transition_mi(cur, nxt, stim)


def _trial_circular_null_occupancy(
    syll: np.ndarray,
    stim: np.ndarray,
    *,
    observed_mm: float,
    n_perm: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    if stim.size == 0:
        return float("nan"), float("nan")
    single = {"_": (syll, stim)}
    nulls: list[float] = []
    for _ in range(n_perm):
        _, mm_c, _, _, _ = _pooled_occupancy_mi(_circular_shift_trial_streams(single, rng))
        nulls.append(mm_c)
    null_arr = np.asarray(nulls, dtype=np.float64)
    return float(np.mean(null_arr)), _null_p_value(observed_mm, null_arr)


def _trial_circular_null_transition(
    cur: np.ndarray,
    nxt: np.ndarray,
    stim: np.ndarray,
    *,
    observed_mm: float,
    n_perm: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    if stim.size == 0:
        return float("nan"), float("nan")
    single = {"_": (cur, nxt, stim)}
    nulls: list[float] = []
    for _ in range(n_perm):
        shifted: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for _trial, (c, nx, st) in single.items():
            k = _circular_shift_amount(st.size, rng)
            shifted[_trial] = (c, nx, np.roll(st, k))
        _, mm_c, _, _, _ = _pooled_transition_from_streams(shifted)
        nulls.append(mm_c)
    null_arr = np.asarray(nulls, dtype=np.float64)
    return float(np.mean(null_arr)), _null_p_value(observed_mm, null_arr)


def _trial_passes_gates(
    *,
    n_bouts: int,
    h_stim: float,
    cum_run_bouts: int,
    min_run_bouts: int | None,
    min_h_stim: float | None,
) -> bool:
    if min_run_bouts is not None and cum_run_bouts < min_run_bouts:
        return False
    if min_h_stim is not None and (not np.isfinite(h_stim) or h_stim < min_h_stim):
        return False
    return True


def compute_per_trial_mi(
    rows: Sequence[Mapping[str, str]],
    *,
    edges: StimulusBinEdges,
    trial_nulls: bool = False,
    n_perm: int = TRIAL_NULL_N_PERM,
    min_run_bouts: int | None = None,
    min_h_stim: float | None = None,
    rng: np.random.Generator | None = None,
) -> list[TrialMiResult]:
    """Per-trial MI for full phase × stim_var × mi_type factorial."""
    gen = rng if rng is not None else np.random.default_rng(0)
    by_animal: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_animal[str(row.get("animal_id", ""))].append(dict(row))

    results: list[TrialMiResult] = []
    for animal_id, animal_rows in sorted(by_animal.items()):
        if not animal_id:
            continue
        trial_order = trial_order_for_animal(animal_rows)
        cum_run = cum_run_bouts_for_animal(animal_rows, trial_order)
        sex = str(animal_rows[0].get("sex", ""))
        strain = str(animal_rows[0].get("strain", ""))
        tx = str(animal_rows[0].get("tx", ""))

        for phase in STIM_PHASES:
            phase_rows = [r for r in animal_rows if bout_in_phase(str(r.get("bout_primary_state", "")), phase)]  # type: ignore[arg-type]
            if not phase_rows:
                continue
            for stim_var in STIM_VARS:
                stim_key: StimVar = stim_var  # type: ignore[assignment]
                occ_streams = _trial_streams(phase_rows, stim_var=stim_key, edges=edges)
                trans_streams = _transition_trial_streams(phase_rows, stim_var=stim_key, edges=edges)
                for mi_type in MI_TYPES:
                    mi_key: MiType = mi_type  # type: ignore[assignment]
                    for entry in trial_order:
                        cum_bouts = cum_run[entry.trial_key]
                        if mi_key == "occupancy":
                            mi_raw, mi_mm, h_syll, h_stim, n_bouts = _single_trial_occupancy_mi(
                                occ_streams, entry.trial_key
                            )
                        else:
                            mi_raw, mi_mm, h_syll, h_stim, n_bouts = _single_trial_transition_mi(
                                trans_streams, entry.trial_key
                            )
                        if n_bouts == 0:
                            continue
                        if not _trial_passes_gates(
                            n_bouts=n_bouts,
                            h_stim=h_stim,
                            cum_run_bouts=cum_bouts,
                            min_run_bouts=min_run_bouts,
                            min_h_stim=min_h_stim,
                        ):
                            continue

                        null_circ_mean = float("nan")
                        null_circ_p = float("nan")
                        excess = float("nan")
                        if trial_nulls:
                            if mi_key == "occupancy":
                                syll, stim = occ_streams[entry.trial_key]
                                mask = stim >= 0
                                null_circ_mean, null_circ_p = _trial_circular_null_occupancy(
                                    syll[mask],
                                    stim[mask],
                                    observed_mm=mi_mm,
                                    n_perm=n_perm,
                                    rng=gen,
                                )
                            else:
                                cur, nxt, stim = trans_streams[entry.trial_key]
                                null_circ_mean, null_circ_p = _trial_circular_null_transition(
                                    cur,
                                    nxt,
                                    stim,
                                    observed_mm=mi_mm,
                                    n_perm=n_perm,
                                    rng=gen,
                                )
                            if np.isfinite(null_circ_mean):
                                excess = mi_mm - null_circ_mean

                        results.append(
                            TrialMiResult(
                                animal_id=animal_id,
                                sex=sex,
                                strain=strain,
                                tx=tx,
                                session=entry.session,
                                trial=entry.trial,
                                trial_key=entry.trial_key,
                                trial_ord=entry.trial_ord,
                                cum_run_bouts=cum_bouts,
                                phase=phase,
                                stim_var=stim_var,
                                mi_type=mi_type,
                                n_bouts=n_bouts,
                                H_stim=h_stim,
                                H_syll=h_syll,
                                mi_raw=mi_raw,
                                mi_mm=mi_mm,
                                null_circ_mean=null_circ_mean,
                                null_circ_p=null_circ_p,
                                excess=excess,
                            )
                        )
    return results


def trial_mi_to_row(result: TrialMiResult) -> dict[str, object]:
    return {
        "animal_id": result.animal_id,
        "sex": result.sex,
        "strain": result.strain,
        "tx": result.tx,
        "session": result.session,
        "trial": result.trial,
        "trial_key": result.trial_key,
        "trial_ord": result.trial_ord,
        "cum_run_bouts": result.cum_run_bouts,
        "phase": result.phase,
        "stim_var": result.stim_var,
        "mi_type": result.mi_type,
        "n_bouts": result.n_bouts,
        "H_stim": result.H_stim,
        "H_syll": result.H_syll,
        "mi_raw": result.mi_raw,
        "mi_mm": result.mi_mm,
        "null_circ_mean": result.null_circ_mean,
        "null_circ_p": result.null_circ_p,
        "excess": result.excess,
    }


def write_mi_per_trial_csv(path: Path | str, rows: Sequence[TrialMiResult | Mapping[str, object]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(MI_PER_TRIAL_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            if isinstance(row, TrialMiResult):
                writer.writerow(trial_mi_to_row(row))
            else:
                writer.writerow(row)


def _ols_slope(x: Sequence[float], y: Sequence[float]) -> float:
    if len(x) < 2 or len(y) < 2:
        return float("nan")
    x_arr = np.asarray(x, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)
    mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    if mask.sum() < 2:
        return float("nan")
    slope, _, _, _, _ = stats.linregress(x_arr[mask], y_arr[mask])
    return float(slope)


def _early_late_delta(
    trial_ord: Sequence[float],
    values: Sequence[float],
    *,
    k: int = EARLY_LATE_K,
    min_trials: int = MIN_TRIALS_FOR_EARLY_LATE,
) -> float:
    pairs = [
        (float(t), float(v))
        for t, v in zip(trial_ord, values, strict=False)
        if np.isfinite(t) and np.isfinite(v)
    ]
    if len(pairs) < min_trials:
        return float("nan")
    pairs.sort(key=lambda item: item[0])
    early_vals = [v for _, v in pairs[:k]]
    late_vals = [v for _, v in pairs[-k:]]
    return float(np.mean(early_vals) - np.mean(late_vals))


@dataclass(frozen=True)
class TrialAnimalSummary:
    animal_id: str
    sex: str
    strain: str
    tx: str
    phase: str
    stim_var: str
    mi_type: str
    n_trials: int
    mean_mi_mm: float
    median_mi_mm: float
    mean_n_bouts: float
    mean_H_stim: float
    slope_vs_trial_ord: float
    early_late_delta: float
    slope_vs_excess: float
    early_late_delta_excess: float
    null_clear_fraction: float


def compute_trial_animal_summaries(
    trial_rows: Sequence[TrialMiResult],
    *,
    trial_nulls: bool = False,
) -> list[TrialAnimalSummary]:
    """Animal-level slope and early−late delta from per-trial MI trajectories."""
    grouped: dict[tuple[str, str, str, str, str, str, str], list[TrialMiResult]] = defaultdict(list)
    for row in trial_rows:
        key = (row.animal_id, row.sex, row.strain, row.tx, row.phase, row.stim_var, row.mi_type)
        grouped[key].append(row)

    summaries: list[TrialAnimalSummary] = []
    for (animal_id, sex, strain, tx, phase, stim_var, mi_type), subset in sorted(grouped.items()):
        subset_sorted = sorted(subset, key=lambda r: r.trial_ord)
        trial_ords = [float(r.trial_ord) for r in subset_sorted]
        mi_vals = [r.mi_mm for r in subset_sorted]
        excess_vals = [r.excess for r in subset_sorted]
        null_ps = [r.null_circ_p for r in subset_sorted]

        null_clear_fraction = float("nan")
        if trial_nulls:
            finite_ps = [p for p in null_ps if np.isfinite(p)]
            if finite_ps:
                null_clear_fraction = float(np.mean([p < NULL_CLEAR_ALPHA for p in finite_ps]))

        slope_excess = float("nan")
        delta_excess = float("nan")
        if trial_nulls:
            slope_excess = _ols_slope(trial_ords, excess_vals)
            delta_excess = _early_late_delta(trial_ords, excess_vals)

        summaries.append(
            TrialAnimalSummary(
                animal_id=animal_id,
                sex=sex,
                strain=strain,
                tx=tx,
                phase=phase,
                stim_var=stim_var,
                mi_type=mi_type,
                n_trials=len(subset_sorted),
                mean_mi_mm=float(np.mean(mi_vals)) if mi_vals else float("nan"),
                median_mi_mm=float(np.median(mi_vals)) if mi_vals else float("nan"),
                mean_n_bouts=float(np.mean([r.n_bouts for r in subset_sorted])) if subset_sorted else float("nan"),
                mean_H_stim=float(np.mean([r.H_stim for r in subset_sorted])) if subset_sorted else float("nan"),
                slope_vs_trial_ord=_ols_slope(trial_ords, mi_vals),
                early_late_delta=_early_late_delta(trial_ords, mi_vals),
                slope_vs_excess=slope_excess,
                early_late_delta_excess=delta_excess,
                null_clear_fraction=null_clear_fraction,
            )
        )
    return summaries


def trial_animal_summary_to_row(summary: TrialAnimalSummary) -> dict[str, object]:
    return {
        "animal_id": summary.animal_id,
        "sex": summary.sex,
        "strain": summary.strain,
        "tx": summary.tx,
        "phase": summary.phase,
        "stim_var": summary.stim_var,
        "mi_type": summary.mi_type,
        "n_trials": summary.n_trials,
        "mean_mi_mm": summary.mean_mi_mm,
        "median_mi_mm": summary.median_mi_mm,
        "mean_n_bouts": summary.mean_n_bouts,
        "mean_H_stim": summary.mean_H_stim,
        "slope_vs_trial_ord": summary.slope_vs_trial_ord,
        "early_late_delta": summary.early_late_delta,
        "slope_vs_excess": summary.slope_vs_excess,
        "early_late_delta_excess": summary.early_late_delta_excess,
        "null_clear_fraction": summary.null_clear_fraction,
    }


def write_mi_trial_animal_summaries_csv(
    path: Path | str,
    rows: Sequence[TrialAnimalSummary | Mapping[str, object]],
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(MI_TRIAL_ANIMAL_SUMMARY_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            if isinstance(row, TrialAnimalSummary):
                writer.writerow(trial_animal_summary_to_row(row))
            else:
                writer.writerow(row)


def _is_primary_when_cell(phase: str, stim_var: str, mi_type: str) -> bool:
    return phase == PRIMARY_WHEN_PHASE and stim_var in STIM_VARS and mi_type == PRIMARY_WHEN_MI_TYPE


def _active_when_metrics(trial_nulls: bool) -> tuple[str, ...]:
    if trial_nulls:
        return WHEN_TEST_METRICS
    return ("slope_vs_trial_ord", "early_late_delta")


def run_group_mi_when_tests(
    summary_rows: Sequence[Mapping[str, object]],
    *,
    trial_nulls: bool = False,
) -> list[dict[str, object]]:
    """Mann-Whitney/Kruskal on animal-level when metrics (primary cells only)."""
    metrics = _active_when_metrics(trial_nulls)
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in summary_rows:
        phase = str(row["phase"])
        stim_var = str(row["stim_var"])
        mi_type = str(row["mi_type"])
        if not _is_primary_when_cell(phase, stim_var, mi_type):
            continue
        key = (phase, stim_var, mi_type)
        grouped[key].append(row)

    out: list[dict[str, object]] = []
    for (phase, stim_var, mi_type), subset in sorted(grouped.items()):
        for metric in metrics:
            for factor in GROUP_FACTORS:
                by_level: dict[str, list[float]] = defaultdict(list)
                for row in subset:
                    level = _factor_value(row, factor)
                    if not level:
                        continue
                    val = float(row[metric])
                    if not np.isfinite(val):
                        continue
                    by_level[level].append(val)
                levels = sorted(by_level)
                if len(levels) < 2:
                    continue
                if len(levels) == 2:
                    a, b = levels
                    vals_a = by_level[a]
                    vals_b = by_level[b]
                    stat, p = stats.mannwhitneyu(vals_a, vals_b, alternative="two-sided")
                    out.append(
                        {
                            "factor": factor,
                            "level_a": a,
                            "level_b": b,
                            "phase": phase,
                            "stim_var": stim_var,
                            "mi_type": mi_type,
                            "metric": metric,
                            "n_a": len(vals_a),
                            "n_b": len(vals_b),
                            "median_a": float(np.median(vals_a)),
                            "median_b": float(np.median(vals_b)),
                            "stat": float(stat),
                            "p": float(p),
                            "test": "mannwhitneyu",
                        }
                    )
                else:
                    samples = [by_level[level] for level in levels]
                    stat, p = stats.kruskal(*samples)
                    all_vals = [v for s in samples for v in s]
                    out.append(
                        {
                            "factor": factor,
                            "level_a": "(all)",
                            "level_b": "",
                            "phase": phase,
                            "stim_var": stim_var,
                            "mi_type": mi_type,
                            "metric": metric,
                            "n_a": len(all_vals),
                            "n_b": 0,
                            "median_a": float(np.median(all_vals)),
                            "median_b": float("nan"),
                            "stat": float(stat),
                            "p": float(p),
                            "test": "kruskal",
                        }
                    )
    return out


def write_group_mi_when_tests_csv(path: Path | str, rows: Sequence[Mapping[str, object]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(GROUP_MI_WHEN_TEST_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
