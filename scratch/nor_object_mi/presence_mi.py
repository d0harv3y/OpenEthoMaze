"""Object-presence MI: excess_I(dist_any) on identical_obj vs no_obj."""

from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

import numpy as np
from scipy import stats

from maze.kpms.behavior_ethogram.stimulus_mi import (
    assign_bins,
    global_quantile_bin_edges,
    occupancy_mi,
)

PRESENCE_CONDITIONS: tuple[str, ...] = ("identical_obj", "no_obj")
_FIELD = "bout_mean_dist_any_m"


def _json_edges(edges: np.ndarray) -> list[object]:
    return [None if not np.isfinite(e) else float(e) for e in edges]


def fit_dist_any_bin_edges(
    rows: Sequence[Mapping[str, object]],
    *,
    n_bins: int = 5,
) -> tuple[np.ndarray, dict[str, object]]:
    vals: list[float] = []
    by_cond: dict[str, int] = defaultdict(int)
    for r in rows:
        cond = str(r.get("condition_layer", ""))
        if cond not in PRESENCE_CONDITIONS:
            continue
        by_cond[cond] += 1
        val = float(r[_FIELD])
        if np.isfinite(val):
            vals.append(val)
    edges = global_quantile_bin_edges(vals, n_bins)
    payload: dict[str, object] = {
        "dist_any": _json_edges(edges),
        "fit": {
            "policy": "shared_dist_any_presence",
            "source_field": _FIELD,
            "condition_layers": list(PRESENCE_CONDITIONS),
            "n_bout_rows_by_condition": dict(by_cond),
            "n_bins": n_bins,
            "n_values": len(vals),
            "dist_any_def": "bout-mean nearest of two loci (real objects or animal×phase pseudo-loci)",
        },
    }
    return edges, payload


def edges_from_payload(payload: Mapping[str, object]) -> np.ndarray:
    raw = list(payload["dist_any"])  # type: ignore[arg-type]
    edges = np.asarray(
        [-np.inf if (v is None or v == "-inf") else (np.inf if v == "inf" else float(v)) for v in raw],
        dtype=np.float64,
    )
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def _circular_shift_amount(size: int, rng: np.random.Generator) -> int:
    if size <= 1:
        return 0
    return int(rng.integers(1, size))


def _null_p(observed: float, nulls: np.ndarray) -> float:
    if nulls.size == 0:
        return float("nan")
    return float((np.sum(nulls >= observed) + 1) / (nulls.size + 1))


def _pooled_occupancy(streams: dict[str, tuple[np.ndarray, np.ndarray]]) -> tuple[float, float, float, float, int]:
    syll_parts: list[np.ndarray] = []
    stim_parts: list[np.ndarray] = []
    for syll, stim in streams.values():
        mask = stim >= 0
        if not np.any(mask):
            continue
        syll_parts.append(syll[mask])
        stim_parts.append(stim[mask])
    if not syll_parts:
        return 0.0, 0.0, 0.0, 0.0, 0
    return occupancy_mi(np.concatenate(syll_parts), np.concatenate(stim_parts))


def _null_circ(
    streams: dict[str, tuple[np.ndarray, np.ndarray]],
    *,
    observed_mm: float,
    n_perm: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    nulls: list[float] = []
    for _ in range(n_perm):
        shifted: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for trial, (syll, stim) in streams.items():
            if stim.size == 0:
                continue
            k = _circular_shift_amount(int(stim.size), rng)
            shifted[trial] = (syll, np.roll(stim, k))
        _, mm, _, _, _ = _pooled_occupancy(shifted)
        nulls.append(mm)
    arr = np.asarray(nulls, dtype=np.float64)
    return float(np.mean(arr)), _null_p(observed_mm, arr)


def _streams(
    rows: Sequence[Mapping[str, object]],
    *,
    animal_id: str,
    condition_layer: str,
    edges: np.ndarray,
    field: str = _FIELD,
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    by_trial: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if str(row["animal_id"]) != animal_id:
            continue
        if str(row.get("condition_layer", "")) != condition_layer:
            continue
        val = float(row[field])
        if not np.isfinite(val):
            continue
        by_trial[str(row["trial_key"])].append(row)
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for trial, trows in by_trial.items():
        trows = sorted(trows, key=lambda r: int(r["bout_index"]))
        syll = np.asarray([int(r["raw_syllable_id"]) for r in trows], dtype=np.int64)
        stim_vals = np.asarray([float(r[field]) for r in trows], dtype=np.float64)
        out[trial] = (syll, assign_bins(stim_vals, edges))
    return out


def compute_presence_mi(
    rows: Sequence[Mapping[str, object]],
    *,
    n_bins: int = 5,
    n_perm: int = 200,
    seed: int = 42,
    bin_edges_payload: Mapping[str, object] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Per-animal excess_I(dist_any) for identical_obj vs no_obj; paired Δ_presence."""
    if bin_edges_payload is None:
        edges, bin_edges_payload = fit_dist_any_bin_edges(rows, n_bins=n_bins)
    else:
        edges = edges_from_payload(bin_edges_payload)

    animals = sorted({str(r["animal_id"]) for r in rows})
    meta: dict[str, Mapping[str, object]] = {}
    for r in rows:
        meta.setdefault(str(r["animal_id"]), r)

    rng = np.random.default_rng(seed)
    mi_rows: list[dict[str, object]] = []
    for aid in animals:
        m = meta[aid]
        for cond in PRESENCE_CONDITIONS:
            streams = _streams(rows, animal_id=aid, condition_layer=cond, edges=edges, field=_FIELD)
            if not streams:
                continue
            mi_raw, mi_mm, h_syll, h_stim, n_bouts = _pooled_occupancy(streams)
            if n_bouts == 0:
                continue
            null_mean, null_p = _null_circ(streams, observed_mm=mi_mm, n_perm=n_perm, rng=rng)
            mi_rows.append(
                {
                    "animal_id": aid,
                    "sex": m["sex"],
                    "tx": m["tx"],
                    "cohort": m["cohort"],
                    "phase_layer": m["phase_layer"],
                    "condition_layer": cond,
                    "object_presence": "present" if cond == "identical_obj" else "absent",
                    "stim_var": "dist_any",
                    "locus": "any",
                    "mi_type": "occupancy",
                    "n_bouts": n_bouts,
                    "H_stim": h_stim,
                    "H_syll": h_syll,
                    "mi_raw": mi_raw,
                    "mi_mm": mi_mm,
                    "null_circ_mean": null_mean,
                    "null_circ_p": null_p,
                    "excess": float(mi_mm - null_mean),
                }
            )

    by_animal: dict[str, dict[str, Mapping[str, object]]] = defaultdict(dict)
    for row in mi_rows:
        by_animal[str(row["animal_id"])][str(row["condition_layer"])] = row

    delta_rows: list[dict[str, object]] = []
    for aid, cmap in sorted(by_animal.items()):
        if "identical_obj" not in cmap or "no_obj" not in cmap:
            continue
        present = cmap["identical_obj"]
        absent = cmap["no_obj"]
        delta_rows.append(
            {
                "animal_id": aid,
                "sex": present["sex"],
                "tx": present["tx"],
                "cohort": present["cohort"],
                "phase_layer": present["phase_layer"],
                "locus": "any",
                "excess_present": present["excess"],
                "excess_absent": absent["excess"],
                "delta_excess_present_minus_absent": float(present["excess"]) - float(absent["excess"]),  # type: ignore[arg-type]
                "mi_mm_present": present["mi_mm"],
                "mi_mm_absent": absent["mi_mm"],
                "n_bouts_present": present["n_bouts"],
                "n_bouts_absent": absent["n_bouts"],
            }
        )

    group_tests = _group_tests_presence(delta_rows)
    return mi_rows, delta_rows, group_tests, dict(bin_edges_payload)


LOCUS_FIELDS: tuple[tuple[str, str], ...] = (
    ("a", "bout_mean_dist_locus_a_m"),
    ("b", "bout_mean_dist_locus_b_m"),
)


def compute_presence_loci_mi(
    rows: Sequence[Mapping[str, object]],
    *,
    n_bins: int = 5,
    n_perm: int = 200,
    seed: int = 42,
    bin_edges_payload: Mapping[str, object] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Per-animal×locus excess_I for identical_obj vs no_obj (spatial A/B).

    Also emits the nearest-locus (``dist_any``) rows for side-by-side comparison
    when those bout fields are present.
    """
    if bin_edges_payload is None:
        edges, bin_edges_payload = fit_dist_any_bin_edges(rows, n_bins=n_bins)
    else:
        edges = edges_from_payload(bin_edges_payload)

    animals = sorted({str(r["animal_id"]) for r in rows})
    meta: dict[str, Mapping[str, object]] = {}
    for r in rows:
        meta.setdefault(str(r["animal_id"]), r)

    stims: list[tuple[str, str]] = [("any", _FIELD), *LOCUS_FIELDS]
    rng = np.random.default_rng(seed)
    mi_rows: list[dict[str, object]] = []
    for aid in animals:
        m = meta[aid]
        for locus, field in stims:
            for cond in PRESENCE_CONDITIONS:
                streams = _streams(
                    rows, animal_id=aid, condition_layer=cond, edges=edges, field=field
                )
                if not streams:
                    continue
                mi_raw, mi_mm, h_syll, h_stim, n_bouts = _pooled_occupancy(streams)
                if n_bouts == 0:
                    continue
                null_mean, null_p = _null_circ(streams, observed_mm=mi_mm, n_perm=n_perm, rng=rng)
                mi_rows.append(
                    {
                        "animal_id": aid,
                        "sex": m["sex"],
                        "tx": m["tx"],
                        "cohort": m["cohort"],
                        "phase_layer": m["phase_layer"],
                        "condition_layer": cond,
                        "object_presence": "present" if cond == "identical_obj" else "absent",
                        "stim_var": f"dist_locus_{locus}" if locus != "any" else "dist_any",
                        "locus": locus,
                        "mi_type": "occupancy",
                        "n_bouts": n_bouts,
                        "H_stim": h_stim,
                        "H_syll": h_syll,
                        "mi_raw": mi_raw,
                        "mi_mm": mi_mm,
                        "null_circ_mean": null_mean,
                        "null_circ_p": null_p,
                        "excess": float(mi_mm - null_mean),
                    }
                )

    by_key: dict[tuple[str, str], dict[str, Mapping[str, object]]] = defaultdict(dict)
    for row in mi_rows:
        by_key[(str(row["animal_id"]), str(row["locus"]))][str(row["condition_layer"])] = row

    delta_rows: list[dict[str, object]] = []
    for (aid, locus), cmap in sorted(by_key.items()):
        if "identical_obj" not in cmap or "no_obj" not in cmap:
            continue
        present = cmap["identical_obj"]
        absent = cmap["no_obj"]
        delta_rows.append(
            {
                "animal_id": aid,
                "sex": present["sex"],
                "tx": present["tx"],
                "cohort": present["cohort"],
                "phase_layer": present["phase_layer"],
                "locus": locus,
                "stim_var": present["stim_var"],
                "excess_present": present["excess"],
                "excess_absent": absent["excess"],
                "delta_excess_present_minus_absent": float(present["excess"]) - float(absent["excess"]),  # type: ignore[arg-type]
                "mi_mm_present": present["mi_mm"],
                "mi_mm_absent": absent["mi_mm"],
                "n_bouts_present": present["n_bouts"],
                "n_bouts_absent": absent["n_bouts"],
            }
        )

    group_tests: list[dict[str, object]] = []
    for locus in ("any", "a", "b"):
        sub = [r for r in delta_rows if str(r["locus"]) == locus]
        for t in _group_tests_presence(sub):
            t = dict(t)
            t["locus"] = locus
            group_tests.append(t)

    return mi_rows, delta_rows, group_tests, dict(bin_edges_payload)


def _group_tests_presence(delta_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Wilcoxon on paired Δ; Kruskal/MW on Δ by tx/sex (pooled + sex-stratified)."""
    out: list[dict[str, object]] = []
    deltas = [float(r["delta_excess_present_minus_absent"]) for r in delta_rows if np.isfinite(float(r["delta_excess_present_minus_absent"]))]
    if len(deltas) >= 2:
        # signed-rank: does presence raise excess_I vs absent?
        stat, p = stats.wilcoxon(deltas, alternative="two-sided", zero_method="wilcox")
        out.append(
            {
                "sex_stratum": "all",
                "factor": "presence_paired",
                "level_a": "present-absent",
                "level_b": "0",
                "n_a": len(deltas),
                "n_b": 0,
                "median_a": float(np.median(deltas)),
                "median_b": 0.0,
                "stat": float(stat),
                "p": float(p),
                "test": "wilcoxon_signed_rank",
                "metric": "delta_excess_present_minus_absent",
            }
        )

    def _factor_tests(subset: Sequence[Mapping[str, object]], *, factor: str, sex_stratum: str) -> None:
        by_level: dict[str, list[float]] = defaultdict(list)
        for row in subset:
            level = str(row.get(factor, "") or "")
            if not level:
                continue
            val = float(row["delta_excess_present_minus_absent"])
            if np.isfinite(val):
                by_level[level].append(val)
        levels = sorted(by_level)
        if len(levels) < 2:
            return
        if len(levels) == 2:
            a, b = levels
            va, vb = by_level[a], by_level[b]
            stat, p = stats.mannwhitneyu(va, vb, alternative="two-sided")
            out.append(
                {
                    "sex_stratum": sex_stratum,
                    "factor": factor,
                    "level_a": a,
                    "level_b": b,
                    "n_a": len(va),
                    "n_b": len(vb),
                    "median_a": float(np.median(va)),
                    "median_b": float(np.median(vb)),
                    "stat": float(stat),
                    "p": float(p),
                    "test": "mannwhitneyu",
                    "metric": "delta_excess_present_minus_absent",
                }
            )
            return
        samples = [by_level[level] for level in levels]
        stat, p = stats.kruskal(*samples)
        all_vals = [v for s in samples for v in s]
        out.append(
            {
                "sex_stratum": sex_stratum,
                "factor": factor,
                "level_a": "|".join(levels),
                "level_b": "",
                "n_a": len(all_vals),
                "n_b": 0,
                "median_a": float(np.median(all_vals)),
                "median_b": float("nan"),
                "stat": float(stat),
                "p": float(p),
                "test": "kruskal",
                "metric": "delta_excess_present_minus_absent",
            }
        )
        if factor == "tx":
            for i, a in enumerate(levels):
                for b in levels[i + 1 :]:
                    va, vb = by_level[a], by_level[b]
                    stat_pw, p_pw = stats.mannwhitneyu(va, vb, alternative="two-sided")
                    out.append(
                        {
                            "sex_stratum": sex_stratum,
                            "factor": factor,
                            "level_a": a,
                            "level_b": b,
                            "n_a": len(va),
                            "n_b": len(vb),
                            "median_a": float(np.median(va)),
                            "median_b": float(np.median(vb)),
                            "stat": float(stat_pw),
                            "p": float(p_pw),
                            "test": "mannwhitneyu_pairwise",
                            "metric": "delta_excess_present_minus_absent",
                        }
                    )

    _factor_tests(delta_rows, factor="tx", sex_stratum="all")
    _factor_tests(delta_rows, factor="sex", sex_stratum="all")
    for sex in sorted({str(r.get("sex", "")) for r in delta_rows if r.get("sex")}):
        subset = [r for r in delta_rows if str(r.get("sex", "")) == sex]
        _factor_tests(subset, factor="tx", sex_stratum=sex)
    return out
